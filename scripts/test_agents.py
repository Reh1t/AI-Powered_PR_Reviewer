import asyncio
import os
import sys

# Ensure the root directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.ai_agents.graph import pr_review_graph

async def main():
    print("Initializing LangGraph Multi-Agent Test...")
    
    # We will simulate a diff that contains multiple issues to see if the agents fan-out correctly.
    # - Security: SQL Injection vulnerability (using string formatting for queries)
    # - Performance: O(n^2) nested loop over users
    # - Style: Bad variable names and missing type hints
    
    fake_diff = """
    @@ -10,15 +10,15 @@
    - def get_user_data(user_id: int) -> dict:
    -     return db.execute("SELECT * FROM users WHERE id = :id", {"id": user_id})
    + def get_user_data(u):
    +     # Fetch user
    +     q = f"SELECT * FROM users WHERE id = {u}"
    +     user = db.execute(q)
    +     
    +     # Check permissions for all other users (O(n^2) bottleneck)
    +     all_users = db.execute("SELECT * FROM users")
    +     for other in all_users:
    +         for p in other.permissions:
    +             if p == "admin":
    +                 pass
    +                 
    +     return user
    """
    
    files_dict = {"app/db/user_queries.py": fake_diff}
    
    initial_state = {
        "files_dict": files_dict,
        "rag_context": "No historical context needed for this test.",
        "security_findings": [],
        "performance_findings": [],
        "style_findings": [],
        "final_findings": []
    }
    
    print("\n--- Invoking LangGraph ---")
    print("Agents should process this concurrently...")
    
    final_state = await pr_review_graph.ainvoke(initial_state)
    
    print("\n--- GRAPH EXECUTION COMPLETE ---")
    print(f"Total Findings Merged by Aggregator: {len(final_state['final_findings'])}")
    
    print("\n--- DETAILED FINDINGS ---")
    for idx, finding in enumerate(final_state['final_findings']):
        print(f"\nFinding #{idx + 1} (Found by: {finding.agent_category})")
        print(f"File: {finding.file_path}:{finding.line_number}")
        print(f"Type: {finding.vulnerability_type} ({finding.severity})")
        print(f"Fix: {finding.suggested_fix_comment[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())
