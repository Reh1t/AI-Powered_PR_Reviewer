import httpx
import logging
import jwt
import time
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger("github-service")

class GithubService:
    """
    Handles all interactions with the GitHub REST API.
    Used for retrieving diffs and submitting reviews.
    """
    BASE_URL = "https://api.github.com"
    
    # Common system/media file extensions and configuration files that clutter the LLM context.
    NOISY_EXTENSIONS = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", 
        ".pdf", ".mp4", ".woff", ".woff2", ".ttf", ".eot",
        ".csv", ".xlsx", ".zip", ".tar", ".gz"
    )
    NOISY_FILES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
        "Pipfile.lock", "Gemfile.lock", "Cargo.lock"
    }

    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    async def _get_installation_token(self) -> str:
        """
        Performs the full GitHub App auth flow:
        - Decodes the RSA private key
        - Generates a short-lived JWT
        - Exchanges it for an Installation Access Token
        """
        private_key = settings.github_app_private_key.replace('\\n', '\n')
        now = int(time.time())
        payload = {
            "iss": settings.github_app_id,
            "iat": now - 60,
            "exp": now + (9 * 60)
        }
        
        encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")
        
        url = f"{self.BASE_URL}/app/installations/{settings.github_installation_id}/access_tokens"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {encoded_jwt}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            response.raise_for_status()
            return response.json()["token"]

    async def get_pr_diff(self, owner: str, repo: str, pull_number: int) -> List[Dict[str, Any]]:
        """
        Fetches the individual files modified in a PR.
        Filters out noisy artifacts.
        Returns a list of dicts heavily filtered for the LLM.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
        cleaned_files = []
        
        token = await self._get_installation_token()
        headers = {**self.headers, "Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            # Note: GitHub paginates this route. A robust implementation would handle pagination
            # if PRs have >30 files (default per-page). We add per_page=100 for better default coverage.
            response = await client.get(url, headers=headers, params={"per_page": 100})
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch PR files: {response.text}")
                response.raise_for_status()
                
            files = response.json()
            
            for file_data in files:
                filename = file_data.get("filename", "")
                patch = file_data.get("patch")
                status = file_data.get("status")
                
                # Filter out noisy files
                if filename.lower().endswith(self.NOISY_EXTENSIONS):
                    continue
                if any(filename.endswith(noisy) for noisy in self.NOISY_FILES):
                    continue
                # If there's no textual patch (e.g. only mode changes, binary files), skip.
                if not patch:
                    continue
                
                patch = self.chunk_diff(patch, filename)
                
                cleaned_files.append({
                    "filename": filename,
                    "status": status,
                    "patch": patch
                })
                
        return cleaned_files

    def chunk_diff(self, patch: str, filename: str) -> str:
        """
        Parses diff hunks and trims context to 3 lines around changes
        if the file patch exceeds the token limit.
        """
        estimated_tokens = len(patch.split()) * 1.3
        if estimated_tokens <= 1000:
            return patch

        lines = patch.split('\n')
        hunks: List[List[str]] = []
        current_hunk: List[str] = []
        
        # Isolate individual change fragments (hunks) by @@ headers
        for line in lines:
            if line.startswith('@@'):
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = [line]
            else:
                if current_hunk:
                    current_hunk.append(line)
        if current_hunk:
            hunks.append(current_hunk)
            
        truncated_lines = []
        
        for hunk in hunks:
            hunk_header = hunk[0]
            hunk_body = hunk[1:]
            
            # Identify all changed lines in this hunk
            changed_indices = {i for i, line in enumerate(hunk_body) if line.startswith('+') or line.startswith('-')}
            
            keep = [False] * len(hunk_body)
            for i in changed_indices:
                keep[i] = True
                
            # Context padding: preserve exactly 3 lines of surrounding context
            for i, line in enumerate(hunk_body):
                if line.startswith(' '):
                    if any(abs(i - c_idx) <= 3 for c_idx in changed_indices):
                        keep[i] = True
                elif line.startswith('\\'):
                    # Retain '\ No newline at end of file' if parent line is kept
                    if i > 0 and keep[i-1]:
                        keep[i] = True
                        
            truncated_lines.append(hunk_header)
            for i, line in enumerate(hunk_body):
                if keep[i]:
                    truncated_lines.append(line)
                    
        truncated_patch = '\n'.join(truncated_lines)
        truncated_tokens = len(truncated_patch.split()) * 1.3
        
        logger.info(f"Truncated diff for {filename}: {estimated_tokens:.0f} tokens -> {truncated_tokens:.0f} tokens")
        
        return truncated_patch

    async def post_pr_review(self, owner: str, repo: str, pull_number: int, commit_id: str, comments: List[Dict[str, Any]], body: str = "", event: str = "COMMENT") -> Dict[str, Any]:
        """
        Submits an official PR review using the GitHub API.
        
        :param commit_id: The SHA of the commit that the review applies to.
        :param comments: List of comment objects mapping to the `patch` lines.
        :param body: The main body text of the review.
        :param event: The review action (APPROVE, REQUEST_CHANGES, COMMENT).
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/reviews"
        
        payload: Dict[str, Any] = {
            "commit_id": commit_id,
            "event": event
        }
        if body:
            payload["body"] = body
        if comments:
            payload["comments"] = comments
            
        token = await self._get_installation_token()
        headers = {**self.headers, "Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.post(url, headers=headers, json=payload)
            
            if response.status_code not in (200, 201):
                logger.error(f"Failed to post PR review: {response.text}")
                response.raise_for_status()
                
            return response.json()

