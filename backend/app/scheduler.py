from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from .models import Appointment
from .storage import Storage


DOCTORS = {
    "D100": {"doctor_name": "Dr. Iyer", "specialty": "General Medicine"},
    "D200": {"doctor_name": "Dr. Shah", "specialty": "Cardiology"},
    "D300": {"doctor_name": "Dr. Lakshmi", "specialty": "Endocrinology"},
}


@dataclass
class BookingResult:
    ok: bool
    appointment: Appointment | None = None
    alternatives: list[datetime] | None = None
    reason: str | None = None


class SchedulerService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def _slot_conflicts(self, doctor_id: str, slot: datetime, exclude_appointment_id: str | None = None) -> bool:
        end_at = slot + timedelta(minutes=30)
        query = """
            SELECT COUNT(*) AS count
            FROM appointments
            WHERE doctor_id = ? AND status = 'booked'
              AND NOT (end_at <= ? OR start_at >= ?)
        """
        params: list[str] = [doctor_id, slot.isoformat(), end_at.isoformat()]
        if exclude_appointment_id:
            query += " AND appointment_id != ?"
            params.append(exclude_appointment_id)
        rows = self.storage.connection.execute(query, params).fetchone()
        return bool(rows["count"])

    def offer_alternatives(self, doctor_id: str, preferred_slot: datetime, count: int = 3) -> list[datetime]:
        options: list[datetime] = []
        cursor = preferred_slot
        while len(options) < count:
            cursor += timedelta(minutes=30)
            if cursor.hour < 9 or cursor.hour >= 18:
                cursor = (cursor + timedelta(days=1)).replace(hour=9, minute=0)
            if cursor <= datetime.utcnow():
                continue
            if not self._slot_conflicts(doctor_id, cursor):
                options.append(cursor)
        return options

    def book(self, patient_id: str, doctor_id: str, slot: datetime, reason: str) -> BookingResult:
        if slot <= datetime.utcnow():
            return BookingResult(ok=False, reason="past-time", alternatives=self.offer_alternatives(doctor_id, datetime.utcnow()))
        if doctor_id not in DOCTORS:
            fallback_doctor_id = "D100"
            return BookingResult(
                ok=False,
                reason="unknown-doctor",
                alternatives=self.offer_alternatives(fallback_doctor_id, slot),
            )
        if self._slot_conflicts(doctor_id, slot):
            return BookingResult(ok=False, reason="slot-conflict", alternatives=self.offer_alternatives(doctor_id, slot))
        doctor = DOCTORS[doctor_id]
        appointment = Appointment(
            appointment_id=str(uuid4()),
            patient_id=patient_id,
            doctor_id=doctor_id,
            doctor_name=doctor["doctor_name"],
            specialty=doctor["specialty"],
            start_at=slot,
            end_at=slot + timedelta(minutes=30),
            reason=reason,
            status="booked",
        )
        return BookingResult(ok=True, appointment=self.storage.create_appointment(appointment))

    def reschedule(self, appointment_id: str, new_slot: datetime) -> BookingResult:
        appointment = self.storage.find_appointment(appointment_id)
        if not appointment:
            return BookingResult(ok=False, reason="appointment-not-found")
        if self._slot_conflicts(appointment.doctor_id, new_slot, exclude_appointment_id=appointment.appointment_id):
            return BookingResult(
                ok=False,
                reason="slot-conflict",
                alternatives=self.offer_alternatives(appointment.doctor_id, new_slot),
            )
        appointment.start_at = new_slot
        appointment.end_at = new_slot + timedelta(minutes=30)
        return BookingResult(ok=True, appointment=self.storage.update_appointment(appointment))

    def cancel(self, appointment_id: str) -> Appointment | None:
        appointment = self.storage.find_appointment(appointment_id)
        if not appointment:
            return None
        appointment.status = "cancelled"
        return self.storage.update_appointment(appointment)
