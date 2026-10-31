from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..api.dependencies import current_user, iso_utc
from ..database import get_db
from ..models import CraceProfile, CraceWorkout
from ..modules import require_module


router = APIRouter(prefix="/api/v1/crace", tags=["crace"], dependencies=[Depends(require_module("crace"))])
RACE_DATE = date(2026, 12, 5)
PLAN_KEYS = {"baseline", *(f"w{number:02d}" for number in range(2, 12)), "race"}


class ProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weight_kg: Decimal | None = Field(default=None, ge=35, le=250, max_digits=6, decimal_places=2)
    max_hr: int = Field(default=190, ge=100, le=230)


class SessionStatusIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed: bool


class HeartRateSample(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: float = Field(ge=0, le=21600)
    hr: int = Field(ge=30, le=250)
    phase: str = Field(default="run", pattern="^(run|station)$")


class WorkoutLap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    seconds: float = Field(ge=0, le=21600)


class WorkoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_key: str | None = Field(default=None, max_length=40)
    title: str = Field(min_length=1, max_length=300)
    started_at: datetime | None = None
    duration_sec: int = Field(ge=0, le=21600)
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str = Field(default="", max_length=4000)
    samples: list[HeartRateSample] = Field(default_factory=list, max_length=21600)
    laps: list[WorkoutLap] = Field(default_factory=list, max_length=100)


def get_or_create_profile(db: Session, user_id: str) -> CraceProfile:
    profile = db.scalar(select(CraceProfile).where(CraceProfile.user_id == user_id))
    if profile is None:
        profile = CraceProfile(
            user_id=user_id,
            race_date=RACE_DATE,
            max_hr=190,
            completed_sessions={"baseline": True},
        )
        db.add(profile)
        db.flush()
    return profile


def workout_out(workout: CraceWorkout) -> dict:
    return {
        "id": workout.id,
        "plan_key": workout.plan_key,
        "title": workout.title,
        "started_at": iso_utc(workout.started_at),
        "duration_sec": workout.duration_sec,
        "avg_hr": workout.avg_hr,
        "max_hr": workout.max_hr,
        "rpe": workout.rpe,
        "notes": workout.notes,
        "samples": workout.samples or [],
        "laps": workout.laps or [],
    }


def payload(db: Session, user_id: str) -> dict:
    profile = get_or_create_profile(db, user_id)
    workouts = list(db.scalars(
        select(CraceWorkout)
        .where(CraceWorkout.user_id == user_id)
        .order_by(CraceWorkout.started_at.desc())
        .limit(50)
    ))
    return {
        "profile": {
            "weight_kg": str(profile.weight_kg) if profile.weight_kg is not None else None,
            "max_hr": profile.max_hr,
            "race_date": profile.race_date.isoformat(),
        },
        "completed_sessions": profile.completed_sessions or {"baseline": True},
        "workouts": [workout_out(item) for item in workouts],
    }


@router.get("")
def get_crace_state(user=Depends(current_user), db: Session = Depends(get_db)):
    result = payload(db, user.id)
    db.commit()
    return result


@router.put("/profile")
def update_profile(data: ProfileIn, user=Depends(current_user), db: Session = Depends(get_db)):
    profile = get_or_create_profile(db, user.id)
    profile.weight_kg = data.weight_kg
    profile.max_hr = data.max_hr
    db.commit()
    return payload(db, user.id)["profile"]


@router.put("/sessions/{plan_key}")
def update_session(plan_key: str, data: SessionStatusIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if plan_key not in PLAN_KEYS:
        raise HTTPException(404, "Тренировка плана не найдена")
    profile = get_or_create_profile(db, user.id)
    completed = dict(profile.completed_sessions or {})
    completed[plan_key] = data.completed
    profile.completed_sessions = completed
    db.commit()
    return {"plan_key": plan_key, "completed": data.completed}


@router.post("/workouts", status_code=201)
def create_workout(data: WorkoutIn, user=Depends(current_user), db: Session = Depends(get_db)):
    if data.plan_key is not None and data.plan_key not in PLAN_KEYS:
        raise HTTPException(422, "Неизвестная тренировка плана")
    samples = [sample.model_dump() for sample in data.samples]
    heart_rates = [sample["hr"] for sample in samples]
    workout = CraceWorkout(
        user_id=user.id,
        plan_key=data.plan_key,
        title=data.title,
        started_at=data.started_at or datetime.now(timezone.utc),
        duration_sec=data.duration_sec,
        avg_hr=round(sum(heart_rates) / len(heart_rates)) if heart_rates else None,
        max_hr=max(heart_rates) if heart_rates else None,
        rpe=data.rpe,
        notes=data.notes,
        samples=samples,
        laps=[lap.model_dump() for lap in data.laps],
    )
    db.add(workout)
    if data.plan_key:
        profile = get_or_create_profile(db, user.id)
        completed = dict(profile.completed_sessions or {})
        completed[data.plan_key] = True
        profile.completed_sessions = completed
    db.commit()
    db.refresh(workout)
    return workout_out(workout)


@router.delete("/workouts/{workout_id}", status_code=204)
def delete_workout(workout_id: str, user=Depends(current_user), db: Session = Depends(get_db)):
    workout = db.get(CraceWorkout, workout_id)
    if workout is None or workout.user_id != user.id:
        raise HTTPException(404, "Тренировка не найдена")
    db.delete(workout)
    db.commit()
    return Response(status_code=204)
