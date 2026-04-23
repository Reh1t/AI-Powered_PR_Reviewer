import asyncio
import os
import sys

# Ensure the app module is importable when running as a direct script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load local environment variables for the test
load_dotenv()

from app.services.ai_reviewer import AIReviewerService

async def test_ai_reviewer():
    if not os.getenv("LLM_API_KEY"):
        print("ERROR: LLM_API_KEY is not set in the .env file.")
        print("Skipping AI integration test.")
        return

    reviewer = AIReviewerService()
    
    # Simulate a patch with an obvious SQL injection vulnerability
    dummy_files = {
        "app/database.py": """@@ -0,0 +1,5 @@
+import sqlite3
+
+def get_user(user_id: str):
+    conn = sqlite3.connect('test.db')
+    # DANGER: String concatenation SQL injection!
+    query = "SELECT * FROM users WHERE id = " + user_id
+    return conn.execute(query).fetchall()
"""
    }

    print("Executing standalone Groq LLM integration test...")
    try:
        result = await reviewer.analyze_diff(dummy_files)
        
        print("\n=== AI REVIEW COMPLETED SUCCESSFULLY ===")
        print(f"Total findings: {len(result.findings)}")
        for finding in result.findings:
            print("\n------------------------------")
            print(f"File:     {finding.file_path}:{finding.line_number}")
            print(f"Type:     {finding.vulnerability_type} ({finding.severity})")
            print(f"Comment:  {finding.suggested_fix_comment}")
            print("------------------------------")
            
        if len(result.findings) == 0:
            print("WARNING: The LLM did not detect the obvious SQL injection! This indicates an issue with the prompt or model.")
            
    except Exception as e:
        print(f"Failed to execute AI review: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_reviewer())
