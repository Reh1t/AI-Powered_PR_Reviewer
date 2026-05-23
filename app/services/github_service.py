import httpx
import logging
import jwt
import time
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
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
        ".csv", ".xlsx", ".zip", ".tar", ".gz", ".map"
    )
    # Sensitive files that should NEVER be sent to an LLM
    SENSITIVE_FILES = {
        ".env", ".pem", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
        "secret", "password", "credentials", ".p12", ".pfx", ".key"
    }
    NOISY_FILES = {
        "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
        "Pipfile.lock", "Gemfile.lock", "Cargo.lock", "pnpm-workspace.yaml"
    }

    def __init__(self):
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=6),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True
    )
    async def _get_installation_token(self) -> str:
        """
        Performs the full GitHub App auth flow with retries.
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
        Fetches the individual files modified in a PR with pagination support.
        Filters out noisy and sensitive artifacts.
        """
        cleaned_files = []
        token = await self._get_installation_token()
        headers = {**self.headers, "Authorization": f"Bearer {token}"}
        
        async with httpx.AsyncClient(follow_redirects=True) as client:
            page = 1
            while True:
                url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pull_number}/files"
                params = {"per_page": 100, "page": page}
                
                response = await client.get(url, headers=headers, params=params)
                if response.status_code != 200:
                    logger.error(f"Failed to fetch PR files: {response.text}")
                    response.raise_for_status()
                
                files = response.json()
                if not files:
                    break
                    
                for file_data in files:
                    filename = file_data.get("filename", "")
                    patch = file_data.get("patch")
                    status = file_data.get("status")
                    
                    # 1. Skip sensitive files
                    if any(s in filename.lower() for s in self.SENSITIVE_FILES):
                        logger.warning(f"Skipping sensitive file: {filename}")
                        continue
                        
                    # 2. Skip noisy extensions
                    if filename.lower().endswith(self.NOISY_EXTENSIONS):
                        continue
                        
                    # 3. Skip noisy lock files
                    if any(filename.endswith(noisy) for noisy in self.NOISY_FILES):
                        continue
                        
                    # 4. Skip non-textual patches
                    if not patch:
                        continue
                    
                    # 5. Smart truncation
                    patch = self.chunk_diff(patch, filename)
                    
                    cleaned_files.append({
                        "filename": filename,
                        "status": status,
                        "patch": patch
                    })
                
                if len(files) < 100:
                    break
                page += 1
                
        return cleaned_files

    def chunk_diff(self, patch: str, filename: str) -> str:
        """
        Aggressively truncates diffs to stay within token limits while preserving context.
        """
        estimated_tokens = len(patch.split()) * 1.3
        
        # Determine context size based on total length. 
        # For huge files, reduce context to 1 line.
        context_size = 1 if estimated_tokens > 2000 else 2

        lines = patch.split('\n')
        hunks: List[List[str]] = []
        current_hunk: List[str] = []
        
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
            
            changed_indices = {i for i, line in enumerate(hunk_body) if line.startswith('+') or line.startswith('-')}
            if not changed_indices:
                continue

            keep = [False] * len(hunk_body)
            for i in changed_indices:
                keep[i] = True
                for j in range(max(0, i - context_size), min(len(hunk_body), i + context_size + 1)):
                    if hunk_body[j].startswith(' '):
                        keep[j] = True
                # Always keep line continuation or no-newline markers if relevant
                if i + 1 < len(hunk_body) and hunk_body[i+1].startswith('\\'):
                    keep[i+1] = True
                        
            truncated_lines.append(hunk_header)
            for i, line in enumerate(hunk_body):
                if keep[i]:
                    truncated_lines.append(line)
                    
        truncated_patch = '\n'.join(truncated_lines)
        truncated_tokens = len(truncated_patch.split()) * 1.3
        
        if truncated_tokens < estimated_tokens:
            logger.info(f"Truncated {filename}: {estimated_tokens:.0f} -> {truncated_tokens:.0f} tokens")
        
        return truncated_patch

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=6),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True
    )
    async def post_pr_review(self, owner: str, repo: str, pull_number: int, commit_id: str, comments: List[Dict[str, Any]], body: str = "", event: str = "COMMENT") -> Dict[str, Any]:
        """
        Submits an official PR review with retries.
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
