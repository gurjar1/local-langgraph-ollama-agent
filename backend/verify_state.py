from agent.state import OverallState
from typing_extensions import is_typeddict
import sys

print(f"OverallState is TypedDict: {is_typeddict(OverallState)}")

try:
    from langgraph.graph import StateGraph
    graph = StateGraph(OverallState)
    print("StateGraph initialized successfully")
except Exception as e:
    print(f"StateGraph failed: {e}")
    sys.exit(1)
