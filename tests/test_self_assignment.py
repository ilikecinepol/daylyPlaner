from fastapi.testclient import TestClient

from app.main import app


def test_member_can_assign_self_and_project_admin_is_notified_once():
    with TestClient(app) as owner,TestClient(app) as member:
        member_user=member.post("/api/v1/auth/register",json={"email":"claim-member@example.com","password":"StrongPass123","name":"Исполнитель","nickname":"claim_member"}).json()
        owner.post("/api/v1/auth/register",json={"email":"claim-owner@example.com","password":"StrongPass123","name":"Администратор","nickname":"claim_owner"})
        owner.post("/api/v1/contacts",json={"user_nickname":"claim_member"})
        request=member.get("/api/v1/friend-requests").json()[0]
        member.post(f"/api/v1/friend-requests/{request['id']}/accept")
        project=owner.post("/api/v1/projects",json={"name":"Самоназначение","color":"#5577e7"}).json()
        role=next(item for item in project["roles"] if item["name"]=="Участник")
        assert owner.post(f"/api/v1/projects/{project['id']}/members",json={"user_nickname":"claim_member","role_ids":[role["id"]]}).status_code==201
        task=owner.post("/api/v1/tasks",json={"title":"Свободная задача","project_id":project["id"]}).json()
        claimed=member.post(f"/api/v1/tasks/{task['id']}/assign-self")
        assert claimed.status_code==200
        assert claimed.json()["assigned_to_id"]==member_user["id"]
        assert member.post(f"/api/v1/tasks/{task['id']}/assign-self").status_code==200
        notices=[item for item in owner.get("/api/v1/notifications/feed").json() if item["type"]=="task_self_assigned"]
        assert len(notices)==1
        assert "Исполнитель" in notices[0]["title"] and "Свободная задача" in notices[0]["title"]
        assert not any(item["type"]=="task_assigned" for item in member.get("/api/v1/notifications/feed").json())


def test_non_member_cannot_assign_self():
    with TestClient(app) as owner,TestClient(app) as outsider:
        outsider.post("/api/v1/auth/register",json={"email":"claim-outsider@example.com","password":"StrongPass123","name":"Outsider","nickname":"claim_outsider"})
        owner.post("/api/v1/auth/register",json={"email":"claim-owner-two@example.com","password":"StrongPass123","name":"Owner","nickname":"claim_owner_two"})
        project=owner.post("/api/v1/projects",json={"name":"Private","color":"#5577e7"}).json()
        task=owner.post("/api/v1/tasks",json={"title":"Private task","project_id":project["id"]}).json()
        assert outsider.post(f"/api/v1/tasks/{task['id']}/assign-self").status_code==403


def test_member_selecting_self_as_assignee_gets_no_assignment_notification():
    with TestClient(app) as owner,TestClient(app) as member:
        member_user=member.post("/api/v1/auth/register",json={"email":"self-select-member@example.com","password":"StrongPass123","name":"Исполнитель","nickname":"self_select_member"}).json()
        owner.post("/api/v1/auth/register",json={"email":"self-select-owner@example.com","password":"StrongPass123","name":"Владелец","nickname":"self_select_owner"})
        owner.post("/api/v1/contacts",json={"user_nickname":"self_select_member"})
        member.post(f"/api/v1/friend-requests/{member.get('/api/v1/friend-requests').json()[0]['id']}/accept")
        project=owner.post("/api/v1/projects",json={"name":"Проект","color":"#5577e7"}).json()
        role=next(item for item in project["roles"] if item["name"]=="Участник")
        owner.post(f"/api/v1/projects/{project['id']}/members",json={"user_nickname":"self_select_member","role_ids":[role["id"]]})
        task=owner.post("/api/v1/tasks",json={"title":"Выбрать себя","project_id":project["id"]}).json()

        updated=member.patch(f"/api/v1/tasks/{task['id']}",json={"assigned_to_id":member_user["id"],"sync_version":task["sync_version"]})

        assert updated.status_code==200
        assert not any(item["type"]=="task_assigned" and item.get("task_id")==task["id"] for item in member.get("/api/v1/notifications/feed").json())
