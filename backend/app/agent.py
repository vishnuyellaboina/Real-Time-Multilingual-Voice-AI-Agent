from __future__ import annotations
from datetime import datetime, timedelta

from .campaigns import CampaignService
from .language import detect_language, render_text
from .latency import LatencyTracker
from .memory import MemoryService
from .models import AgentReply, SessionState, ToolCall, UserTurn
from .scheduler import SchedulerService
from .storage import Storage


class RealtimeVoiceAgent:
    def __init__(
        self,
        storage: Storage,
        memory: MemoryService,
        scheduler: SchedulerService,
        campaigns: CampaignService,
    ) -> None:
        self.storage = storage
        self.memory = memory
        self.scheduler = scheduler
        self.campaigns = campaigns

    def _extract_doctor(self, text: str, state: SessionState) -> str:
        lowered = text.lower()
        if "cardio" in lowered or "shah" in lowered:
            return "D200"
        if "diabetes" in lowered or "endo" in lowered or "lakshmi" in lowered:
            return "D300"
        if "general" in lowered or "iyer" in lowered:
            return "D100"
        return state.last_doctor_id or "D100"

    def _extract_reason(self, text: str, state: SessionState) -> str:
        lowered = text.lower()
        if "follow" in lowered:
            return "follow-up"
        if "cardio" in lowered or "heart" in lowered:
            return "cardiology review"
        if "diabetes" in lowered or "sugar" in lowered:
            return "diabetes consultation"
        return state.last_reason or "general consultation"

    def _extract_slot(self, text: str) -> datetime:
        now = datetime.utcnow().replace(second=0, microsecond=0)
        day_offset = 1
        if "today" in text.lower() or "आज" in text or "இன்று" in text:
            day_offset = 0
        if "day after" in text.lower():
            day_offset = 2
        base = (now + timedelta(days=day_offset)).replace(minute=0)
        if any(token in text.lower() for token in ["10", "ten", "morning", "सुबह", "காலை"]):
            return base.replace(hour=10)
        if any(token in text.lower() for token in ["2", "afternoon"]):
            return base.replace(hour=14)
        if any(token in text.lower() for token in ["4", "evening", "शाम", "மாலை"]):
            return base.replace(hour=16)
        return base.replace(hour=11)

    def _detect_intent(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ["cancel", "cancellation", "रद्द"]) or "ரத்து" in text:
            return "cancel"
        if any(word in lowered for word in ["reschedule", "move", "change", "बदल"]) or "மாற்ற" in text:
            return "reschedule"
        if any(word in lowered for word in ["book", "appointment", "schedule", "बुक"]) or "பதிவு" in text:
            return "book"
        if any(word in lowered for word in ["reminder", "confirm"]):
            return "reminder"
        return "unknown"

    def _format_slot(self, slot: datetime) -> str:
        return slot.strftime("%d %b %I:%M %p UTC")

    def _tool_lookup_patient(self, patient_id: str) -> dict[str, object]:
        return self.memory.build_context(patient_id)

    def process_turn(self, patient_id: str, turn: UserTurn) -> AgentReply:
        tracker = LatencyTracker()
        state = self.memory.get_or_create_session(patient_id)
        tracker.mark_dispatch()

        language = detect_language(turn.transcript, state.language)
        state.language = language
        intent = self._detect_intent(turn.transcript)
        state.active_intent = intent

        self.memory.add_trace(state, "language", f"Detected {language} from transcript.")
        self.memory.add_trace(state, "intent", f"Resolved user intent as {intent}.")

        tool_calls = [ToolCall(name="lookup_patient", arguments={"patient_id": patient_id}, rationale="Load cross-session memory and active appointments.")]
        patient_context = self._tool_lookup_patient(patient_id)
        self.memory.add_trace(
            state,
            "memory",
            f"Loaded {len(patient_context['appointments'])} active appointments and {len(patient_context['recent_interactions'])} recent interactions.",
        )

        tracker.mark_reasoning_done()

        reply_text = render_text(language, "fallback")
        data: dict[str, object] = {"context": patient_context}

        if intent == "book":
            doctor_id = self._extract_doctor(turn.transcript, state)
            slot = self._extract_slot(turn.transcript)
            reason = self._extract_reason(turn.transcript, state)
            tool_calls.append(
                ToolCall(
                    name="book_appointment",
                    arguments={"patient_id": patient_id, "doctor_id": doctor_id, "slot": slot.isoformat(), "reason": reason},
                    rationale="Attempt to create a valid appointment or produce alternatives.",
                )
            )
            result = self.scheduler.book(patient_id, doctor_id, slot, reason)
            state.last_doctor_id = doctor_id
            state.last_requested_slot = slot.isoformat()
            state.last_reason = reason
            if result.ok and result.appointment:
                reply_text = render_text(language, "booked", doctor=result.appointment.doctor_name, slot=self._format_slot(result.appointment.start_at))
                data["appointment"] = result.appointment.model_dump()
                self.memory.add_trace(state, "tool", f"Booked appointment {result.appointment.appointment_id}.")
            else:
                options = ", ".join(self._format_slot(item) for item in (result.alternatives or []))
                reply_text = render_text(language, "alternatives", options=options)
                data["alternatives"] = [item.isoformat() for item in (result.alternatives or [])]
                self.memory.add_trace(state, "tool", f"Booking rejected because {result.reason}.")
        elif intent == "reschedule":
            appointments = self.storage.list_appointments(patient_id)
            if not appointments:
                reply_text = render_text(language, "not_found")
            else:
                slot = self._extract_slot(turn.transcript)
                appointment = appointments[0]
                tool_calls.append(
                    ToolCall(
                        name="reschedule_appointment",
                        arguments={"appointment_id": appointment.appointment_id, "slot": slot.isoformat()},
                        rationale="Move the active appointment to a valid alternative slot.",
                    )
                )
                result = self.scheduler.reschedule(appointment.appointment_id, slot)
                if result.ok and result.appointment:
                    reply_text = render_text(language, "rescheduled", doctor=result.appointment.doctor_name, slot=self._format_slot(result.appointment.start_at))
                    data["appointment"] = result.appointment.model_dump()
                    self.memory.add_trace(state, "tool", f"Rescheduled appointment {appointment.appointment_id}.")
                else:
                    options = ", ".join(self._format_slot(item) for item in (result.alternatives or []))
                    reply_text = render_text(language, "alternatives", options=options)
        elif intent == "cancel":
            appointments = self.storage.list_appointments(patient_id)
            if not appointments:
                reply_text = render_text(language, "not_found")
            else:
                appointment = appointments[0]
                tool_calls.append(
                    ToolCall(
                        name="cancel_appointment",
                        arguments={"appointment_id": appointment.appointment_id},
                        rationale="Cancel the active appointment after user request.",
                    )
                )
                cancelled = self.scheduler.cancel(appointment.appointment_id)
                if cancelled:
                    reply_text = render_text(language, "cancelled", slot=self._format_slot(cancelled.start_at))
                    data["appointment"] = cancelled.model_dump()
                    self.memory.add_trace(state, "tool", f"Cancelled appointment {appointment.appointment_id}.")
        elif intent == "reminder" and turn.channel == "outbound":
            profile = self.storage.get_patient(patient_id)
            name = profile.full_name if profile else patient_id
            reply_text = render_text(language, "campaign_intro", name=name)
            tool_calls.append(
                ToolCall(
                    name="log_campaign_outcome",
                    arguments={"campaign_id": turn.campaign_id or "manual", "patient_id": patient_id, "status": "engaged"},
                    rationale="Record that the patient answered the reminder campaign.",
                )
            )
            data["campaign"] = self.campaigns.log_outcome(turn.campaign_id, patient_id, "engaged", "Patient answered reminder flow.")

        tracker.mark_tools_done()

        self.memory.persist_profile(patient_id, language, state.last_doctor_id, state.last_reason)
        self.storage.save_interaction(patient_id, turn.channel, language, turn.transcript, reply_text)
        self.memory.save_session(state)
        tracker.mark_render_done()

        return AgentReply(
            language=language,
            intent=intent,
            text=reply_text,
            trace=state.trace[-8:],
            tool_calls=tool_calls,
            latency=tracker.build(),
            state=state,
            data=data,
        )
