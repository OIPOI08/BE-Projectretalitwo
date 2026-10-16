
from datetime import date, datetime, time
from typing import Any, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class KloterCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str = "aktif"


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=30,
        pattern=r"^[A-Za-z0-9_]{3,30}$",
    )
    full_name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
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
    status: str = "pending"
    priority: str = "normal"
    due_date: date | None = None


class TaskStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1, max_length=50)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
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


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class VerifyResetOTPRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    otp: str = Field(pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    reset_token: str = Field(min_length=32, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)


# ==========================================
# TUGAS CEKLIS
# ==========================================

class ChecklistTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    opens_at: datetime
    closes_at: datetime

    @model_validator(mode="after")
    def validate_schedule(self):
        if (
            self.opens_at.tzinfo is None
            or self.closes_at.tzinfo is None
        ):
            raise ValueError(
                "Waktu buka dan tutup harus menyertakan timezone."
            )

        if self.closes_at <= self.opens_at:
            raise ValueError(
                "Waktu tutup harus setelah waktu buka."
            )

        return self


class ChecklistTaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    description: str | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    status: Literal[
        "draft",
        "published",
        "archived",
    ] | None = None


class ChecklistQuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str = Field(
        min_length=1,
        max_length=1000,
    )
    answer_type: Literal[
        "text",
        "yes_no",
        "number",
        "single_choice",
        "multiple_choice",
    ] = "text"
    options: list[str] | None = None
    is_required: bool = True
    sort_order: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_options(self):
        if self.answer_type in (
            "single_choice",
            "multiple_choice",
        ):
            if not self.options:
                raise ValueError(
                    "Soal pilihan harus memiliki daftar options."
                )

            normalized = [
                option.strip()
                for option in self.options
            ]

            if any(not option for option in normalized):
                raise ValueError(
                    "Pilihan jawaban tidak boleh kosong."
                )

            if len(set(normalized)) != len(normalized):
                raise ValueError(
                    "Pilihan jawaban tidak boleh duplikat."
                )

            self.options = normalized

        return self


class ChecklistRecipientsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_ids: list[UUID] = Field(min_length=1)


class ChecklistAnswerCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: UUID
    answer: Any

# =====================================================
# ITINERARY SCHEMAS
# =====================================================

class ItineraryActivityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    activity_time: time | None = None
    description: str | None = None
    location: str | None = None


class ItineraryDayInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    activity_date: date
    title: str | None = Field(default=None, max_length=200)
    activities: list[ItineraryActivityInput] = Field(
        default_factory=list
    )


class ItineraryRecipientInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_role: Literal["tour_leader", "muthawif"]
    recipient_mode: Literal["all", "selected"]
    profile_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_recipients(self):
        if len(set(self.profile_ids)) != len(self.profile_ids):
            raise ValueError("ID penerima tidak boleh duplikat.")

        if self.recipient_mode == "all" and self.profile_ids:
            raise ValueError(
                "Mode all tidak boleh berisi profile_ids."
            )

        if self.recipient_mode == "selected" and not self.profile_ids:
            raise ValueError(
                "Mode selected harus memiliki minimal satu penerima."
            )

        return self


class ItineraryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date

    # Hari itinerary dibuat otomatis dari periode.
    # Field days dipakai untuk mengisi judul hari dan kegiatannya.
    days: list[ItineraryDayInput] = Field(default_factory=list)

    # Bisa mengatur Tour Leader, Muthawif, atau keduanya.
    recipients: list[ItineraryRecipientInput] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_itinerary(self):
        self.title = self.title.strip()

        if not self.title:
            raise ValueError("Judul itinerary tidak boleh kosong.")

        if self.end_date < self.start_date:
            raise ValueError(
                "Tanggal selesai harus sama dengan atau setelah tanggal mulai."
            )

        activity_dates = [
            day.activity_date for day in self.days
        ]

        if len(activity_dates) != len(set(activity_dates)):
            raise ValueError(
                "Tanggal hari itinerary tidak boleh duplikat."
            )

        for day in self.days:
            if not (
                self.start_date
                <= day.activity_date
                <= self.end_date
            ):
                raise ValueError(
                    "Tanggal kegiatan harus berada dalam periode itinerary."
                )

        roles = [
            recipient.recipient_role
            for recipient in self.recipients
        ]

        if len(roles) != len(set(roles)):
            raise ValueError(
                "Aturan penerima untuk setiap role hanya boleh satu."
            )

        return self


class ItineraryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )
    status: Literal["draft", "published", "archived"] | None = None