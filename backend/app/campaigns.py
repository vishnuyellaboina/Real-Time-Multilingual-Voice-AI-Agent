from __future__ import annotations

from datetime import datetime

from .models import AgentReply


class CampaignService:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def log_outcome(self, campaign_id: str | None, patient_id: str, status: str, detail: str) -> dict[str, str]:
        event = {
            "campaign_id": campaign_id or "manual",
            "patient_id": patient_id,
            "status": status,
            "detail": detail,
            "logged_at": datetime.utcnow().isoformat(),
        }
        self.events.append(event)
        return event

    def snapshot(self) -> list[dict[str, str]]:
        return list(self.events)

