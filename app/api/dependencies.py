import hmac
import hashlib
from fastapi import Request, HTTPException, status
from app.core.config import settings

async def verify_github_signature(request: Request) -> None:
    """
    Verifies the X-Hub-Signature-256 header using the locally configured GITHUB_WEBHOOK_SECRET.
    Validates that the payload is genuinely from GitHub and hasn't been tampered with.
    """
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header"
        )
    
    # Read the raw request body (needed for HMAC calculation)
    # request.body() is safe to call multiple times in FastAPI as long as it's awaited first.
    body = await request.body()
    
    # Calculate the expected HMAC
    secret_bytes = settings.github_webhook_secret.encode("utf-8")
    expected_mac = hmac.new(secret_bytes, msg=body, digestmod=hashlib.sha256).hexdigest()
    expected_signature = f"sha256={expected_mac}"
    
    # Use hmac.compare_digest for constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_header, expected_signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
