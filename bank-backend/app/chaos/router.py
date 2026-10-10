from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class ChaosSettings(BaseModel):
    latency_ms: int = Field(default=0, ge=0)
    error_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    drop_response: bool = False
    down: bool = False


# In-memory chaos state
current_chaos = ChaosSettings()


@router.get("", response_model=ChaosSettings, summary="Get current chaos simulation settings")
async def get_chaos():
    return current_chaos


@router.post("", response_model=ChaosSettings, summary="Update chaos simulation settings")
async def update_chaos(settings: ChaosSettings):
    global current_chaos
    current_chaos = settings
    return current_chaos

