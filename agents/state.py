import operator
from typing import Annotated, List, TypedDict, Union
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """The state of the agent execution."""
    messages: Annotated[List[BaseMessage], operator.add]
    query: str
    relevant_docs: List[str]
    steps: List[str]
