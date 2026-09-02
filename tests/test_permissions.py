from fastapi.testclient import TestClient
from app.main import app

def register(client,email,name):
    return client.post("/api/v1/auth/register",json={"email":email,"password":"StrongPass123","name":name})

def test_observer_and_outsider_cannot_mutate_or_read_private_project_data():
    with TestClient(app) as client:
        register(client,"observer@example.com","Observer");client.post("/api/v1/auth/logout")
        register(client,"outsider@example.com","Outsider");client.post("/api/v1/auth/logout")
        register(client,"permissions-owner@example.com","Owner")
        project=client.post("/api/v1/projects",json={"name":"Private","color":"#123456"}).json()
        observer_role=next(role for role in project["roles"] if role["name"]=="Наблюдатель")
        member=client.post(f'/api/v1/projects/{project["id"]}/members',json={"email":"observer@example.com","role_ids":[observer_role["id"]]}).json()
        task=client.post("/api/v1/tasks",json={"title":"Private task","project_id":project["id"],"column_id":project["columns"][0]["id"]}).json()
        channel=project["channels"][0]

        client.post("/api/v1/auth/logout");client.post("/api/v1/auth/login",json={"email":"observer@example.com","password":"StrongPass123"})
        assert client.patch(f'/api/v1/projects/{project["id"]}',json={"name":"Hacked","color":"#000000"}).status_code in (403,404)
        assert client.patch(f'/api/v1/tasks/{task["id"]}',json={"title":"Hacked","sync_version":task["sync_version"]}).status_code==403
        assert client.post(f'/api/v1/projects/{project["id"]}/members',json={"email":"outsider@example.com","role_ids":[observer_role["id"]]}).status_code==403
        assert client.post(f'/api/v1/projects/{project["id"]}/roles',json={"name":"Admin","permissions":["manage_members"]}).status_code==403
        assert client.delete(f'/api/v1/members/{member["id"]}').status_code==403

        client.post("/api/v1/auth/logout");client.post("/api/v1/auth/login",json={"email":"outsider@example.com","password":"StrongPass123"})
        assert client.get(f'/api/v1/tasks/{task["id"]}').status_code==404
        assert client.get(f'/api/v1/channels/{channel["id"]}/messages').status_code==403
        assert all(item["id"]!=project["id"] for item in client.get("/api/v1/projects").json())

def test_cross_origin_state_change_is_rejected():
    with TestClient(app) as client:
        response=client.post("/api/v1/auth/register",headers={"Origin":"https://evil.example"},json={"email":"csrf@example.com","password":"StrongPass123","name":"CSRF"})
        assert response.status_code==403

def test_project_member_must_receive_kanban_view_access():
    with TestClient(app) as client:
        register(client,"kanban-member@example.com","Kanban Member");client.post("/api/v1/auth/logout")
        register(client,"kanban-owner@example.com","Kanban Owner")
        project=client.post("/api/v1/projects",json={"name":"Shared kanban","color":"#123456"}).json()
        chat_only=client.post(f'/api/v1/projects/{project["id"]}/roles',json={"name":"Только чат","permissions":["send_messages"]}).json()
        denied=client.post(f'/api/v1/projects/{project["id"]}/members',json={"email":"kanban-member@example.com","role_ids":[chat_only["id"]]})
        assert denied.status_code==400

        observer=next(role for role in project["roles"] if role["name"]=="Наблюдатель")
        added=client.post(f'/api/v1/projects/{project["id"]}/members',json={"email":"kanban-member@example.com","role_ids":[observer["id"]]})
        assert added.status_code==201
        assert client.patch(f'/api/v1/members/{added.json()["id"]}',json={"role_ids":[chat_only["id"]]}).status_code==400
        client.post("/api/v1/auth/logout");client.post("/api/v1/auth/login",json={"email":"kanban-member@example.com","password":"StrongPass123"})
        assert any(item["id"]==project["id"] for item in client.get("/api/v1/projects").json())
