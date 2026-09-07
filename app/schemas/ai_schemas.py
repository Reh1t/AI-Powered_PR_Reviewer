from pydantic import BaseModel, Field
from enum import Enum
from typing import List

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ReviewFinding(BaseModel):
    file_path: str = Field(..., description="The path of the file containing the vulnerability or issue.")
    line_number: int = Field(..., description="The approximate line number where the issue occurs.")
    internal_reasoning: str = Field(..., description="Step-by-step analysis of why this specific line is an issue, and why it belongs strictly to your assigned domain.")
    vulnerability_type: str = Field(..., description="The category of the issue (e.g., XSS, SQLi, Logic Bug, OWASP Category).")
    severity: SeverityLevel = Field(..., description="The severity level of the vulnerability.")
    suggested_fix_comment: str = Field(..., description="A detailed markdown comment explaining the issue and suggesting a fix. Formatted for a GitHub PR review.")
    agent_category: str = Field(default="Aggregator", description="The agent that identified this issue (e.g., Security, Performance, Style).")

class ReviewResult(BaseModel):
    has_relevant_issues: bool = Field(..., description="Set to True ONLY if the code diff contains issues that strictly belong to your assigned domain.")
    findings: List[ReviewFinding] = Field(default_factory=list, description="A list of identified vulnerabilities and architectural flaws. Must be empty if has_relevant_issues is False.")
