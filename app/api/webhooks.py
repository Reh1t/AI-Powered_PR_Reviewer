from fastapi import APIRouter, Depends, Request, BackgroundTasks
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.api.dependencies import verify_github_signature
from app.services.github_service import GithubService
from app.services.ai_reviewer import AIReviewerService
from app.services.rag_service import RAGService
from app.core.database import get_db, AsyncSessionLocal
from app.models.webhook import WebhookEvent, WebhookStatus
from app.models.review import PRReview

# Setup basic logger
logger = logging.getLogger("webhook-router")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/api/webhook", tags=["webhooks"])

async def process_pr_review_task(delivery_id: str, owner: str, repo: str, pr_number: int, commit_id: str):
    """
    Background task to process the PR review. 
    Handles fetching diffs, AI analysis, and posting the review back to GitHub.
    """
    github_service = GithubService()
    ai_reviewer = AIReviewerService()
    rag_service = RAGService()
    full_repo_name = f"{owner}/{repo}"
    
    async with AsyncSessionLocal() as session:
        try:
            # 1. Fetch clean patch representation
            diff_files = await github_service.get_pr_diff(owner, repo, pr_number)
            logger.info(f"Processing background review for {repo}#{pr_number}: {len(diff_files)} files fetched.")
            
            if not diff_files:
                logger.info(f"No meaningful code changes for {repo}#{pr_number}. Skipping.")
                return

            # 2. Convert to dictionary for AI Reviewer
            files_dict = {f["filename"]: f["patch"] for f in diff_files}
            
            # 3. Retrieve Historical RAG Context (Embed the diff patches)
            diff_text = "\n".join(files_dict.values())
            rag_context = await rag_service.retrieve_context(full_repo_name, diff_text, limit=3)
            logger.info(f"Retrieved RAG context for {repo}#{pr_number}")
            
            # 4. Analyze with Groq LLM (now uses batching internally)
            review_result = await ai_reviewer.analyze_diff(files_dict, rag_context)
            logger.info(f"AI Review completed for {repo}#{pr_number}. Found {len(review_result.findings)} findings.")
            
            # 4. Construct PR Review Summary
            event_type = "COMMENT"
            if review_result.findings:
                summary_body = "## 🛡️ AI Security & Architecture Review\n\nI have reviewed the changes in this PR. "
                summary_body += f"I found **{len(review_result.findings)}** potential vulnerabilities or architectural concerns.\n\n"
                
                summary_body += "| Severity | Vulnerability | File | Suggested Fix |\n"
                summary_body += "|----------|---------------|------|---------------|\n"
                
                has_critical = False
                for finding in review_result.findings:
                    if finding.severity.name in ["HIGH", "CRITICAL"]:
                        has_critical = True
                    clean_comment = finding.suggested_fix_comment.replace('\\n', ' ').replace('\n', ' ')
                    summary_body += f"| {finding.severity.name} | {finding.vulnerability_type} | `{finding.file_path}:{finding.line_number}` | {clean_comment} |\n"
                
                event_type = "REQUEST_CHANGES" if has_critical else "COMMENT"
                
                # 5. Post to GitHub
                await github_service.post_pr_review(
                    owner=owner,
                    repo=repo,
                    pull_number=pr_number,
                    commit_id=commit_id,
                    comments=[], 
                    body=summary_body,
                    event=event_type
                )
            else:
                event_type = "APPROVE"
                # Pass the PR
                await github_service.post_pr_review(
                    owner=owner, 
                    repo=repo, 
                    pull_number=pr_number, 
                    commit_id=commit_id,
                    comments=[],
                    body="## 🛡️ AI Security Review\n\nNo significant security vulnerabilities or architectural flaws detected. LGTM! ✅",
                    event=event_type
                )
            
            # Record Review in DB
            pr_review = PRReview(
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                commit_sha=commit_id,
                status=event_type,
                findings_count=len(review_result.findings),
                findings_summary=[finding.model_dump() for finding in review_result.findings]
            )
            session.add(pr_review)
            
            # Update Webhook status
            stmt = select(WebhookEvent).filter_by(delivery_id=delivery_id)
            result = await session.execute(stmt)
            webhook_event = result.scalars().first()
            if webhook_event:
                webhook_event.status = WebhookStatus.SUCCESS

            await session.commit()
            logger.info(f"Successfully posted review for {repo}#{pr_number}")

        except Exception as e:
            logger.error(f"Error in background task for {repo}#{pr_number}: {str(e)}")
            stmt = select(WebhookEvent).filter_by(delivery_id=delivery_id)
            result = await session.execute(stmt)
            webhook_event = result.scalars().first()
            if webhook_event:
                webhook_event.status = WebhookStatus.FAILED
                await session.commit()

@router.post("", dependencies=[Depends(verify_github_signature)])
async def handle_github_webhook(request: Request, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """
    Receives GitHub webhook events and offloads heavy processing to background tasks.
    Idempotent by X-GitHub-Delivery ID.
    """
    delivery_id = request.headers.get("X-GitHub-Delivery")
    if not delivery_id:
        return {"status": "error", "message": "Missing X-GitHub-Delivery header"}
        
    event_type = request.headers.get("X-GitHub-Event", "unknown")
    payload = await request.json()
    action = payload.get("action")
    
    # Check Idempotency
    stmt = select(WebhookEvent).filter_by(delivery_id=delivery_id)
    result = await db.execute(stmt)
    existing_event = result.scalars().first()
    
    if existing_event:
        logger.info(f"Webhook {delivery_id} already processed or processing (Status: {existing_event.status.value}). Idempotent return.")
        return {"status": "idempotent", "event_type": event_type, "webhook_status": existing_event.status.value}
        
    # Record new event
    new_event = WebhookEvent(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        status=WebhookStatus.PENDING
    )
    db.add(new_event)
    await db.commit()
    
    logger.info(f"Received GitHub webhook: delivery_id={delivery_id}, event_type={event_type}")
    
    if event_type == "pull_request":
        pr_data = payload.get("pull_request", {})
        pr_number = pr_data.get("number")
        repo_data = payload.get("repository", {})
        repo_full_name = repo_data.get("full_name")
        
        # We only care about events that change code or open a new PR
        if action in ["opened", "synchronize", "reopened"] and repo_full_name and pr_number:
            owner, repo = repo_full_name.split("/", 1)
            commit_id = pr_data.get("head", {}).get("sha")
            
            # Offload to background task to respond to GitHub immediately
            background_tasks.add_task(
                process_pr_review_task,
                delivery_id=delivery_id,
                owner=owner,
                repo=repo,
                pr_number=pr_number,
                commit_id=commit_id
            )
            logger.info(f"Queued background review task for {repo_full_name}#{pr_number}")
            return {"status": "queued", "action": action}
            
    return {"status": "accepted", "event_type": event_type}

