import logging
from langgraph.graph import StateGraph, END
from typing import Literal

from .agents import planner_node, search_node
from .agents import scrape_node, analyzer_node, synthesizer_node
from .models import AgentState

logger = logging.getLogger(__name__)


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


def should_retry_or_synthesize(state: AgentState) -> Literal["search", "synthesize"]:
    # The analyzer_node sets analysis_round = 0 to explicitly signal a retry
    if state.get("analysis_round", 1) == 0:
        logger.info(f"[WORKFLOW] Retry triggered, going back to search (retry #{state.get('retry_count', 1)})")
        return "search"
    return "synthesize"


def create_research_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("search", search_node)
    workflow.add_node("scrape", scrape_node)
    workflow.add_node("analyzer", analyzer_node)
    workflow.add_node("synthesize", synthesizer_node)

    workflow.set_entry_point("planner")

    workflow.add_edge("planner", "search")
    workflow.add_conditional_edges("search", should_skip_to_synthesize)
    workflow.add_conditional_edges("scrape", should_skip_to_synthesize_after_scrape)
    workflow.add_conditional_edges("analyzer", should_retry_or_synthesize)
    workflow.add_edge("synthesize", END)

    return workflow.compile()


research_graph = create_research_graph()