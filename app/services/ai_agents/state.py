from typing import TypedDict, List, Dict
from app.schemas.ai_schemas import ReviewFinding

class PRReviewState(TypedDict):
    """
    The State object passed through the LangGraph workflow.
    """
    files_dict: Dict[str, str]       # The git diffs being reviewed (filename -> patch)
    rag_context: str                 # Historical context from pgvector
    
    # Outputs from Fan-Out Agents
    security_findings: List[ReviewFinding]
    performance_findings: List[ReviewFinding]
    style_findings: List[ReviewFinding]
    
    # Output from the Aggregator Agent (Fan-In)
    final_findings: List[ReviewFinding]
