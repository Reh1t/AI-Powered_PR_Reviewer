import hmac
import hashlib
import json
import httpx
import logging
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tester")

WEBHOOK_URL = "http://127.0.0.1:8000/api/webhook"
SECRET = "test_super_secret"

def sign_payload(payload_bytes: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode('utf-8'), msg=payload_bytes, digestmod=hashlib.sha256).hexdigest()
    return f"sha256={mac}"

async def run_tests():
    payload = {
        "action": "opened",
        "pull_request": {
            "number": 1337,
            "title": "Test PR"
        }
    }
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    
    async with httpx.AsyncClient() as client:
        # Test 1: Missing Header
        logger.info("Test 1: Sending request with no signature header...")
        resp = await client.post(
            WEBHOOK_URL,
            content=payload_bytes,
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"}
        )
        logger.info(f"Response: {resp.status_code} - {resp.text}")
        assert resp.status_code == 401, "Test 1 Failed"
        
        # Test 2: Invalid Signature
        logger.info("Test 2: Sending request with invalid signature header...")
        resp = await client.post(
            WEBHOOK_URL,
            content=payload_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": "sha256=invalid_signature_here"
            }
        )
        logger.info(f"Response: {resp.status_code} - {resp.text}")
        assert resp.status_code == 401, "Test 2 Failed"
        
        # Test 3: Valid Signature
        logger.info("Test 3: Sending request with VALID signature header...")
        valid_signature = sign_payload(payload_bytes, SECRET)
        resp = await client.post(
            WEBHOOK_URL,
            content=payload_bytes,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": valid_signature
            }
        )
        logger.info(f"Response: {resp.status_code} - {resp.text}")
        assert resp.status_code == 200, "Test 3 Failed"
        assert resp.json()["status"] == "accepted", "Test 3 Json validation Failed"
        
        logger.info("All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(run_tests())
