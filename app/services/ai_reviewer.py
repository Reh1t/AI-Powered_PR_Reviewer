import instructor
import logging
import asyncio
from groq import AsyncGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.core.config import settings
from app.schemas.ai_schemas import ReviewResult, ReviewFinding

logger = logging.getLogger("ai-reviewer")

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
    # Enterprise constraint: Groq Free/On-Demand tier has a very low TPM (12,000)
    # We target ~5,000 tokens per batch to leave plenty of room for:
    # 1. The System Prompt (~500 tokens)
    # 2. The AI's structured response (~1000-2000 tokens)
    # 3. Buffer for token calculation variance
    MAX_BATCH_TOKENS = 5000 

    def __init__(self):
        # Initialize Groq client natively via official SDK
        # We patch it with Instructor to enforce pure JSON structured outputs mathematically.
        self.client = instructor.from_groq(
            AsyncGroq(api_key=settings.llm_api_key)
        )
        self.model_name = settings.llm_model_name

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True
    )
    async def _call_llm(self, prompt: str) -> ReviewResult:
        """
        Internal method to call the LLM with retry logic.
        """
        return await self.client.chat.completions.create(
            model=self.model_name,
            response_model=ReviewResult,
            temperature=0.0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT.strip()},
                {"role": "user", "content": prompt}
            ]
        )

    async def analyze_diff(self, files_dict: dict[str, str]) -> ReviewResult:
        """
        Analyze a dictionary of file diffs using a batched approach to respect token limits.
        Returns an aggregated ReviewResult.
        """
        all_findings: list[ReviewFinding] = []
        current_batch_files: dict[str, str] = {}
        current_batch_tokens = 0

        # Sort files by size to optimize packing (optional but good)
        sorted_files = sorted(files_dict.items(), key=lambda x: len(x[1]), reverse=True)

        for file_path, patch in sorted_files:
            file_tokens = len(patch.split()) * 1.3
            
            # If a single file is too large for a batch, we process it alone (it was already truncated in GithubService)
            if file_tokens > self.MAX_BATCH_TOKENS:
                logger.warning(f"File {file_path} is very large ({file_tokens:.0f} tokens). Processing in isolation.")
                isolated_result = await self._process_batch({file_path: patch})
                all_findings.extend(isolated_result.findings)
                continue

            if current_batch_tokens + file_tokens > self.MAX_BATCH_TOKENS:
                # Process the current batch before starting a new one
                batch_result = await self._process_batch(current_batch_files)
                all_findings.extend(batch_result.findings)
                
                # Reset for next batch
                current_batch_files = {file_path: patch}
                current_batch_tokens = file_tokens
                # Add a small delay between batches to respect Rate Limits (RPM)
                await asyncio.sleep(1)
            else:
                current_batch_files[file_path] = patch
                current_batch_tokens += file_tokens

        # Process the final remaining batch
        if current_batch_files:
            batch_result = await self._process_batch(current_batch_files)
            all_findings.extend(batch_result.findings)

        return ReviewResult(findings=all_findings)

    async def _process_batch(self, batch_files: dict[str, str]) -> ReviewResult:
        """
        Helper to format a batch and call the LLM.
        """
        if not batch_files:
            return ReviewResult(findings=[])

        prompt = "Review the following code changes:\n\n"
        for file_path, patch in batch_files.items():
            prompt += f"--- FILE: {file_path} ---\n{patch}\n\n"

        logger.info(f"Sending batch of {len(batch_files)} files to LLM...")
        try:
            return await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"LLM Batch processing failed after retries: {str(e)}")
            # Return empty findings for this batch rather than crashing the whole PR review
            return ReviewResult(findings=[])
