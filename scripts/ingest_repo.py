import asyncio
import os
import sys

# Ensure the root directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag_service import RAGService
from app.services.github_service import GithubService

async def main():
    repo = input("Enter the repository to ingest (e.g., your-username/ai-powered-pr-reviewer): ").strip()
    if not repo:
        print("Invalid repository.")
        return

    print(f"Initializing FastEmbed (this may take a moment to download the model)...")
    rag = RAGService()
    
    # In a real scenario, you would clone the repo or use GitHub API to fetch all files.
    # For this script, we'll just read local files as an example if it's the current repo.
    # Or, we can just ingest some mock data to prove it works.
    
    choice = input(f"Do you want to ingest the local files of THIS project as '{repo}'? (y/n): ")
    if choice.lower() == 'y':
        print(f"Clearing old embeddings for '{repo}'...")
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("DELETE FROM code_embeddings WHERE repo = :repo"), {"repo": repo})
            await session.commit()
            
        print(f"Scanning local directory for .py files...")
        for root, dirs, files in os.walk("app"):
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        
                    print(f"Ingesting {file_path}...")
                    await rag.ingest_file(repo, file_path, content)
                    
        print(f"\nSuccess! Successfully embedded local app/ files into pgvector under repo '{repo}'")
    else:
        print("Skipping ingestion.")

if __name__ == "__main__":
    asyncio.run(main())
