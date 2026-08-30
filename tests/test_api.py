import os,tempfile
db_file=tempfile.NamedTemporaryFile(suffix=".db",delete=False).name
os.environ["DATABASE_URL"]="sqlite:///"+db_file
os.environ["SECRET_KEY"]="test-secret"
from fastapi.testclient import TestClient
from app.main import app

def test_auth_crud_and_soft_delete():
    with TestClient(app) as c:
        r=c.post("/api/v1/auth/register",json={"email":"test@example.com","password":"strong-pass","name":"Test"});assert r.status_code==201
        p=c.post("/api/v1/projects",json={"name":"Project","color":"#5577e7"});assert p.status_code==201;project=p.json();assert len(project["columns"])==4
        t=c.post("/api/v1/tasks",json={"title":"Task","priority":"P1","project_id":project["id"],"column_id":project["columns"][0]["id"],"start_at":"2026-08-27T10:00:00Z","reminder_offsets":[30]});assert t.status_code==201;task=t.json()
        u=c.patch(f'/api/v1/tasks/{task["id"]}',json={"status":"completed","sync_version":task["sync_version"]});assert u.status_code==200
        assert c.delete(f'/api/v1/tasks/{task["id"]}').status_code==204
        assert c.get("/api/v1/tasks").json()==[]

def test_requires_authentication():
    with TestClient(app) as c:assert c.get("/api/v1/tasks").status_code==401

def test_registration_validation_and_relogin():
    with TestClient(app) as c:
        assert c.post("/api/v1/auth/register",json={"email":"bad","password":"123","name":""}).status_code==422
        email="registration@example.com";password="StrongPass123"
        assert c.post("/api/v1/auth/register",json={"email":email,"password":password,"name":"Новый пользователь"}).status_code==201
        assert c.post("/api/v1/auth/logout").status_code==204
        assert c.get("/api/v1/auth/me").status_code==401
        assert c.post("/api/v1/auth/login",json={"email":email,"password":password}).status_code==200
        assert c.get("/api/v1/auth/me").json()["email"]==email

def test_utc_time_roundtrip_contract():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"timezone@example.com","password":"StrongPass123","name":"Timezone"})
        task=c.post("/api/v1/tasks",json={"title":"17:30 Moscow","start_at":"2026-08-27T14:30:00Z","duration_minutes":60}).json()
        assert task["start_at"]=="2026-08-27T14:30:00Z"
        loaded=c.get(f'/api/v1/tasks/{task["id"]}').json()
        assert loaded["start_at"]=="2026-08-27T14:30:00Z"

def test_team_contacts_roles_channels_and_task_attachment():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"member@example.com","password":"StrongPass123","name":"Member"});c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"owner@example.com","password":"StrongPass123","name":"Owner"})
        contact=c.post("/api/v1/contacts",json={"email":"member@example.com","nickname":"Коллега"});assert contact.status_code==201
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"member@example.com","password":"StrongPass123"});request=c.get("/api/v1/friend-requests").json()[0];assert c.post(f'/api/v1/friend-requests/{request["id"]}/accept').status_code==200;c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"owner@example.com","password":"StrongPass123"})
        project=c.post("/api/v1/projects",json={"name":"Team project","color":"#5577e7"}).json();member_role=next(r for r in project["roles"] if r["name"]=="Участник")
        member=c.post(f'/api/v1/projects/{project["id"]}/members',json={"email":"member@example.com","role_id":member_role["id"]});assert member.status_code==201
        channel=c.post(f'/api/v1/projects/{project["id"]}/channels',json={"name":"разработка","description":"Dev"}).json()
        task=c.post("/api/v1/tasks",json={"title":"Kanban card","project_id":project["id"],"column_id":project["columns"][0]["id"]}).json()
        message=c.post(f'/api/v1/channels/{channel["id"]}/messages',json={"content":"Берём в работу","attached_task_id":task["id"]});assert message.status_code==201;assert message.json()["task"]["title"]=="Kanban card"
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"member@example.com","password":"StrongPass123"})
        assert any(p["id"]==project["id"] for p in c.get("/api/v1/projects").json())
        assert c.get(f'/api/v1/channels/{channel["id"]}/messages').json()[0]["content"]=="Берём в работу"

