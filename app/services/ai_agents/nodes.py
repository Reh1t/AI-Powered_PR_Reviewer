import logging
import re
from typing import Dict, List
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.schemas.ai_schemas import ReviewFinding, SeverityLevel
from app.services.ai_agents.state import PRReviewState

logger = logging.getLogger("ai-agents")

# Shared LLM Client using local Ollama (Raw AsyncOpenAI, NO INSTRUCTOR)
client = AsyncOpenAI(
    base_url=settings.ollama_base_url,
    api_key=settings.llm_api_key
)

def _parse_markdown_response(text: str) -> List[ReviewFinding]:
    """Parses the strict markdown format back into Pydantic objects."""
    if "ISSUES_FOUND: NO" in text.upper() or "ISSUES_FOUND: FALSE" in text.upper():
        return []
        
    findings = []
    
    # We split by "ISSUES_FOUND: YES" to handle multiple findings if the LLM generated them
    blocks = text.split("ISSUES_FOUND: YES")
    for block in blocks[1:]:  # Skip the first split which is usually empty or prelude
        try:
            finding = ReviewFinding(
                file_path="unknown",
                line_number=0,
                internal_reasoning="None provided.",
                vulnerability_type="Unknown",
                severity=SeverityLevel.MEDIUM,
                suggested_fix_comment="None provided."
            )
            
            # Simple regex extractors
            agent_match = re.search(r"AGENT:\s*(.+)", block, re.IGNORECASE)
            if agent_match: finding.agent_category = agent_match.group(1).strip()
            
            type_match = re.search(r"TYPE:\s*(.+)", block, re.IGNORECASE)
            if type_match: finding.vulnerability_type = type_match.group(1).strip()
                
            file_match = re.search(r"FILE:\s*(.+)", block, re.IGNORECASE)
            if file_match: finding.file_path = file_match.group(1).strip()
                
            line_match = re.search(r"LINE:\s*(\d+)", block, re.IGNORECASE)
            if line_match: finding.line_number = int(line_match.group(1).strip())
                
            reasoning_match = re.search(r"REASONING:\s*(.+?)(?=\n[A-Z]+:|$)", block, re.IGNORECASE | re.DOTALL)
            if reasoning_match: finding.internal_reasoning = reasoning_match.group(1).strip()
                
            fix_match = re.search(r"FIX:\s*(.+?)(?=\n[A-Z]+:|$)", block, re.IGNORECASE | re.DOTALL)
            if fix_match: finding.suggested_fix_comment = fix_match.group(1).strip()
            
            findings.append(finding)
        except Exception as e:
            logger.error(f"Failed to parse block: {e}")
            
    return findings

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
async def _call_agent(system_prompt: str, files_dict: Dict[str, str], rag_context: str) -> List[ReviewFinding]:
    """Helper to format the batch and call the LLM using Raw Text/Markdown."""
    if not files_dict:
        return []

    # Explicitly separate the RAG context from the new code changes
    prompt = f"""
{rag_context}

### IMPORTANT INSTRUCTIONS ###
DO NOT REVIEW THE HISTORICAL RAG CONTEXT ABOVE! It is only there to help you understand the architecture.
ONLY REVIEW THE NEW CODE CHANGES BELOW:

"""
    for file_path, patch in files_dict.items():
        prompt += f"--- NEW FILE DIFF: {file_path} ---\n{patch}\n\n"

    try:
        response = await client.chat.completions.create(
            model=settings.llm_model_name,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": prompt}
            ]
        )
        
        raw_text = response.choices[0].message.content
        return _parse_markdown_response(raw_text)
    except Exception as e:
        logger.error(f"Agent processing failed: {str(e)}")
        return []

# -----------------------------------------------------------------
# FAN-OUT AGENTS
# -----------------------------------------------------------------

base_format_instructions = """
OUTPUT FORMAT RULES:
If you find absolutely zero issues belonging to your domain, output EXACTLY this and nothing else:
ISSUES_FOUND: NO

If you find an issue, output it EXACTLY in this format:
ISSUES_FOUND: YES
AGENT: <Your assigned domain (e.g. Security, Performance, Style)>
TYPE: <Name of vulnerability/issue>
FILE: <File path from the diff>
LINE: <Line number>
REASONING: <Your step-by-step reasoning for why this is a valid issue>
FIX: <Markdown formatted string on how to fix it>
"""

