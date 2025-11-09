from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.deps import get_db
from app import models
from app.services.email_service import EmailService
from app.config import settings
import telnyx

router = APIRouter(prefix="/appointments", tags=["appointments"])
telnyx.api_key = getattr(settings, "TELNYX_API_KEY", None)


# ---------- Schemas ----------
class AppointmentCreate(BaseModel):
    customer_name: str = Field(..., min_length=2)
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    starts_at: datetime
    duration_minutes: int = Field(30, ge=5, le=480)
    timezone: str = "America/New_York"
    notes: Optional[str] = None
    send_confirmations: bool = True
    remind_minutes_before: Optional[int] = 30


class AppointmentOut(BaseModel):
    id: int
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    starts_at: datetime
    duration_minutes: int
    timezone: str
    status: str
    notes: Optional[str]

    class Config:
        from_attributes = True


class AppointmentUpdate(BaseModel):
    starts_at: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=5, le=480)
    timezone: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


# ---------- Helpers ----------
def _send_sms(to: str, text: str):
    """Send an SMS using Telnyx (if configured)."""
    if not telnyx.api_key or not getattr(settings, "TELNYX_FROM_NUMBER", None):
        return
    try:
        telnyx.Message.create(
            from_=settings.TELNYX_FROM_NUMBER,
            to=to,
            text=text,
            messaging_profile_id=settings.TELNYX_MESSAGING_PROFILE_ID,
        )
    except Exception as e:
        print("SMS send error:", e)


def _send_email(to_email: str, subject: str, html: str):
    """Send an email using SendGrid (if configured)."""
    if not getattr(settings, "SENDGRID_API_KEY", None):
        return
    try:
        EmailService.send_email(to_email, subject, html)
    except Exception as e:
        print("Email send error:", e)


# ---------- Routes ----------
@router.post("/", response_model=AppointmentOut)
def create_appointment(
    body: AppointmentCreate,
    bg: BackgroundTasks,
    db: Session = Depends(get_db),
):
    appt = models.Appointment(
        customer_name=body.customer_name,
        customer_email=body.customer_email,
        customer_phone=body.customer_phone,
        starts_at=body.starts_at,
        duration_minutes=body.duration_minutes,
        timezone=body.timezone,
        notes=body.notes,
        status="pending",
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)

    # Confirmation notifications
    if body.send_confirmations:
        msg = f"Hi {body.customer_name}, your appointment is scheduled for {body.starts_at.strftime('%Y-%m-%d %H:%M %Z')}."
        if body.customer_phone:
            bg.add_task(_send_sms, body.customer_phone, msg)
        if body.customer_email:
            bg.add_task(_send_email, body.customer_email, "Appointment Confirmation", f"<p>{msg}</p>")

    # Reminder notification
    if body.remind_minutes_before and body.customer_phone:
        delay = (body.starts_at - timedelta(minutes=body.remind_minutes_before) - datetime.utcnow()).total_seconds()
        if delay > 0:
            bg.add_task(_send_sms, body.customer_phone, f"Reminder: appointment at {body.starts_at.strftime('%Y-%m-%d %H:%M %Z')}")

    return appt


@router.get("/", response_model=List[AppointmentOut])
def list_appointments(db: Session = Depends(get_db)):
    return db.query(models.Appointment).order_by(models.Appointment.starts_at.desc()).all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")
    return appt


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(appointment_id: int, body: AppointmentUpdate, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")

    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(appt, key, value)

    db.commit()
    db.refresh(appt)
    return appt


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")

    appt.status = "confirmed"
    db.commit()
    db.refresh(appt)

    msg = f"Hi {appt.customer_name}, your appointment is confirmed for {appt.starts_at.strftime('%Y-%m-%d %H:%M %Z')}."
    if appt.customer_phone:
        _send_sms(appt.customer_phone, msg)
    if appt.customer_email:
        _send_email(appt.customer_email, "Appointment Confirmed", f"<p>{msg}</p>")

    return appt


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db)):
    appt = db.get(models.Appointment, appointment_id)
    if not appt:
        raise HTTPException(404, "Appointment not found")

    appt.status = "cancelled"
    db.commit()
    db.refresh(appt)

    msg = f"Hi {appt.customer_name}, your appointment on {appt.starts_at.strftime('%Y-%m-%d %H:%M %Z')} has been cancelled."
    if appt.customer_phone:
        _send_sms(appt.customer_phone, msg)
    if appt.customer_email:
        _send_email(appt.customer_email, "Appointment Cancelled", f"<p>{msg}</p>")

    return appt
