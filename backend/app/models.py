from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


LanguageCode = Literal["en", "hi", "ta"]
IntentName = Literal["book", "reschedule", "cancel", "reminder", "unknown"]
ToolName = Literal[
    "lookup_patient",
    "find_appointments",
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "log_campaign_outcome",
]


class PatientProfile(BaseModel):
    patient_id: str
    full_name: str
    preferred_language: LanguageCode = "en"
    preferred_doctor: str | None = None
    preferred_time_of_day: str | None = None
    last_reason: str | None = None


class Appointment(BaseModel):
    appointment_id: str
    patient_id: str
    doctor_id: str
    doctor_name: str
    specialty: str
    start_at: datetime
    end_at: datetime
    reason: str
    status: Literal["booked", "cancelled"] = "booked"


class ToolCall(BaseModel):
    name: ToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str


class TraceStep(BaseModel):
    stage: str
    detail: str
    at: datetime = Field(default_factory=datetime.utcnow)


class LatencyBreakdown(BaseModel):
    speech_end_to_dispatch_ms: float
    reasoning_ms: float
    tool_ms: float
    response_render_ms: float
    total_ms: float


class SessionState(BaseModel):
    patient_id: str
    language: LanguageCode = "en"
    active_intent: IntentName = "unknown"
    pending_confirmation: dict[str, Any] | None = None
    last_doctor_id: str | None = None
    last_requested_slot: str | None = None
    last_reason: str | None = None
    trace: list[TraceStep] = Field(default_factory=list)


class UserTurn(BaseModel):
    transcript: str
    speech_ended_at: datetime = Field(default_factory=datetime.utcnow)
    channel: Literal["inbound", "outbound"] = "inbound"
    campaign_id: str | None = None


class AgentReply(BaseModel):
    language: LanguageCode
    intent: IntentName
    text: str
    trace: list[TraceStep]
    tool_calls: list[ToolCall]
    latency: LatencyBreakdown
    state: SessionState
    data: dict[str, Any] = Field(default_factory=dict)

