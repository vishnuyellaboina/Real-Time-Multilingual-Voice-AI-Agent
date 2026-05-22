from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "2care Voice Agent"
    database_path: Path = Path("data/agent.db")
    session_ttl_seconds: int = 1800
    response_latency_target_ms: int = 450
    clinic_open_hour: int = 9
    clinic_close_hour: int = 18


settings = Settings()

