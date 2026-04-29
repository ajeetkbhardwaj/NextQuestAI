import logging
from langgraph.graph import StateGraph, END
from typing import Literal

from .agents import router_node, planner_node, search_node
from .agents import scrape_node, analyzer_node, ranker_node, synthesizer_node, verifier_node
from .models import AgentState

logger = logging.getLogger(__name__)


def route_query(state: AgentState) -> Literal["planner", "synthesize"]:
    """Routes the query based on the router's decision."""
    next_step = state.get("next_step", "research")
    if next_step == "direct":
        logger.info("[WORKFLOW] Routing to direct answer (skipping research)")
        return "synthesize"
    return "planner"


def should_skip_to_synthesize(state: AgentState) -> Literal["scrape", "synthesize"]:
    if state.get("error"):
        logger.warning(f"Error detected in state, skipping to synthesize: {state['error']}")
        return "synthesize"
    if not state.get("search_results"):
        logger.warning("No search results, skipping to synthesize")
        return "synthesize"
    return "scrape"


def should_skip_to_synthesize_after_scrape(state: AgentState) -> Literal["analyzer", "synthesize"]:
    if state.get("error"):
        logger.warning(f"Error detected after scrape, skipping to synthesize")
        return "synthesize"
    if not state.get("scraped_content"):
        logger.warning("No scraped content, skipping analyzer")
        return "synthesize"
    return "analyzer"


def should_retry_or_rank(state: AgentState) -> Literal["search", "ranker"]:
    # The analyzer_node sets analysis_round = 0 to explicitly signal a retry
    if state.get("analysis_round", 1) == 0:
        logger.info(f"[WORKFLOW] Retry triggered, going back to search (retry #{state.get('retry_count', 1)})")
        return "search"
    return "ranker"


def create_research_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("search", search_node)
    workflow.add_node("scrape", scrape_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("ranker", ranker_node)
    workflow.add_node("synthesize", synthesizer_node)
    workflow.add_node("verifier", verifier_node)

    # Entry point is now the router
    workflow.set_entry_point("router")

    # Conditional routing after the router
    workflow.add_conditional_edges("router", route_query)

    workflow.add_edge("planner", "search")
    workflow.add_conditional_edges("search", should_skip_to_synthesize)
    workflow.add_conditional_edges("scrape", should_skip_to_synthesize_after_scrape)
    workflow.add_conditional_edges("analyzer", should_retry_or_rank)
    workflow.add_edge("ranker", "synthesize")
    workflow.add_edge("synthesize", "verifier")
    workflow.add_edge("verifier", END)

    return workflow.compile()


research_graph = create_research_graph()