from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


def register(client):
    response=client.post("/api/v1/auth/register",json={"email":f"{uuid4()}@example.com","password":"StrongPass123","name":"Modules"})
    assert response.status_code==201
    return response.json()


def test_optional_modules_are_private_and_locked_by_default():
    with TestClient(app) as first, TestClient(app) as second:
        register(first);register(second)
        modules={item["key"]:item for item in first.get("/api/v1/modules").json()}
        assert set(modules)=={"ai","finance","crace"}
        assert not any(item["connected"] for item in modules.values())
        assert first.get("/api/v1/finance/accounts").status_code==403
        assert first.get("/api/v1/crace").status_code==403
        assert first.post("/api/v1/modules/finance/unlock",json={"code":"wrong-code"}).status_code==403
        unlocked=first.post("/api/v1/modules/finance/unlock",json={"code":"test-module-code"})
        assert unlocked.status_code==200 and unlocked.json()["connected"] is True
        assert first.get("/api/v1/finance/accounts").status_code==200
        assert second.get("/api/v1/finance/accounts").status_code==403


def test_unlock_is_persistent_and_ai_unlock_grants_ai_access(monkeypatch):
    monkeypatch.setenv("AI_ENABLED","1");monkeypatch.setenv("AI_PROVIDER","demo")
    monkeypatch.setenv("AI_DEMO_ACCESS","0");monkeypatch.setenv("APP_ENV","production")
    with TestClient(app) as client:
        register(client)
        assert client.post("/api/v1/modules/ai/unlock",json={"code":"test-module-code"}).status_code==200
        assert client.get("/api/v1/ai/status").json()["access"] is True
        assert {item["key"]:item["connected"] for item in client.get("/api/v1/modules").json()}["ai"] is True


def test_finance_fields_cannot_bypass_module_api():
    with TestClient(app) as client:
        register(client)
        task=client.post("/api/v1/tasks",json={"title":"Обычная задача"})
        assert task.status_code==201
        finance={"type":"expense","amount":"10","currency":"RUB","account_id":"missing","category_id":None}
        assert client.post("/api/v1/tasks",json={"title":"Скрытый платёж","finance":finance}).status_code==403
        goal=client.post("/api/v1/goals",json={"title":"Цель","why":"","period":"month","date":"2026-10-01","target_amount":"100","currency":"RUB"})
        assert goal.status_code==403
