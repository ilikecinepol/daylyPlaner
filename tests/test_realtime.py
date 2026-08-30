from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.services.realtime import revision


def test_realtime_revision_changes_for_tasks_projects_and_messages():
    with TestClient(app) as client:
        user=client.post("/api/v1/auth/register",json={"email":"realtime@example.com","password":"StrongPass123","name":"Realtime"}).json()
        with SessionLocal() as db:initial=revision(db,user["id"])
        project=client.post("/api/v1/projects",json={"name":"Live project","color":"#5577e7"}).json()
        with SessionLocal() as db:after_project=revision(db,user["id"])
        assert after_project!=initial
        task=client.post("/api/v1/tasks",json={"title":"Live task","project_id":project["id"]}).json()
        with SessionLocal() as db:after_task=revision(db,user["id"])
        assert after_task!=after_project
        channel=project["channels"][0]
        client.post(f"/api/v1/channels/{channel['id']}/messages",json={"content":"Live message","attached_task_id":task["id"]})
        with SessionLocal() as db:after_message=revision(db,user["id"])
        assert after_message!=after_task


def test_event_stream_requires_authentication():
    with TestClient(app) as client:
        assert client.get("/api/v1/events").status_code==401
