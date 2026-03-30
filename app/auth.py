from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ActorContext:
    email: str
    display_name: str
    auth_provider: str

