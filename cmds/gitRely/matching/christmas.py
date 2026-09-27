"""Monte Carlo matching policy for the Christmas event constraints."""

from __future__ import annotations

import random
from typing import Any

from ..models import GiftAssignment, Participant


class ChristmasGiftPolicy:
    def generate(
        self,
        participants: list[Participant],
        blocked_edges: set[tuple[str, str]],
        config: dict[str, Any],
    ) -> list[GiftAssignment]:
        ids = [participant.discord_user_id for participant in participants]
        if len(ids) < 2:
            raise ValueError("至少需要兩位有效報名者才能產生送禮配對。")
        attempts = int(config.get("max_attempts", 10000))
        if attempts < 1:
            raise ValueError("嘗試次數必須大於 0。")
        rng = random.SystemRandom()
        for _ in range(attempts):
            receivers = ids.copy()
            rng.shuffle(receivers)
            if any(
                giver == receiver or (giver, receiver) in blocked_edges
                for giver, receiver in zip(ids, receivers)
            ):
                continue
            return [
                GiftAssignment(giver_id=giver, receiver_id=receiver)
                for giver, receiver in zip(ids, receivers)
            ]
        raise ValueError(f"重骰 {attempts} 次仍無法產生合法配對。")
