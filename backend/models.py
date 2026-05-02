from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import uuid


class JobSubmit(BaseModel):
    name: str
    image: str = "nvcr.io/nvidia/pytorch:24.01-py3"
    command: str
    env: dict[str, str] = {}
    gpu_count: int = Field(default=1, ge=0, le=1)


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    image: str
    command: str
    env: dict[str, str] = {}
    gpu_count: int = 1
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    exit_code: Optional[int] = None
    log_output: Optional[str] = None
    pod_name: Optional[str] = None
    owner: str = "default"


class UserCreate(BaseModel):
    username: str
    password: str


class User(BaseModel):
    username: str
    disabled: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
