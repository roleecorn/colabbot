"""Protocol for activity-specific gift matching rules."""

from __future__ import annotations

from typing import Any, Protocol

from ..models import GiftAssignment, Participant


class GiftMatchingPolicy(Protocol):
    def generate(
        self,
        participants: list[Participant],
        blocked_edges: set[tuple[str, str]],
        config: dict[str, Any],
    ) -> list[GiftAssignment]: ...
