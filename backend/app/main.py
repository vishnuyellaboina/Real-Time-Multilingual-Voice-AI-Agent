from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agent import RealtimeVoiceAgent
from .campaigns import CampaignService
from .config import settings
from .memory import MemoryService
from .models import AgentReply, UserTurn
from .scheduler import SchedulerService
from .storage import Storage

storage = Storage(settings.database_path)
memory = MemoryService(storage, settings.session_ttl_seconds)
scheduler = SchedulerService(storage)
campaigns = CampaignService()
agent = RealtimeVoiceAgent(storage, memory, scheduler, campaigns)

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TurnRequest(BaseModel):
    patient_id: str
    transcript: str
    channel: str = "inbound"
    campaign_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/patients/{patient_id}/context")
def patient_context(patient_id: str) -> dict[str, object]:
    return memory.build_context(patient_id)


@app.post("/api/turn", response_model=AgentReply)
def process_turn(payload: TurnRequest) -> AgentReply:
    return agent.process_turn(
        patient_id=payload.patient_id,
        turn=UserTurn(transcript=payload.transcript, channel=payload.channel, campaign_id=payload.campaign_id),
    )


@app.get("/api/campaigns")
def list_campaign_events() -> list[dict[str, str]]:
    return campaigns.snapshot()


@app.websocket("/ws/session/{patient_id}")
async def session_socket(websocket: WebSocket, patient_id: str) -> None:
    await websocket.accept()
    while True:
        payload = await websocket.receive_json()
        turn = UserTurn(**payload)
        reply = agent.process_turn(patient_id=patient_id, turn=turn)
        await websocket.send_json(reply.model_dump(mode="json"))

