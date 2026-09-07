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

You will be provided with "Historical RAG Context" (semantically related files from the codebase).
Use this context to understand the broader architecture, conventions, and existing implementations 
before passing judgment on the PR diff. Do not flag issues that are already established patterns 
in the RAG context unless they are explicitly vulnerable.

CRITICAL INSTRUCTIONS:
1. ONLY flag genuine security issues or severe anti-patterns. Do NOT comment on minor stylistic issues.
2. For each issue, provide the precise file_path and an approximate line_number (or best guess based on the patch).
3. If no issues are found, return an empty findings list. Do NOT hallucinate issues.
4. Your findings must strictly adhere to the provided JSON schema.
"""

from app.services.ai_agents.graph import pr_review_graph

class AIReviewerService:
    # Enterprise constraint: Groq Free/On-Demand tier has a very low TPM (12,000)
    MAX_BATCH_TOKENS = 5000 

    async def analyze_diff(self, files_dict: dict[str, str], rag_context: str = "") -> ReviewResult:
        """
        Analyze a dictionary of file diffs using a batched approach to respect token limits.
        Invokes the LangGraph Multi-Agent Fan-Out for each batch.
        Returns an aggregated ReviewResult.
        """
        all_findings: list[ReviewFinding] = []
        current_batch_files: dict[str, str] = {}
        current_batch_tokens = 0

        # Sort files by size to optimize packing
        sorted_files = sorted(files_dict.items(), key=lambda x: len(x[1]), reverse=True)

        for file_path, patch in sorted_files:
            file_tokens = len(patch.split()) * 1.3
            
            if file_tokens > self.MAX_BATCH_TOKENS:
                logger.warning(f"File {file_path} is very large ({file_tokens:.0f} tokens). Processing in isolation.")
                isolated_result = await self._process_batch_with_graph({file_path: patch}, rag_context)
                all_findings.extend(isolated_result.findings)
                continue

            if current_batch_tokens + file_tokens > self.MAX_BATCH_TOKENS:
                batch_result = await self._process_batch_with_graph(current_batch_files, rag_context)
                all_findings.extend(batch_result.findings)
                
                current_batch_files = {file_path: patch}
                current_batch_tokens = file_tokens
                await asyncio.sleep(1)
            else:
                current_batch_files[file_path] = patch
                current_batch_tokens += file_tokens

        if current_batch_files:
            batch_result = await self._process_batch_with_graph(current_batch_files, rag_context)
            all_findings.extend(batch_result.findings)

        return ReviewResult(findings=all_findings)

    async def _process_batch_with_graph(self, batch_files: dict[str, str], rag_context: str) -> ReviewResult:
        """
        Invokes the LangGraph workflow for a batch of files.
        """
        if not batch_files:
            return ReviewResult(findings=[])

        logger.info(f"Invoking Multi-Agent LangGraph for batch of {len(batch_files)} files...")
        try:
            # Prepare the initial state
            initial_state = {
                "files_dict": batch_files,
                "rag_context": rag_context,
                "security_findings": [],
                "performance_findings": [],
                "style_findings": [],
                "final_findings": []
            }
            
            # Run the graph
            final_state = await pr_review_graph.ainvoke(initial_state)
            
            return ReviewResult(findings=final_state.get("final_findings", []))
        except Exception as e:
            logger.error(f"LangGraph execution failed: {str(e)}")
            return ReviewResult(findings=[])
