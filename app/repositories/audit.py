from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditEvent, User
from app.models.enums import AuditEventType


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        *,
        event_type: AuditEventType,
        entity_type: str,
        entity_id: str,
        payload_json: dict,
        actor: User | None = None,
        actor_email: str | None = None,
        actor_display_name: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_user_id=actor.id if actor else None,
            actor_email=actor_email or (actor.email if actor else None),
            actor_display_name=actor_display_name or (actor.display_name if actor else None),
            payload_json=payload_json,
        )
        self.session.add(event)
        self.session.flush()
        return event

