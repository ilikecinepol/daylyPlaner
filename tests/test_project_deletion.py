from contextlib import contextmanager

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ChatChannel, Project, ProjectMember, Task


@contextmanager
def project_client(email):
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"email":email,"password":"StrongPass123","name":"Owner"})
        project=client.post("/api/v1/projects",json={"name":"Disposable","color":"#5577e7"}).json()
        yield client,project


def create_task(client,project,title,status="planned"):
    return client.post("/api/v1/tasks",json={"title":title,"status":status,"project_id":project["id"],"column_id":project["columns"][0]["id"]}).json()


def test_delete_project_keeps_tasks_as_personal_by_default():
    with project_client("project-keep@example.com") as (client,project):
        task=create_task(client,project,"Keep me")
        result=client.post(f"/api/v1/projects/{project['id']}/delete",json={"task_policy":"keep"})
        assert result.status_code==200
        assert result.json()["affected_tasks"]==1
        assert client.get("/api/v1/projects").json()==[]
        kept=client.get(f"/api/v1/tasks/{task['id']}").json()
        assert kept["project_id"] is None
        assert kept["column_id"] is None


def test_delete_project_can_archive_tasks_and_preserves_collaboration_data():
    with project_client("project-archive@example.com") as (client,project):
        task=create_task(client,project,"Archive me")
        result=client.post(f"/api/v1/projects/{project['id']}/delete",json={"task_policy":"archive"})
        assert result.status_code==200
        assert client.get("/api/v1/tasks").json()==[]
        archived=client.get("/api/v1/tasks?include_archived=true").json()[0]
        assert archived["id"]==task["id"] and archived["archived_at"]
        with SessionLocal() as db:
            assert db.get(Project,project["id"]).deleted_at is not None
            assert db.query(ProjectMember).filter(ProjectMember.project_id==project["id"]).count()==1
            assert db.query(ChatChannel).filter(ChatChannel.project_id==project["id"]).count()==1


def test_delete_project_can_soft_delete_tasks():
    with project_client("project-delete@example.com") as (client,project):
        task=create_task(client,project,"Delete me")
        result=client.post(f"/api/v1/projects/{project['id']}/delete",json={"task_policy":"delete"})
        assert result.status_code==200
        assert client.get(f"/api/v1/tasks/{task['id']}").status_code==404
        with SessionLocal() as db:
            assert db.get(Task,task["id"]).deleted_at is not None


def test_project_delete_policy_is_validated():
    with project_client("project-invalid@example.com") as (client,project):
        assert client.post(f"/api/v1/projects/{project['id']}/delete",json={"task_policy":"explode"}).status_code==422
