import hmac
import hashlib
import httpx
import json
import asyncio
import os
import uuid
from dotenv import load_dotenv

# Load the secret from .env
load_dotenv()
SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "test_super_secret").encode("utf-8")

async def send_webhook():
    url = "http://localhost:8000/api/webhook"
    
    # Generate a unique Delivery ID for this test run
    delivery_id = str(uuid.uuid4())
    
    # Minimal payload that satisfies our webhook router
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 1,
            "head": {"sha": "abcdef123456"}
        },
        "repository": {
            "test-owner/test-repo": "test-owner/test-repo", # Adjusted for safety
            "full_name": "test-owner/test-repo"
        }
    }
    
    body = json.dumps(payload).encode("utf-8")
    
    # Calculate HMAC signature
    mac = hmac.new(SECRET, msg=body, digestmod=hashlib.sha256).hexdigest()
    signature = f"sha256={mac}"
    
    headers = {
        "Content-Type": "application/json",
        "X-GitHub-Event": "pull_request",
        "X-GitHub-Delivery": delivery_id,
        "X-Hub-Signature-256": signature
    }

    print(f"--- TEST 1: Sending FIRST Webhook (Delivery ID: {delivery_id}) ---")
    async with httpx.AsyncClient() as client:
        try:
            response1 = await client.post(url, content=body, headers=headers)
            print(f"Status: {response1.status_code}")
            print(f"Response: {response1.json()}\n")
        except httpx.ConnectError:
            print("ERROR: FastAPI server is not running! Please run 'uvicorn app.main:app --reload' first.\n")
            return
        
    print("--- TEST 2: Sending EXACT SAME Webhook (Testing Idempotency) ---")
    async with httpx.AsyncClient() as client:
        response2 = await client.post(url, content=body, headers=headers)
        print(f"Status: {response2.status_code}")
        print(f"Response: {response2.json()}\n")

if __name__ == "__main__":
    asyncio.run(send_webhook())
