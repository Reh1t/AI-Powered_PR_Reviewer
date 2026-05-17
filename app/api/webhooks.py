from fastapi import APIRouter, Depends, Request
import logging
from app.api.dependencies import verify_github_signature
from app.services.github_service import GithubService

# Setup basic logger
logger = logging.getLogger("webhook-router")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])

@router.post("", dependencies=[Depends(verify_github_signature)])
async def handle_github_webhook(request: Request):
    """
    Receives and processes GitHub webhook events.
    Access to this endpoint is strictly protected by the `verify_github_signature` dependency.
    """
    # Parse the JSON payload
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    
    logger.info(f"Received valid GitHub webhook: event_type={event_type}")
    
    # For now, just log the event and fetch PR files to prove interaction. 
    # LLM generation and actual review processing will be integrated later.
    if event_type == "pull_request":
        action = payload.get("action")
        pr_data = payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        repo_full_name = payload.get("repository", {}).get("full_name")
        
        logger.info(f"Processing pull request event: action={action}, repo={repo_full_name}, pr={pr_number}")
        
        if action in ["opened", "synchronize"] and repo_full_name and pr_number:
            owner, repo = repo_full_name.split("/", 1)
            commit_id = pr_data.get("head", {}).get("sha")
            
            # Use GitHub App Flow configured natively within GithubService
            github_service = GithubService()
            
            try:
                # 1. Fetch clean patch representation
                diff_files = await github_service.get_pr_diff(owner, repo, pr_number)
                logger.info(f"Successfully fetched {len(diff_files)} meaningful files for analysis from {repo_full_name}#{pr_number}")
                
                if not diff_files:
                    logger.info("No meaningful code changes detected (only ignored files). Skipping AI review.")
                    return {"status": "skipped_no_meaningful_files"}
                
                # 2. Convert to dictionary for AI Reviewer
                files_dict = {f["filename"]: f["patch"] for f in diff_files}
                
                # 3. Analyze with Groq LLM
                from app.services.ai_reviewer import AIReviewerService
                ai_reviewer = AIReviewerService()
                review_result = await ai_reviewer.analyze_diff(files_dict)
                
                logger.info(f"AI Review completed. Found {len(review_result.findings)} findings.")
                
                # 4. Construct PR Review
                if review_result.findings:
                    # Construct an overarching markdown summary
                    summary_body = "## 🛡️ AI Security & Architecture Review\n\nI have reviewed the changes in this PR. "
                    summary_body += f"I found **{len(review_result.findings)}** potential vulnerabilities or architectural concerns.\n\n"
                    
                    summary_body += "| Severity | Vulnerability | File | Suggested Fix |\n"
                    summary_body += "|----------|---------------|------|---------------|\n"
                    
                    has_critical = False
                    
                    for finding in review_result.findings:
                        if finding.severity.name in ["HIGH", "CRITICAL"]:
                            has_critical = True
                        # Clean up newlines in comments to fit in table gracefully
                        clean_comment = finding.suggested_fix_comment.replace('\\n', ' ').replace('\n', ' ')
                        summary_body += f"| {finding.severity.name} | {finding.vulnerability_type} | `{finding.file_path}:{finding.line_number}` | {clean_comment} |\n"
                    
                    # Instead of brittle inline comments with `position` math, we post a high-value summary comment
                    # Request Changes if High/Critical issues exist!
                    event_type = "REQUEST_CHANGES" if has_critical else "COMMENT"
                    
                    # 5. Post to GitHub
                    await github_service.post_pr_review(
                        owner=owner,
                        repo=repo,
                        pull_number=pr_number,
                        commit_id=commit_id,
                        comments=[], # Skipping inline comments to prevent positional API errors for now
                        body=summary_body,
                        event=event_type
                    )
                    logger.info("Successfully posted AI PR Review to GitHub!")
                else:
                    # Pass the PR
                    await github_service.post_pr_review(
                        owner=owner, 
                        repo=repo, 
                        pull_number=pr_number, 
                        commit_id=commit_id,
                        comments=[],
                        body="## 🛡️ AI Security Review\n\nNo significant security vulnerabilities or architectural flaws detected. LGTM! ✅",
                        event="APPROVE"
                    )
                    logger.info("Successfully posted AI APPROVAL to GitHub!")
                
            except Exception as e:
                logger.error(f"Failed to process PR webhook end-to-end: {str(e)}")
                
    return {"status": "accepted"}
