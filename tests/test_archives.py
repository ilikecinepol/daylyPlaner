from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import SessionLocal
from app.main import app
from app.models import Task, User
from app.services.archives import process_archives


@contextmanager
def registered_client(email):
    with TestClient(app) as client:
        response=client.post("/api/v1/auth/register",json={"email":email,"password":"StrongPass123","name":"Archive"})
        assert response.status_code==201
        yield client,response.json()["id"]


def test_manual_archive_is_hidden_and_can_be_restored():
    with registered_client("manual-archive@example.com") as (client,_):
        task=client.post("/api/v1/tasks",json={"title":"Done","status":"completed"}).json()
        archived=client.post(f"/api/v1/tasks/{task['id']}/archive")
        assert archived.status_code==200
        assert archived.json()["archived_at"]
        assert task["id"] not in {item["id"] for item in client.get("/api/v1/tasks").json()}
        assert task["id"] in {item["id"] for item in client.get("/api/v1/tasks?include_archived=true").json()}
        restored=client.post(f"/api/v1/tasks/{task['id']}/restore")
        assert restored.status_code==200
        assert restored.json()["archived_at"] is None


def test_active_task_cannot_be_archived():
    with registered_client("active-archive@example.com") as (client,_):
        task=client.post("/api/v1/tasks",json={"title":"Still active"}).json()
        assert client.post(f"/api/v1/tasks/{task['id']}/archive").status_code==409


def test_archive_settings_validation_and_storage():
    with registered_client("archive-settings@example.com") as (client,_):
        saved=client.patch("/api/v1/auth/archive-settings",json={"policy":"after_days","days":14})
        assert saved.status_code==200
        assert saved.json()["completed_task_archive_policy"]=="after_days"
        assert saved.json()["completed_task_archive_days"]==14
        assert client.patch("/api/v1/auth/archive-settings",json={"policy":"after_days","days":0}).status_code==422


def test_automatic_archive_policies_are_idempotent():
    current=datetime(2030,1,10,12,tzinfo=timezone.utc)
    with registered_client("auto-archive@example.com") as (_,user_id):
        with SessionLocal() as db:
            user=db.get(User,user_id);user.completed_task_archive_policy="after_days";user.completed_task_archive_days=3
            old=Task(user_id=user_id,title="Old",status="completed",completed_at=current-timedelta(days=4))
            recent=Task(user_id=user_id,title="Recent",status="completed",completed_at=current-timedelta(days=2))
            db.add_all([old,recent]);db.commit();old_id=old.id;recent_id=recent.id
        with SessionLocal() as db:
            assert process_archives(db,current)=={"auto_archived":1}
            assert process_archives(db,current)=={"auto_archived":0}
            assert db.get(Task,old_id).archived_at is not None
            assert db.get(Task,recent_id).archived_at is None


def test_end_of_day_uses_user_timezone():
    current=datetime(2030,1,10,0,30,tzinfo=timezone.utc)
    with registered_client("day-archive@example.com") as (_,user_id):
        with SessionLocal() as db:
            user=db.get(User,user_id);user.timezone="Europe/Moscow";user.completed_task_archive_policy="end_of_day"
            task=Task(user_id=user_id,title="Yesterday locally",status="completed",completed_at=datetime(2030,1,9,20,tzinfo=timezone.utc))
            db.add(task);db.commit();task_id=task.id
        with SessionLocal() as db:
            assert process_archives(db,current)=={"auto_archived":1}
            assert db.get(Task,task_id).archived_at is not None
