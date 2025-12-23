import os

from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig

# NEW IMPORTS FOR LOCAL MODELS
from langchain_ollama import ChatOllama
# Browser-based search using Playwright
from agent.browser_search import search_google

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from agent.utils import (
    get_research_topic,
)

load_dotenv()

# Helper to get Ollama LLM
def get_ollama_llm(model_name: str, config: RunnableConfig):
    # Strip any specific configuration if needed, or pass directly
    # 'model_name' comes from our config 
    return ChatOllama(
        model=model_name,
        temperature=0,
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )

# Nodes
def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """LangGraph node that generates search queries based on the User's question."""
    configurable = Configuration.from_runnable_config(config)
    
    # Use the model from state (sent by frontend) with hardcoded fallback
    # This bypasses any cached LangGraph assistant configuration
    model_to_use = state.get("reasoning_model") or "llama3.1"
    
    print(f"[DEBUG generate_query] USING model = {model_to_use}")

    # check for custom initial search query count
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    # init Ollama with the correct model
    llm = get_ollama_llm(model_to_use, config)
    structured_llm = llm.with_structured_output(SearchQueryList)

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    
    # Generate the search queries
    result = structured_llm.invoke(formatted_prompt)
    return {"search_query": result.query}


def continue_to_web_research(state: OverallState):
    """LangGraph node that sends the search queries to the web research node."""
    deep_research = state.get("deep_research", False)
    reasoning_model = state.get("reasoning_model", "llama3.1")
    return [
        Send("web_research", {
            "search_query": search_query, 
            "id": int(idx),
            "deep_research": deep_research,
            "reasoning_model": reasoning_model,
        })
        for idx, search_query in enumerate(state["search_query"])
    ]


def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research with full page content extraction."""
    
    deep_research = state.get("deep_research", False)
    reasoning_model = state.get("reasoning_model", "llama3.1")
    
    try:
        # Execute search with full page content extraction
        mode = "DEEP RESEARCH" if deep_research else "Standard"
        print(f"[Web Research] [{mode}] Searching for: {state['search_query']}")
        results = search_google(
            state["search_query"], 
            max_results=5, 
            deep_research=deep_research,
            model=reasoning_model
        )
        
        # Format results with full content when available
        formatted_results = []
        sources = []
        for r in results:
            # Use full_content if available, otherwise fall back to snippet
            content = r.get('full_content', r.get('snippet', 'N/A'))
            
            formatted_results.append(
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL: {r.get('url', 'N/A')}\n"
                f"Content: {content}"
            )
            if r.get('url'):
                sources.append({"url": r.get('url'), "title": r.get('title', '')})
        
        search_results = "\n\n---\n\n".join(formatted_results) if formatted_results else "No results found."
        print(f"[Web Research] Found {len(results)} results with content")
    except Exception as e:
        print(f"[Web Research] Error: {str(e)}")
        search_results = f"Search failed: {str(e)}. Please try again."
        sources = []
    
    return {
        "sources_gathered": sources,
        "search_query": [state["search_query"]],
        "web_research_result": [f"Search Query: {state['search_query']}\nResults:\n{search_results}"],
    }


def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates potential follow-up queries."""
    configurable = Configuration.from_runnable_config(config)
    # Increment the research loop count
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    
    # Use the model from state with hardcoded fallback
    reasoning_model = state.get("reasoning_model") or "llama3.1"

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    
    # init Reasoning Model
    llm = get_ollama_llm(reasoning_model, config)
    result = llm.with_structured_output(Reflection).invoke(formatted_prompt)

    return {
        "is_sufficient": result.is_sufficient,
        "knowledge_gap": result.knowledge_gap,
        "follow_up_queries": result.follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(state: ReflectionState, config: RunnableConfig) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow."""
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    if state["is_sufficient"] or state["research_loop_count"] >= max_research_loops:
        return "finalize_answer"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the research summary."""
    # Use the model from state with hardcoded fallback
    reasoning_model = state.get("reasoning_model") or "llama3.1"

    # Format the prompt
    current_date = get_current_date()
    formatted_prompt = answer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n---\n\n".join(state["web_research_result"]),
    )

    # init Reasoning Model
    llm = get_ollama_llm(reasoning_model, config)
    result = llm.invoke(formatted_prompt)

    return {
        "messages": [AIMessage(content=result.content)],
        "sources_gathered": [],
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
builder.add_edge(START, "generate_query")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_query", continue_to_web_research, ["web_research"]
)
# Reflect on the web research
builder.add_edge("web_research", "reflection")
# Evaluate the research
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "finalize_answer"]
)
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")
