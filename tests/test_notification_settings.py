from datetime import datetime,timedelta,timezone

from fastapi.testclient import TestClient

from app.main import app


def test_notification_channels_priorities_settings_and_clear():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"email":"notification-settings@example.com","password":"StrongPass123","name":"Notify"})
        deadline=(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()
        task=client.post("/api/v1/tasks",json={"title":"Очень срочно","priority":"P1","deadline_at":deadline}).json()
        feed=client.get("/api/v1/notifications/feed").json()
        urgent=next(item for item in feed if item["type"]=="urgent_task" and item["task_id"]==task["id"])
        soon=next(item for item in feed if item["type"]=="deadline_soon" and item["task_id"]==task["id"])
        assert urgent["channel"]=="alarm" and urgent["priority"]=="urgent"
        assert soon["channel"]=="sound" and soon["priority"]=="high"
        saved=client.patch("/api/v1/auth/notification-settings",json={"rules":{"urgent_task":{"enabled":False,"channel":"bell","priority":"normal"}}})
        assert saved.status_code==200
        assert saved.json()["notification_settings"]["urgent_task"]["enabled"] is False
        assert not any(item["type"]=="urgent_task" for item in client.get("/api/v1/notifications/feed").json())
        assert client.post("/api/v1/notifications/clear").status_code==204
        assert client.get("/api/v1/notifications/feed").json()==[]


def test_notification_settings_validation():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"email":"notification-validation@example.com","password":"StrongPass123","name":"Notify"})
        response=client.patch("/api/v1/auth/notification-settings",json={"rules":{"urgent_task":{"enabled":True,"channel":"telegram","priority":"urgent"}}})
        assert response.status_code==422
