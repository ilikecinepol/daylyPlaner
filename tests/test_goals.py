from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app

def account(client):
    assert client.post("/api/v1/auth/register", json={"email":f"{uuid4()}@example.com","password":"StrongPass123","name":"Goal user"}).status_code == 201

def make(client, period="month", date="2028-02-18", **values):
    return client.post("/api/v1/goals", json={"title":"Важная цель","why":"Помнить зачем","period":period,"date":date,**values})

def test_goal_periods_hierarchy_and_isolation():
    with TestClient(app) as first, TestClient(app) as second:
        account(first); account(second)
        month=make(first).json()
        assert month["period_start"]=="2028-02-01" and month["period_end"]=="2028-02-29"
        week=make(first,"week",parent_id=month["id"]).json()
        assert week["period_start"]=="2028-02-14" and week["period_end"]=="2028-02-20"
        day=make(first,"day",parent_id=week["id"]).json()
        assert day["period_start"]==day["period_end"]=="2028-02-18"
        assert make(first,parent_id=day["id"]).status_code==400
        assert make(second,"day",parent_id=month["id"]).status_code==404
        assert second.get("/api/v1/goals").json()==[]
        assert second.delete("/api/v1/goals/"+month["id"]).status_code==404
        assert first.put("/api/v1/goals/"+month["id"],json={"title":"Changed","period":"day","date":"2028-02-18"}).status_code==400

def test_tasks_progress_detachment_and_preservation():
    with TestClient(app) as client, TestClient(app) as other:
        account(client);account(other)
        goal=make(client).json()
        task=client.post("/api/v1/tasks",json={"title":"Normal task","goal_id":goal["id"]}).json()
        assert task["goal_id"]==goal["id"]
        assert other.post("/api/v1/tasks",json={"title":"Denied","goal_id":goal["id"]}).status_code==404
        assert client.get("/api/v1/goals").json()[0]["progress"]==0
        assert client.patch("/api/v1/tasks/"+task["id"],json={"status":"completed"}).status_code==200
        assert client.post("/api/v1/tasks/"+task["id"]+"/archive").status_code==200
        client.post("/api/v1/tasks",json={"title":"Cancelled","status":"cancelled","goal_id":goal["id"]})
        progress=client.get("/api/v1/goals").json()[0]
        assert (progress["total"],progress["completed"],progress["progress"])==(1,1,100)
        child=make(client,"day",parent_id=goal["id"]).json()
        assert client.delete("/api/v1/goals/"+goal["id"]).status_code==204
        saved=client.get("/api/v1/tasks/"+task["id"]).json()
        assert saved["goal_id"] is None and saved["status"]=="completed" and saved["archived_at"]
        assert client.get("/api/v1/goals").json()[0]["parent_id"] is None
        assert client.patch("/api/v1/tasks/"+task["id"],json={"goal_id":goal["id"]}).status_code==404

def test_goal_validation_and_existing_task_link():
    with TestClient(app) as client:
        account(client)
        for values in [{"title":" "},{"period":"year"},{"date":"invalid"}]:
            assert make(client,**values).status_code==422
        goal=make(client).json()
        task=client.post("/api/v1/tasks",json={"title":"Existing"}).json()
        response=client.patch("/api/v1/tasks/"+task["id"],json={"goal_id":goal["id"],"sync_version":task["sync_version"]})
        assert response.status_code==200
        assert client.patch("/api/v1/tasks/"+task["id"],json={"goal_id":None,"sync_version":task["sync_version"]}).status_code==409
        assert client.patch("/api/v1/tasks/"+task["id"],json={"goal_id":None}).json()["goal_id"] is None
