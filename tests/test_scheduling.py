from contextlib import contextmanager
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.main import app
from app.models import ActivityLog, Task
from app.services.deadlines import process_deadlines


@contextmanager
def registered_client(email="schedule@example.com"):
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "StrongPass123", "name": "Schedule"},
        )
        assert response.status_code == 201
        yield client


def test_start_and_duration_calculate_end():
    with registered_client("duration@example.com") as client:
        task = client.post(
            "/api/v1/tasks",
            json={
                "title": "Duration",
                "start_at": "2030-01-10T10:00:00Z",
                "duration_minutes": 90,
            },
        ).json()
        assert task["end_at"] == "2030-01-10T11:30:00Z"
        assert task["due_at"] == task["end_at"]  # temporary legacy alias
        assert task["duration_minutes"] == 90


def test_start_and_end_calculate_duration():
    with registered_client("end@example.com") as client:
        task = client.post(
            "/api/v1/tasks",
            json={
                "title": "Explicit end",
                "start_at": "2030-01-10T10:00:00Z",
                "end_at": "2030-01-10T12:15:00Z",
                "duration_minutes": 30,
            },
        ).json()
        assert task["duration_minutes"] == 135
        assert task["end_at"] == "2030-01-10T12:15:00Z"


def test_end_must_be_after_start():
    with registered_client("invalid-end@example.com") as client:
        response = client.post(
            "/api/v1/tasks",
            json={
                "title": "Invalid",
                "start_at": "2030-01-10T10:00:00Z",
                "end_at": "2030-01-10T09:00:00Z",
            },
        )
        assert response.status_code == 422
        assert "позже начала" in response.json()["detail"]


def test_only_deadline_controls_overdue_state():
    with registered_client("overdue@example.com") as client:
        old_schedule = client.post(
            "/api/v1/tasks",
            json={"title": "Old schedule", "start_at": "2020-01-01T10:00:00Z"},
        ).json()
        overdue = client.post(
            "/api/v1/tasks",
            json={"title": "Past deadline", "deadline_at": "2020-01-01T23:59:59Z"},
        ).json()
        assert old_schedule["is_overdue"] is False
        assert overdue["is_overdue"] is True
        assert overdue["start_at"] is None

        completed = client.patch(
            f'/api/v1/tasks/{overdue["id"]}',
            json={"status": "completed", "sync_version": overdue["sync_version"]},
        ).json()
        assert completed["is_overdue"] is False


def test_legacy_due_at_is_treated_as_calendar_end_not_deadline():
    with registered_client("legacy-due@example.com") as client:
        task = client.post(
            "/api/v1/tasks",
            json={
                "title": "Legacy client",
                "start_at": "2030-01-10T10:00:00Z",
                "due_at": "2030-01-10T11:00:00Z",
            },
        ).json()
        assert task["end_at"] == "2030-01-10T11:00:00Z"
        assert task["deadline_at"] is None
        assert task["is_overdue"] is False


def test_deadline_actions_are_idempotent():
    with registered_client("actions@example.com") as client:
        marked = client.post(
            "/api/v1/tasks",
            json={"title": "Mark", "deadline_at": "2020-01-01T10:00:00Z", "deadline_action": "mark_overdue"},
        ).json()
        automatic = client.post(
            "/api/v1/tasks",
            json={"title": "Complete", "deadline_at": "2020-01-01T10:00:00Z", "deadline_action": "auto_complete"},
        ).json()
        ignored = client.post(
            "/api/v1/tasks",
            json={"title": "Ignore", "deadline_at": "2020-01-01T10:00:00Z", "deadline_action": "none"},
        ).json()

        now = datetime(2020, 1, 2, tzinfo=timezone.utc)
        with SessionLocal() as db:
            assert process_deadlines(db, now) == {"marked_overdue": 1, "auto_completed": 1}
            assert process_deadlines(db, now) == {"marked_overdue": 0, "auto_completed": 0}
            log_count = db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.action.in_(["task_marked_overdue", "task_auto_completed"])))
            assert log_count == 2

        marked_after = client.get(f'/api/v1/tasks/{marked["id"]}').json()
        automatic_after = client.get(f'/api/v1/tasks/{automatic["id"]}').json()
        ignored_after = client.get(f'/api/v1/tasks/{ignored["id"]}').json()
        assert marked_after["status"] == "planned" and marked_after["is_overdue"]
        assert marked_after["deadline_processed_at"] is not None
        assert automatic_after["status"] == "completed" and not automatic_after["is_overdue"]
        assert automatic_after["completed_at"] is not None
        assert ignored_after["status"] == "planned" and ignored_after["deadline_processed_at"] is None


def test_changing_deadline_resets_processing_and_cancelled_is_not_overdue():
    with registered_client("reset-deadline@example.com") as client:
        task = client.post(
            "/api/v1/tasks",
            json={"title": "Reset", "deadline_at": "2020-01-01T10:00:00Z", "deadline_action": "mark_overdue"},
        ).json()
        with SessionLocal() as db:
            process_deadlines(db, datetime(2020, 1, 2, tzinfo=timezone.utc))
        processed = client.get(f'/api/v1/tasks/{task["id"]}').json()
        changed = client.patch(
            f'/api/v1/tasks/{task["id"]}',
            json={"deadline_at": "2030-01-01T10:00:00Z", "sync_version": processed["sync_version"]},
        ).json()
        assert changed["deadline_processed_at"] is None
        cancelled = client.patch(
            f'/api/v1/tasks/{task["id"]}',
            json={"status": "cancelled", "deadline_at": "2020-01-01T10:00:00Z", "sync_version": changed["sync_version"]},
        ).json()
        assert cancelled["status"] == "cancelled"
        assert cancelled["is_overdue"] is False