def test_team_label_auto_membership_and_multiple_roles():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"robot@example.com","password":"StrongPass123","name":"Робототехник"});c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"lead@example.com","password":"StrongPass123","name":"Руководитель"})
        contact=c.post("/api/v1/contacts",json={"email":"robot@example.com","tags":["Подводная робототехника","Инженеры"]});assert contact.status_code==201
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"robot@example.com","password":"StrongPass123"});request=c.get("/api/v1/friend-requests").json()[0];c.post(f'/api/v1/friend-requests/{request["id"]}/accept');c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"lead@example.com","password":"StrongPass123"})
        project=c.post("/api/v1/projects",json={"name":"Батискаф","color":"#5577e7","team_label":"подводная робототехника"});assert project.status_code==201
        data=project.json();member=next(m for m in data["members"] if m["email"]=="robot@example.com");assert [r["name"] for r in member["roles"]]==["Участник"]
        custom=c.post(f'/api/v1/projects/{data["id"]}/roles',json={"name":"Куратор","color":"#8b5cf6","permissions":["view","manage_channels"]}).json()
        participant=next(r for r in data["roles"] if r["name"]=="Участник")
        changed=c.patch(f'/api/v1/members/{member["id"]}',json={"email":"robot@example.com","role_ids":[participant["id"],custom["id"]]});assert changed.status_code==200;assert {r["name"] for r in changed.json()["roles"]}=={"Участник","Куратор"}
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"robot@example.com","password":"StrongPass123"})
        assert any(p["id"]==data["id"] for p in c.get("/api/v1/projects").json())
        assert c.post(f'/api/v1/projects/{data["id"]}/channels',json={"name":"испытания"}).status_code==201

def test_nickname_friend_search_and_project_admin():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"friend@example.com","password":"StrongPass123","name":"Друг","nickname":"ocean_friend"});c.post("/api/v1/auth/logout")
        owner=c.post("/api/v1/auth/register",json={"email":"boss@example.com","password":"StrongPass123","name":"Создатель","nickname":"team_boss"});assert owner.json()["nickname"]=="team_boss"
        search=c.get("/api/v1/users/search?q=ocean");assert search.status_code==200;assert search.json()[0]["nickname"]=="ocean_friend";assert not search.json()[0]["is_friend"]
        friend=c.post("/api/v1/contacts",json={"user_nickname":"ocean_friend","tags":[]});assert friend.status_code==201;assert friend.json()["status"]=="pending"
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"friend@example.com","password":"StrongPass123"});request=c.get("/api/v1/friend-requests").json()[0];c.post(f'/api/v1/friend-requests/{request["id"]}/accept');c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"boss@example.com","password":"StrongPass123"})
        project=c.post("/api/v1/projects",json={"name":"Nick project","color":"#5577e7"}).json();admin=next(m for m in project["members"] if m["is_owner"]);assert admin["role"]=="Администратор"
        member_role=next(r for r in project["roles"] if r["name"]=="Участник")
        member=c.post(f'/api/v1/projects/{project["id"]}/members',json={"user_nickname":"ocean_friend","role_ids":[member_role["id"]]});assert member.status_code==201;assert member.json()["nickname"]=="ocean_friend"
        assert c.patch(f'/api/v1/members/{admin["id"]}',json={"user_nickname":"team_boss","role_ids":[member_role["id"]]}).status_code==400

def test_channel_management_and_add_friends_during_creation():
    with TestClient(app) as c:
        friend=c.post("/api/v1/auth/register",json={"email":"channel-friend@example.com","password":"StrongPass123","name":"Друг канала","nickname":"channel_friend"}).json();c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"channel-owner@example.com","password":"StrongPass123","name":"Владелец","nickname":"channel_owner"})
        c.post("/api/v1/contacts",json={"user_nickname":"channel_friend"})
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"channel-friend@example.com","password":"StrongPass123"});request=c.get("/api/v1/friend-requests").json()[0];c.post(f'/api/v1/friend-requests/{request["id"]}/accept');c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"channel-owner@example.com","password":"StrongPass123"})
        project=c.post("/api/v1/projects",json={"name":"Каналы","color":"#5577e7"}).json();common=project["channels"][0]
        created=c.post(f'/api/v1/projects/{project["id"]}/channels',json={"name":"дизайн","description":"Макеты","contact_user_ids":[friend["id"]]});assert created.status_code==201;assert created.json()["contacts_added"]==1
        refreshed=c.get("/api/v1/projects").json()[0];assert any(m["user_id"]==friend["id"] for m in refreshed["members"])
        channel=created.json();edited=c.patch(f'/api/v1/channels/{channel["id"]}',json={"name":"продукт","description":"Новый текст"});assert edited.status_code==200;assert edited.json()["name"]=="продукт"
        assert c.delete(f'/api/v1/channels/{channel["id"]}').status_code==204
        assert c.delete(f'/api/v1/channels/{common["id"]}').status_code==400

def test_friend_request_can_be_rejected():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"rejectee@example.com","password":"StrongPass123","name":"Получатель","nickname":"rejectee"});c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"requester@example.com","password":"StrongPass123","name":"Отправитель","nickname":"requester"})
        assert c.post("/api/v1/contacts",json={"user_nickname":"rejectee"}).json()["status"]=="pending"
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"rejectee@example.com","password":"StrongPass123"})
        request=c.get("/api/v1/friend-requests").json()[0];assert request["nickname"]=="requester"
        assert c.post(f'/api/v1/friend-requests/{request["id"]}/reject').status_code==204
        assert c.get("/api/v1/friend-requests").json()==[];assert c.get("/api/v1/contacts").json()==[]

