from __future__ import annotations

from datetime import datetime, timedelta

from .models import PatientProfile, SessionState, TraceStep
from .storage import Storage


class MemoryService:
    def __init__(self, storage: Storage, session_ttl_seconds: int) -> None:
        self.storage = storage
        self.session_ttl = timedelta(seconds=session_ttl_seconds)
        self.session_cache: dict[str, tuple[SessionState, datetime]] = {}

    def get_or_create_session(self, patient_id: str) -> SessionState:
        now = datetime.utcnow()
        cached = self.session_cache.get(patient_id)
        if cached and now - cached[1] <= self.session_ttl:
            return cached[0]
        patient = self.storage.get_patient(patient_id)
        session = SessionState(
            patient_id=patient_id,
            language=patient.preferred_language if patient else "en",
            last_reason=patient.last_reason if patient else None,
        )
        self.session_cache[patient_id] = (session, now)
        return session

    def save_session(self, state: SessionState) -> None:
        self.session_cache[state.patient_id] = (state, datetime.utcnow())

    def add_trace(self, state: SessionState, stage: str, detail: str) -> None:
        state.trace.append(TraceStep(stage=stage, detail=detail))

    def build_context(self, patient_id: str) -> dict[str, object]:
        profile = self.storage.get_patient(patient_id)
        appointments = self.storage.list_appointments(patient_id)
        recent_interactions = self.storage.recent_interactions(patient_id)
        return {
            "profile": profile.model_dump() if profile else None,
            "appointments": [appointment.model_dump() for appointment in appointments],
            "recent_interactions": recent_interactions,
        }

    def persist_profile(self, patient_id: str, language: str, doctor_id: str | None, reason: str | None) -> PatientProfile:
        existing = self.storage.get_patient(patient_id) or PatientProfile(patient_id=patient_id, full_name=patient_id)
        existing.preferred_language = language
        existing.preferred_doctor = doctor_id or existing.preferred_doctor
        existing.last_reason = reason or existing.last_reason
        return self.storage.upsert_patient(existing)

