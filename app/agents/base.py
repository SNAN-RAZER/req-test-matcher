from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from app.models import AgentTrace


@dataclass
class Blackboard:
    """Shared swarm memory. All agents read/write here; nothing leaves the process."""

    req_paths: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=list)
    req_docs: list[Any] = field(default_factory=list)
    test_docs: list[Any] = field(default_factory=list)
    table_text: dict[str, str] = field(default_factory=dict)
    semantic_text: dict[str, str] = field(default_factory=dict)
    vision_text: dict[str, str] = field(default_factory=dict)
    requirements: list[Any] = field(default_factory=list)
    test_cases: list[Any] = field(default_factory=list)
    collection: str = ""
    kg: Any = None
    matches: list[Any] = field(default_factory=list)
    report: Any = None
    traces: list[AgentTrace] = field(default_factory=list)
    on_log: Callable[[dict[str, Any]], None] | None = None

    def log(self, agent: str, role: str, action: str, detail: str = "") -> None:
        self.traces.append(AgentTrace(agent=agent, role=role, action=action, detail=detail[:800]))
        if self.on_log:
            self.on_log({"type": "log", "agent": agent, "role": role, "action": action, "detail": detail[:400]})


class Agent(Protocol):
    name: str
    role: str

    def run(self, board: Blackboard) -> None: ...