def test_global_friend_roles_restrict_projects_and_channels():
    with TestClient(app) as c:
        c.post("/api/v1/auth/register",json={"email":"restricted@example.com","password":"StrongPass123","name":"Исполнитель","nickname":"restricted_user"});c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"roles-owner@example.com","password":"StrongPass123","name":"Владелец","nickname":"roles_owner"})
        pending=c.post("/api/v1/contacts",json={"user_nickname":"restricted_user"}).json();c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"restricted@example.com","password":"StrongPass123"})
        request=c.get("/api/v1/friend-requests").json()[0];c.post(f'/api/v1/friend-requests/{request["id"]}/accept');c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"roles-owner@example.com","password":"StrongPass123"})
        role=c.post("/api/v1/friend-roles",json={"name":"Подрядчик","color":"#8b5cf6"}).json();contact=c.get("/api/v1/contacts").json()[0]
        assert c.patch(f'/api/v1/contacts/{contact["id"]}',json={"nickname":"Внешний специалист","role_ids":[role["id"]]}).status_code==200
        project=c.post("/api/v1/projects",json={"name":"Закрытый проект","color":"#5577e7"}).json();project_role=c.post(f'/api/v1/projects/{project["id"]}/roles',json={"name":"Расширенный","color":"#999999","permissions":["view","edit_tasks","send_messages","manage_channels","manage_members"]}).json()
        c.post(f'/api/v1/projects/{project["id"]}/members',json={"user_nickname":"restricted_user","role_ids":[project_role["id"]]});channel=project["channels"][0]
        c.put(f'/api/v1/projects/{project["id"]}/role-rules',json={"role_id":role["id"],"denied_permissions":["edit_tasks"]})
        c.put(f'/api/v1/channels/{channel["id"]}/role-rules',json={"role_id":role["id"],"denied_permissions":["view","send_messages","manage_members"]})
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"restricted@example.com","password":"StrongPass123"})
        assert c.post("/api/v1/tasks",json={"title":"Запрещено","project_id":project["id"]}).status_code==403
        assert c.get(f'/api/v1/channels/{channel["id"]}/messages').status_code==403
        assert c.post(f'/api/v1/channels/{channel["id"]}/messages',json={"content":"Запрещено"}).status_code==403
        assert c.post(f'/api/v1/projects/{project["id"]}/members',json={"user_nickname":"roles_owner","role_ids":[project_role["id"]],"channel_id":channel["id"]}).status_code==403

def test_task_assignee_notifications_and_kanban_status_sync():
    with TestClient(app) as c:
        member=c.post("/api/v1/auth/register",json={"email":"assigned@example.com","password":"StrongPass123","name":"Исполнитель","nickname":"assigned_member"}).json();c.post("/api/v1/auth/logout")
        c.post("/api/v1/auth/register",json={"email":"assigner@example.com","password":"StrongPass123","name":"Руководитель","nickname":"assigner"})
        c.post("/api/v1/contacts",json={"user_nickname":"assigned_member"});c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"assigned@example.com","password":"StrongPass123"});request=c.get("/api/v1/friend-requests").json()[0];c.post(f'/api/v1/friend-requests/{request["id"]}/accept');c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"assigner@example.com","password":"StrongPass123"})
        project=c.post("/api/v1/projects",json={"name":"Workflow","color":"#5577e7"}).json();role=next(r for r in project["roles"] if r["name"]=="Участник");c.post(f'/api/v1/projects/{project["id"]}/members',json={"user_nickname":"assigned_member","role_ids":[role["id"]]})
        task=c.post("/api/v1/tasks",json={"title":"Назначенная задача","project_id":project["id"],"assigned_to_id":member["id"],"status":"planned"}).json();planned=next(x for x in project["columns"] if x["name"]=="Запланировано");assert task["column_id"]==planned["id"]
        c.post("/api/v1/auth/logout");c.post("/api/v1/auth/login",json={"email":"assigned@example.com","password":"StrongPass123"})
        feed=c.get("/api/v1/notifications/feed").json();assert any(x["type"]=="task_assigned" and x["task_id"]==task["id"] for x in feed)
        working=c.patch(f'/api/v1/tasks/{task["id"]}',json={"status":"in_progress","sync_version":task["sync_version"]}).json();assert working["started_by"]["id"]==member["id"];assert working["column_id"]==next(x for x in project["columns"] if x["name"]=="В работе")["id"]
        done=c.patch(f'/api/v1/tasks/{task["id"]}',json={"status":"completed","sync_version":working["sync_version"]}).json();assert done["completed_by"]["id"]==member["id"];assert done["column_id"]==next(x for x in project["columns"] if x["name"]=="Готово")["id"]
