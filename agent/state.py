from typing import Annotated, Any, Optional, TypedDict, Union
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    instruction: str
    working_directory: str
    context: dict
    plan: list[Union[str, dict]]
    current_step: int
    file_buffer: dict[str, str]
    edit_history: list[dict]
    error_state: Optional[str]
    # Multi-agent coordination fields
    is_parallel: bool
    parallel_batches: list[list[int]]
    sequential_first: list[int]
    has_conflicts: bool
    model_usage: dict[str, int]
    autonomy_mode: str  # "supervised" | "autonomous"
    # ast-grep integration fields
    ast_available: dict[str, bool]
    invalidated_files: list[str]
