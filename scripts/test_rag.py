import asyncio
import os
import sys

# Ensure the root directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.rag_service import RAGService

async def main():
    print("Initializing RAG Service (Loading FastEmbed model)...")
    rag = RAGService()
    
    repo = input("Enter the repository name you ingested (e.g., test-owner/test-repo): ").strip()
    
    # A fake diff that simulates a security issue (e.g., hardcoded secret or auth bypass)
    # We will search the database to find related authentication or config files.
    fake_diff = """
    @@ -10,5 +10,5 @@
    - def verify_user(token):
    -     return jwt.decode(token, SECRET)
    + def verify_user(token):
    +     # TODO: Fix signature validation
    +     return jwt.decode(token, "hardcoded_secret_key", options={"verify_signature": False})
    """
    
    print("\n--- Simulating PR Diff ---")
    print(fake_diff)
    
    print("\n--- Retrieving Semantic Context from pgvector ---")
    context = await rag.retrieve_context(repo, fake_diff, limit=2)
    
    print(context)
    print("\nTest Complete! The above context would be injected into the LLM's system prompt.")

if __name__ == "__main__":
    asyncio.run(main())
