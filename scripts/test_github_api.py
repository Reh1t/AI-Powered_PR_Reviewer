import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env manually for standalone script execution
load_dotenv()

# We patch sys.path so we can import from app without relative issues
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.github_service import GithubService
from app.core.config import settings

async def run_test():
    """
    Test script to verify GithubService interaction with real API endpoints.
    Requires GITHUB_TOKEN to be set in .env!
    """
    token = settings.github_token
    if not token or token == "your_github_token_here":
        print("ERROR: Please set a valid GITHUB_TOKEN in your .env file to run this test.")
        return

    # Using a popular public repo and PR as a test target
    # e.g., fastapi repo, PR #10000 (Replace with any known PR)
    owner = "tiangolo"
    repo = "fastapi"
    pr_number = 15375
    
    try:
        service = GithubService(token=token)
        print(f"Fetching PR files for {owner}/{repo}#{pr_number}...")
        files = await service.get_pr_diff(owner, repo, pr_number)
        
        print(f"\nSuccessfully fetched {len(files)} files!")
        
        for f in files:
            print(f"- Filename: {f['filename']}")
            print(f"  Status: {f['status']}")
            patch_preview = f['patch'][:100].replace('\n', ' ') + "..."
            print(f"  Patch preview: {patch_preview}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
