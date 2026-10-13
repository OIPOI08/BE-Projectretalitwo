
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class KloterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "aktif"


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = Field(default=None, min_length=1)
    email: str | None = None
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AttendanceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    type: str = Field(min_length=1)
    note: str | None = None


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str | None = None
    assigned_to: str | None = None
    kloter_id: str | None = None
    status: str = "belum"
    priority: str = "sedang"
    due_date: date | None = None


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1)
    password: str = Field(min_length=1)


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    user_id: str | None = None
    type: str = "info"


class ScanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    scan_type: str = "masuk"
    location: str | None = None
