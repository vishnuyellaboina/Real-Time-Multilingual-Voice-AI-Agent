from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import Appointment, PatientProfile


class Storage:
    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._init_schema()
        self._seed()

    def _init_schema(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS patients (
                patient_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                preferred_language TEXT NOT NULL,
                preferred_doctor TEXT,
                preferred_time_of_day TEXT,
                last_reason TEXT
            );
            CREATE TABLE IF NOT EXISTS appointments (
                appointment_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                doctor_name TEXT NOT NULL,
                specialty TEXT NOT NULL,
                start_at TEXT NOT NULL,
                end_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS interactions (
                interaction_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                language TEXT NOT NULL,
                transcript TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def _seed(self) -> None:
        count = self.connection.execute("SELECT COUNT(*) AS count FROM patients").fetchone()["count"]
        if count:
            return
        patients = [
            ("P1001", "Ananya Rao", "en", "D100", "evening", "follow-up"),
            ("P1002", "Ravi Kumar", "hi", "D200", "morning", "cardiology review"),
            ("P1003", "Meena Subramanian", "ta", "D300", "afternoon", "diabetes consultation"),
        ]
        self.connection.executemany(
            "INSERT INTO patients VALUES (?, ?, ?, ?, ?, ?)",
            patients,
        )
        tomorrow = datetime.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(days=1)
        seeded = [
            (
                str(uuid4()),
                "P1002",
                "D200",
                "Dr. Shah",
                "Cardiology",
                (tomorrow.replace(hour=10)).isoformat(),
                (tomorrow.replace(hour=10) + timedelta(minutes=30)).isoformat(),
                "cardiology review",
                "booked",
            ),
        ]
        self.connection.executemany(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            seeded,
        )
        self.connection.commit()

    def get_patient(self, patient_id: str) -> PatientProfile | None:
        row = self.connection.execute(
            "SELECT * FROM patients WHERE patient_id = ?",
            (patient_id,),
        ).fetchone()
        return PatientProfile(**dict(row)) if row else None

    def upsert_patient(self, profile: PatientProfile) -> PatientProfile:
        self.connection.execute(
            """
            INSERT INTO patients (patient_id, full_name, preferred_language, preferred_doctor, preferred_time_of_day, last_reason)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET
                full_name = excluded.full_name,
                preferred_language = excluded.preferred_language,
                preferred_doctor = excluded.preferred_doctor,
                preferred_time_of_day = excluded.preferred_time_of_day,
                last_reason = excluded.last_reason
            """,
            (
                profile.patient_id,
                profile.full_name,
                profile.preferred_language,
                profile.preferred_doctor,
                profile.preferred_time_of_day,
                profile.last_reason,
            ),
        )
        self.connection.commit()
        return profile

    def list_appointments(self, patient_id: str, active_only: bool = True) -> list[Appointment]:
        query = "SELECT * FROM appointments WHERE patient_id = ?"
        params: list[Any] = [patient_id]
        if active_only:
            query += " AND status = 'booked'"
        rows = self.connection.execute(query, params).fetchall()
        return [Appointment(**dict(row)) for row in rows]

    def find_appointment(self, appointment_id: str) -> Appointment | None:
        row = self.connection.execute(
            "SELECT * FROM appointments WHERE appointment_id = ?",
            (appointment_id,),
        ).fetchone()
        return Appointment(**dict(row)) if row else None

    def create_appointment(self, appointment: Appointment) -> Appointment:
        self.connection.execute(
            "INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                appointment.appointment_id,
                appointment.patient_id,
                appointment.doctor_id,
                appointment.doctor_name,
                appointment.specialty,
                appointment.start_at.isoformat(),
                appointment.end_at.isoformat(),
                appointment.reason,
                appointment.status,
            ),
        )
        self.connection.commit()
        return appointment

    def update_appointment(self, appointment: Appointment) -> Appointment:
        self.connection.execute(
            """
            UPDATE appointments
            SET patient_id = ?, doctor_id = ?, doctor_name = ?, specialty = ?, start_at = ?, end_at = ?, reason = ?, status = ?
            WHERE appointment_id = ?
            """,
            (
                appointment.patient_id,
                appointment.doctor_id,
                appointment.doctor_name,
                appointment.specialty,
                appointment.start_at.isoformat(),
                appointment.end_at.isoformat(),
                appointment.reason,
                appointment.status,
                appointment.appointment_id,
            ),
        )
        self.connection.commit()
        return appointment

    def save_interaction(
        self,
        patient_id: str,
        channel: str,
        language: str,
        transcript: str,
        response: str,
    ) -> None:
        self.connection.execute(
            "INSERT INTO interactions VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                patient_id,
                channel,
                language,
                transcript,
                response,
                datetime.utcnow().isoformat(),
            ),
        )
        self.connection.commit()

    def recent_interactions(self, patient_id: str, limit: int = 5) -> list[dict[str, str]]:
        rows = self.connection.execute(
            """
            SELECT channel, language, transcript, response, created_at
            FROM interactions
            WHERE patient_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (patient_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