async def security_agent(state: PRReviewState) -> PRReviewState:
    logger.info("Running Security Agent...")
    prompt = f"""
    You are a strictly specialized Application Security Engineer.
    Focus ONLY on security vulnerabilities (OWASP Top 10, Auth bypass, SQLi, XSS, exposed secrets).
    
    CRITICAL CONSTRAINTS:
    - DO NOT comment on performance, style, or general architecture.
    - If no security issues are found, return ISSUES_FOUND: NO.
    
    FEW-SHOT EXAMPLES:
    Example 1 (Input has bad variable names):
    ISSUES_FOUND: NO
    
    Example 2 (Input has `open(f'/var/www/{{file}}')`):
    ISSUES_FOUND: YES
    AGENT: Security
    TYPE: Path Traversal
    FILE: app/main.py
    LINE: 12
    REASONING: User input is directly concatenated into a file path, allowing path traversal.
    FIX: Use a secure library like `pathlib` or sanitize the input.
    
    {base_format_instructions}
    """
    findings = await _call_agent(prompt, state["files_dict"], state["rag_context"])
    return {"security_findings": findings}

async def performance_agent(state: PRReviewState) -> PRReviewState:
    logger.info("Running Performance Agent...")
    prompt = f"""
    You are a strictly specialized Performance Engineer.
    Focus ONLY on performance bottlenecks (O(n^2) loops, N+1 database queries, memory leaks, missing indexes).
    
    CRITICAL CONSTRAINTS:
    - DO NOT comment on security vulnerabilities.
    - If no performance issues are found, return ISSUES_FOUND: NO.
    
    FEW-SHOT EXAMPLES:
    Example 1 (Input has SQL Injection):
    ISSUES_FOUND: NO
    
    Example 2 (Input has a loop inside a loop querying the DB):
    ISSUES_FOUND: YES
    AGENT: Performance
    TYPE: N+1 Query
    FILE: app/db.py
    LINE: 45
    REASONING: The code queries the database inside a for loop, creating an O(n^2) bottleneck.
    FIX: Use a `JOIN` or `select_related` to fetch the data in a single query.
    
    {base_format_instructions}
    """
    findings = await _call_agent(prompt, state["files_dict"], state["rag_context"])
    return {"performance_findings": findings}

async def style_agent(state: PRReviewState) -> PRReviewState:
    logger.info("Running Style Agent...")
    prompt = f"""
    You are a strictly specialized Code Quality and Style Engineer.
    Focus ONLY on PEP8 violations, missing type hints, poor variable naming, and readability issues.
    
    CRITICAL CONSTRAINTS:
    - DO NOT comment on security or performance.
    - If no style issues are found, return ISSUES_FOUND: NO.
    
    FEW-SHOT EXAMPLES:
    Example 1 (Input has SQL Injection):
    ISSUES_FOUND: NO
    
    Example 2 (Input uses a bare except clause `except:`):
    ISSUES_FOUND: YES
    AGENT: Style
    TYPE: Bare Except Clause
    FILE: app/api.py
    LINE: 22
    REASONING: Catching a bare Exception violates PEP8 and makes debugging hard.
    FIX: Catch a specific exception like `except ValueError:` instead.
    
    {base_format_instructions}
    """
    findings = await _call_agent(prompt, state["files_dict"], state["rag_context"])
    return {"style_findings": findings}

# -----------------------------------------------------------------
# FAN-IN AGENT (AGGREGATOR)
# -----------------------------------------------------------------

async def aggregator_agent(state: PRReviewState) -> PRReviewState:
    logger.info("Running Aggregator Agent...")
    
    all_findings = []
    all_findings.extend(state.get("security_findings", []))
    all_findings.extend(state.get("performance_findings", []))
    all_findings.extend(state.get("style_findings", []))
    
    if not all_findings:
        return {"final_findings": []}

    # Format findings for the aggregator LLM
    findings_text = ""
    for idx, f in enumerate(all_findings):
        findings_text += f"\nFinding {idx+1}:\nISSUES_FOUND: YES\nAGENT: {f.agent_category}\nTYPE: {f.vulnerability_type}\nFILE: {f.file_path}\nLINE: {f.line_number}\nREASONING: {f.internal_reasoning}\nFIX: {f.suggested_fix_comment}\n"

    prompt = f"""
    You are the Lead Aggregator Engineer. 
    Below is a list of code review findings generated by your junior specialist agents (Security, Performance, Style).
    Some of these agents disobeyed their instructions and reported issues outside their domain, causing duplicates.
    
    Your job is to:
    1. Remove duplicate findings (e.g., if Style and Security both reported SQLi, keep only the Security one).
    2. Keep ONLY the highest quality, most accurate findings.
    
    {base_format_instructions}
    
    Raw Findings:
    {findings_text}
    """
    
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model_name,
            temperature=0.0,
            messages=[
                {"role": "system", "content": "You are a code review aggregator. Output a clean, deduplicated list of findings based strictly on the user's provided list using the exact markdown format requested."},
                {"role": "user", "content": prompt}
            ]
        )
        
        raw_text = response.choices[0].message.content
        return {"final_findings": _parse_markdown_response(raw_text)}
    except Exception as e:
        logger.error(f"Aggregator processing failed: {str(e)}")
        # Fallback to returning all if the LLM fails
        return {"final_findings": all_findings}
