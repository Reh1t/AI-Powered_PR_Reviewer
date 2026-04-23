import instructor
from groq import AsyncGroq
from app.core.config import settings
from app.schemas.ai_schemas import ReviewResult

# Define strict SYSTEM PROMPT for AppSec code evaluation
SYSTEM_PROMPT = """
You are a Senior Application Security Engineer performing a Pull Request Code Review.
Your task is to analyze the provided code changes (git diffs) and identify security vulnerabilities, 
architectural flaws, and logic bugs, with a focus on the OWASP Top 10.

CRITICAL INSTRUCTIONS:
1. ONLY flag genuine security issues or severe anti-patterns. Do NOT comment on minor stylistic issues.
2. For each issue, provide the precise file_path and an approximate line_number (or best guess based on the patch).
3. If no issues are found, return an empty findings list. Do NOT hallucinate issues.
4. Your findings must strictly adhere to the provided JSON schema.
"""

class AIReviewerService:
    def __init__(self):
        # Initialize Groq client natively via official SDK
        # We patch it with Instructor to enforce pure JSON structured outputs mathematically.
        self.client = instructor.from_groq(
            AsyncGroq(api_key=settings.llm_api_key)
        )
        self.model_name = settings.llm_model_name

    async def analyze_diff(self, files_dict: dict[str, str]) -> ReviewResult:
        """
        Analyze a dictionary of file diffs and return a structured Pydantic object of vulnerabilities.
        files_dict maps filename (str) to git patch content (str).
        """
        
        # Format the user payload
        # For large diffs, we may eventually need to chunk this or use Map-Reduce.
        prompt = "Review the following incoming Pull Request code changes:\n\n"
        for file_path, patch in files_dict.items():
            prompt += f"--- FILE: {file_path} ---\n{patch}\n\n"
            
        print(f"Sending payloads to LLM ({self.model_name}) for analysis...")
        
        # Invoke the instructor-wrapped response
        response = await self.client.chat.completions.create(
            model=self.model_name,
            response_model=ReviewResult,
            temperature=0.0, # Zero temperature to prevent hallucination and improve determinism
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response
