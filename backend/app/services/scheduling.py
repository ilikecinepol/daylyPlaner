from datetime import datetime, timedelta, timezone

from fastapi import HTTPException


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def normalize_schedule(values: dict, current=None) -> dict:
    """Normalize the calendar block while keeping its deadline independent."""
    patch = dict(values)
    provided = set(patch)
    if "due_at" in provided and "end_at" not in provided:
        patch["end_at"] = patch["due_at"]
        provided.add("end_at")
    patch.pop("due_at", None)

    def value(name, default=None):
        return patch[name] if name in patch else getattr(current, name, default)

    start = _aware(value("start_at"))
    end = _aware(value("end_at"))
    duration = value("duration_minutes", 60)
    all_day = bool(value("all_day", False))
    deadline = _aware(value("deadline_at"))

    if duration is None or duration < 0:
        raise HTTPException(422, "Продолжительность не может быть отрицательной")
    if end is not None and start is None:
        raise HTTPException(422, "Нельзя указать окончание без начала")

    if start is None or all_day:
        end = None
    elif "end_at" in provided:
        if end is None:
            end = start + timedelta(minutes=duration)
        elif end <= start:
            raise HTTPException(422, "Время окончания должно быть позже начала")
        else:
            duration = round((end - start).total_seconds() / 60)
    elif {"start_at", "duration_minutes", "all_day"} & provided or current is None:
        end = start + timedelta(minutes=duration)

    patch["start_at"] = start
    patch["end_at"] = end
    patch["duration_minutes"] = duration
    patch["deadline_at"] = deadline
    return patch


def is_overdue(task, now: datetime | None = None) -> bool:
    deadline = _aware(task.deadline_at)
    current = _aware(now) or datetime.now(timezone.utc)
    return bool(
        deadline
        and task.status not in ("completed", "cancelled")
        and task.completed_at is None
        and task.deleted_at is None
        and deadline < current
    )
