from fastapi.testclient import TestClient

from app.main import app


def test_template_preserves_complete_task_card():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"email":"template-full@example.com","password":"StrongPass123","name":"Template"})
        task_data={
            "title":"Еженедельный отчёт","description":"Собрать показатели","priority":"P2","status":"planned",
            "start_at":"2030-01-10T07:00:00Z","end_at":"2030-01-10T08:30:00Z","deadline_at":"2030-01-10T12:00:00Z",
            "deadline_action":"mark_overdue","duration_minutes":90,"all_day":False,"location":"Онлайн",
            "tags":["отчёт","работа"],"recurrence_rule":"WEEKLY","reminder_offsets":[30],"project_id":None,"column_id":None,"assigned_to_id":None,
        }
        created=client.post("/api/v1/templates",json={"name":"Отчёт","description":task_data["description"],"duration":90,"priority":"P2","location":"Онлайн","reminders":[30],"task_data":task_data})
        assert created.status_code==201
        loaded=client.get("/api/v1/templates").json()[0]
        assert loaded["task_data"]==task_data


def test_legacy_template_gets_compatible_task_data():
    with TestClient(app) as client:
        client.post("/api/v1/auth/register",json={"email":"template-legacy@example.com","password":"StrongPass123","name":"Template"})
        client.post("/api/v1/templates",json={"name":"Старый шаблон","description":"Описание","duration":60,"priority":"P3","location":"Офис","reminders":[15]})
        loaded=client.get("/api/v1/templates").json()[0]
        assert loaded["task_data"]["title"]=="Старый шаблон"
        assert loaded["task_data"]["reminder_offsets"]==[15]
