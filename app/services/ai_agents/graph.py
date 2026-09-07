from langgraph.graph import StateGraph, START, END
from app.services.ai_agents.state import PRReviewState
from app.services.ai_agents.nodes import security_agent, performance_agent, style_agent, aggregator_agent

def create_review_graph() -> StateGraph:
    """
    Constructs the LangGraph workflow for PR Reviews.
    Runs Sequentially to preserve VRAM on local hardware:
    START -> Security -> Performance -> Style -> Aggregator -> END
    """
    graph = StateGraph(PRReviewState)
    
    # Add nodes
    graph.add_node("security_agent", security_agent)
    graph.add_node("performance_agent", performance_agent)
    graph.add_node("style_agent", style_agent)
    graph.add_node("aggregator_agent", aggregator_agent)
    
    # Sequential Pipeline
    graph.add_edge(START, "security_agent")
    graph.add_edge("security_agent", "performance_agent")
    graph.add_edge("performance_agent", "style_agent")
    graph.add_edge("style_agent", "aggregator_agent")
    graph.add_edge("aggregator_agent", END)
    
    return graph.compile()

# Compile a singleton instance of the graph
pr_review_graph = create_review_graph()
