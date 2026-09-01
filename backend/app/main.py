import os,asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from .database import Base,engine,get_db
from .models import User,Project,Task,TaskTemplate,KanbanColumn,Reminder,ActivityLog,Contact,ProjectRole,ProjectMember,ProjectMemberRole,ChatChannel,ChatMessage,FriendRole,ContactFriendRole,ProjectRoleRule,ChannelRoleRule
from .schemas import Credentials,TaskIn,TaskPatch,ProjectIn,ProjectDeleteIn,ColumnIn,TemplateIn,ContactIn,RoleIn,MemberIn,ChannelIn,MessageIn,FriendRoleIn,RoleRuleIn,ArchiveSettings,NotificationSettingsIn
from .security import hash_password,verify_password
from .services.recurrence import next_occurrence
from .services.notifications import due_reminders,filter_notification_feed,notification_settings
from .services.bootstrap import initialize_database
from .services.scheduling import is_overdue, normalize_schedule
from .services.realtime import revision as realtime_revision
from .schemas import ProfileIn
from .api.dependencies import set_session_cookie as cookie,current_user,iso_utc as dt
from .api.integrations import router as integrations_router
from .api.goals import router as goals_router, owned_goal

@asynccontextmanager
async def lifespan(_app:FastAPI):
    initialize_database()
    yield

app=FastAPI(title="План API",version="1.0.0",docs_url="/api/docs",openapi_url="/api/openapi.json",lifespan=lifespan)
app.include_router(integrations_router)
app.include_router(goals_router)

@app.middleware("http")
async def reject_cross_origin_writes(request:Request,call_next):
    if request.method not in {"GET","HEAD","OPTIONS"}:
        origin=request.headers.get("origin");allowed={value.strip() for value in os.getenv("ALLOWED_ORIGINS","").split(",") if value.strip()}
        if origin and origin.rstrip("/")!=str(request.base_url).rstrip("/") and origin not in allowed:return Response(status_code=403,content="Cross-origin state change rejected")
    return await call_next(request)
def own(db,model,obj_id,user):
    obj=db.get(model,obj_id)
    if not obj or getattr(obj,"user_id",None)!=user.id or getattr(obj,"deleted_at",None): raise HTTPException(404,"Объект не найден")
    return obj
def membership(db,project_id,user,permission="view"):
    p=db.get(Project,project_id)
    if not p or p.deleted_at:raise HTTPException(404,"Проект не найден")
    if p.user_id==user.id:return p
    member=db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==user.id));roles=[db.get(ProjectRole,x.role_id) for x in db.scalars(select(ProjectMemberRole).where(ProjectMemberRole.member_id==member.id))] if member else []
    permissions={perm for role in roles if role for perm in (role.permissions or [])}
    if permission not in permissions:raise HTTPException(403,"Недостаточно прав")
    owner_contact=db.scalar(select(Contact).where(Contact.owner_user_id==p.user_id,Contact.contact_user_id==user.id,Contact.status=="accepted"))
    role_ids=list(db.scalars(select(ContactFriendRole.role_id).where(ContactFriendRole.contact_id==owner_contact.id))) if owner_contact else []
    denied={value for rule in db.scalars(select(ProjectRoleRule).where(ProjectRoleRule.project_id==project_id,ProjectRoleRule.role_id.in_(role_ids))) for value in (rule.denied_permissions or [])} if role_ids else set()
    if permission in denied:raise HTTPException(403,"Доступ запрещён ролью")
    return p
def channel_permission(db,channel,user,permission):
    p=membership(db,channel.project_id,user,"view" if permission=="view" else permission)
    if p.user_id==user.id:return
    contact=db.scalar(select(Contact).where(Contact.owner_user_id==p.user_id,Contact.contact_user_id==user.id,Contact.status=="accepted"));role_ids=list(db.scalars(select(ContactFriendRole.role_id).where(ContactFriendRole.contact_id==contact.id))) if contact else []
    denied={value for rule in db.scalars(select(ChannelRoleRule).where(ChannelRoleRule.channel_id==channel.id,ChannelRoleRule.role_id.in_(role_ids))) for value in (rule.denied_permissions or [])} if role_ids else set()
    if permission in denied:raise HTTPException(403,"Доступ к каналу запрещён ролью")
def accessible_projects(db,user):return list(db.scalars(select(ProjectMember.project_id).join(Project,Project.id==ProjectMember.project_id).where(ProjectMember.user_id==user.id,Project.deleted_at==None)))
def set_member_roles(db,member,role_ids):
    found={r.id:r for r in db.scalars(select(ProjectRole).where(ProjectRole.id.in_(role_ids),ProjectRole.project_id==member.project_id))} if role_ids else {};roles=[found[x] for x in dict.fromkeys(role_ids) if x in found]
    if not roles:raise HTTPException(400,"Нужно назначить хотя бы одну роль")
    if len(roles)!=len(set(role_ids)):raise HTTPException(400,"Одна из ролей не принадлежит проекту")
    db.query(ProjectMemberRole).filter(ProjectMemberRole.member_id==member.id).delete();[db.add(ProjectMemberRole(member_id=member.id,role_id=r.id)) for r in roles];member.role_id=roles[0].id;return roles
def sync_team_label(db,p):
    label=(p.team_label or "").strip().casefold()
    if not label:return 0
    role=db.scalar(select(ProjectRole).where(ProjectRole.project_id==p.id,ProjectRole.name=="Участник")) or db.scalar(select(ProjectRole).where(ProjectRole.project_id==p.id).order_by(ProjectRole.position))
    if not role:return 0
    added=0
    for c in db.scalars(select(Contact).where(Contact.owner_user_id==p.user_id,Contact.status=="accepted")):
        if label not in {str(x).strip().casefold() for x in (c.tags or [])}:continue
        m=db.scalar(select(ProjectMember).where(ProjectMember.project_id==p.id,ProjectMember.user_id==c.contact_user_id))
        if not m:m=ProjectMember(project_id=p.id,user_id=c.contact_user_id,role_id=role.id);db.add(m);db.flush();added+=1
        if not db.scalar(select(ProjectMemberRole).where(ProjectMemberRole.member_id==m.id,ProjectMemberRole.role_id==role.id)):db.add(ProjectMemberRole(member_id=m.id,role_id=role.id))
    return added
def find_user(db,email=None,nickname=None):
    if nickname:return db.scalar(select(User).where(func.lower(User.nickname)==nickname.strip().lower(),User.deleted_at==None))
    if email:return db.scalar(select(User).where(func.lower(User.email)==email.strip().lower(),User.deleted_at==None))
    return None
def user_brief(db,user_id):
    user=db.get(User,user_id) if user_id else None
    return {"id":user.id,"name":user.name,"nickname":user.nickname} if user else None
def validate_assignee(db,project_id,assigned_to_id,owner_id):
    if not assigned_to_id:return
    if not project_id:
        if assigned_to_id!=owner_id:raise HTTPException(400,"Для личной задачи исполнителем можете быть только вы")
        return
    if not db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==assigned_to_id)):raise HTTPException(400,"Исполнитель не является участником проекта")
def sync_task_workflow(db,task,actor,status_changed=False,column_changed=False):
    names={"idea":"идеи","planned":"запланировано","in_progress":"в работе","completed":"готово"}
    if column_changed and task.column_id:
        column=db.get(KanbanColumn,task.column_id)
        reverse={v:k for k,v in names.items()};task.status=reverse.get(column.name.strip().casefold(),task.status) if column else task.status
    elif status_changed and task.project_id:
        wanted=names.get(task.status);column=next((c for c in db.scalars(select(KanbanColumn).where(KanbanColumn.project_id==task.project_id)) if c.name.strip().casefold()==wanted),None) if wanted else None
        if column:task.column_id=column.id
    if task.status=="in_progress" and status_changed:task.started_by_id=actor.id
    if task.status=="completed" and status_changed:task.completed_by_id=actor.id;task.completed_at=datetime.now(timezone.utc)
    elif status_changed:task.completed_at=None
def task_out(db,t):
    reminders=list(db.scalars(select(Reminder).where(Reminder.task_id==t.id)))
    return {"id":t.id,"goal_id":t.goal_id,"user_id":t.user_id,"title":t.title,"description":t.description,"status":t.status,"priority":t.priority,"project_id":t.project_id,"column_id":t.column_id,"assigned_to_id":t.assigned_to_id,"assignee":user_brief(db,t.assigned_to_id),"started_by":user_brief(db,t.started_by_id),"completed_by":user_brief(db,t.completed_by_id),"start_at":dt(t.start_at),"end_at":dt(t.end_at),"postponed_at":dt(t.postponed_at),"deadline_at":dt(t.deadline_at),"deadline_action":t.deadline_action or "none","deadline_processed_at":dt(t.deadline_processed_at),"due_at":dt(t.end_at),"duration_minutes":t.duration_minutes,"all_day":t.all_day,"is_overdue":is_overdue(t),"location":t.location,"tags":t.tags or [],"mentions":t.mentions or [],"recurrence_rule":t.recurrence_rule or "","reminder_offsets":[r.offset_minutes for r in reminders],"completed_at":dt(t.completed_at),"archived_at":dt(t.archived_at),"sync_version":t.sync_version,"created_at":dt(t.created_at),"updated_at":dt(t.updated_at)}
def project_out(db,p):
    roles=list(db.scalars(select(ProjectRole).where(ProjectRole.project_id==p.id).order_by(ProjectRole.position)));members=[]
    for m in db.scalars(select(ProjectMember).where(ProjectMember.project_id==p.id)):
        user=db.get(User,m.user_id);member_roles=[db.get(ProjectRole,x.role_id) for x in db.scalars(select(ProjectMemberRole).where(ProjectMemberRole.member_id==m.id))];member_roles=[r for r in member_roles if r]
        if not member_roles:
            legacy=db.get(ProjectRole,m.role_id)
            if legacy:member_roles=[legacy]
        primary=member_roles[0];serialized=[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions} for r in member_roles]
        members.append({"id":m.id,"user_id":m.user_id,"name":user.name,"nickname":user.nickname,"email":user.email,"is_owner":m.user_id==p.user_id,"role_id":primary.id,"role_ids":[r.id for r in member_roles],"role":primary.name,"role_color":primary.color,"roles":serialized})
    project_rules=[{"role_id":x.role_id,"denied_permissions":x.denied_permissions or []} for x in db.scalars(select(ProjectRoleRule).where(ProjectRoleRule.project_id==p.id))]
    channels=[]
    for c in db.scalars(select(ChatChannel).where(ChatChannel.project_id==p.id).order_by(ChatChannel.position)):
        rules=[{"role_id":x.role_id,"denied_permissions":x.denied_permissions or []} for x in db.scalars(select(ChannelRoleRule).where(ChannelRoleRule.channel_id==c.id))]
        channels.append({"id":c.id,"name":c.name,"description":c.description,"position":c.position,"role_rules":rules})
    return {"id":p.id,"name":p.name,"description":p.description,"color":p.color,"priority":p.priority,"team_label":p.team_label or "","owner_id":p.user_id,"columns":[{"id":c.id,"name":c.name,"position":c.position} for c in db.scalars(select(KanbanColumn).where(KanbanColumn.project_id==p.id).order_by(KanbanColumn.position))],"roles":[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions,"position":r.position} for r in roles],"members":members,"role_rules":project_rules,"channels":channels}
def log(db,u,action,task_id=None,changes={}): db.add(ActivityLog(user_id=u.id,task_id=task_id,action=action,changes=changes))
@app.post("/api/v1/auth/register",status_code=201)
def register(c:Credentials,response:Response,db:Session=Depends(get_db)):
    if db.scalar(select(User).where(User.email==c.email.lower())): raise HTTPException(409,"Email уже используется")
    nickname=(c.nickname or c.email.split("@")[0]).lower()
    if db.scalar(select(User).where(func.lower(User.nickname)==nickname)):raise HTTPException(409,"Этот ник уже занят")
    u=User(email=c.email.lower(),nickname=nickname,password_hash=hash_password(c.password),name=c.name or "Пользователь");db.add(u);db.commit();cookie(response,u.id);return {"id":u.id,"email":u.email,"nickname":u.nickname,"name":u.name,"timezone":u.timezone}
@app.post("/api/v1/auth/login")
def login(c:Credentials,response:Response,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==c.email.lower()))
    if not u or not verify_password(c.password,u.password_hash): raise HTTPException(401,"Неверный email или пароль")
    cookie(response,u.id);return {"id":u.id,"email":u.email,"nickname":u.nickname,"name":u.name,"timezone":u.timezone}
@app.post("/api/v1/auth/logout",status_code=204)
def logout(response:Response): response.delete_cookie("plan_session",path="/")
def user_out(u):return {"id":u.id,"email":u.email,"nickname":u.nickname,"name":u.name,"timezone":u.timezone,"last_name":u.last_name,"job_title":u.job_title,"profile_status":u.profile_status,"contact_info":u.contact_info,"avatar_data_url":u.avatar_data_url,"completed_task_archive_policy":u.completed_task_archive_policy or "never","completed_task_archive_days":u.completed_task_archive_days or 7,"notification_settings":notification_settings(u),"notifications_cleared_at":dt(u.notifications_cleared_at)}
@app.put("/api/v1/auth/profile")
def save_profile(data:ProfileIn,u=Depends(current_user),db:Session=Depends(get_db)):
    for key,value in data.model_dump().items():setattr(u,key,value)
    db.commit();return user_out(u)
@app.get("/api/v1/auth/me")
def me(u=Depends(current_user)): return user_out(u)
@app.patch("/api/v1/auth/archive-settings")
def archive_settings(data:ArchiveSettings,u=Depends(current_user),db:Session=Depends(get_db)):
    u.completed_task_archive_policy=data.policy;u.completed_task_archive_days=data.days;db.commit();return user_out(u)
@app.patch("/api/v1/auth/notification-settings")
def save_notification_settings(data:NotificationSettingsIn,u=Depends(current_user),db:Session=Depends(get_db)):
    allowed=set(notification_settings(u));u.notification_settings={key:value.model_dump() for key,value in data.rules.items() if key in allowed};db.commit();return user_out(u)
@app.post("/api/v1/notifications/clear",status_code=204)
def clear_notifications(u=Depends(current_user),db:Session=Depends(get_db)):
    u.notifications_cleared_at=datetime.now(timezone.utc);db.commit()

@app.get("/api/v1/tasks")
def tasks(q:str|None=None,status:str|None=None,priority:str|None=None,project:str|None=None,from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,include_archived:bool=False,u=Depends(current_user),db:Session=Depends(get_db)):
    shared=accessible_projects(db,u);s=select(Task).where(or_(Task.user_id==u.id,Task.project_id.in_(shared)),Task.deleted_at==None)
    if not include_archived:s=s.where(Task.archived_at==None)
    if q:s=s.where(or_(Task.title.ilike(f"%{q}%"),Task.description.ilike(f"%{q}%"),Task.location.ilike(f"%{q}%")))
    if status:s=s.where(Task.status==status)
    if priority:s=s.where(Task.priority==priority)
    if project:s=s.where(Task.project_id==project)
    if from_:s=s.where(Task.start_at>=from_)
    if to:s=s.where(Task.start_at<=to)
    return [task_out(db,t) for t in db.scalars(s.order_by(Task.start_at.asc().nullslast(),Task.priority))]
@app.post("/api/v1/tasks",status_code=201)
def create_task(data:TaskIn,u=Depends(current_user),db:Session=Depends(get_db)):
    return create_task_service(data,u,db)

def create_task_service(data,u,db,commit=True):
    if data.goal_id:owned_goal(db,data.goal_id,u)
    if data.project_id:membership(db,data.project_id,u,"edit_tasks")
    validate_assignee(db,data.project_id,data.assigned_to_id,u.id);values=normalize_schedule(data.model_dump(exclude={"reminder_offsets"}));t=Task(user_id=u.id,**values);sync_task_workflow(db,t,u,status_changed=True,column_changed=bool(t.column_id))
    db.add(t);db.flush();[db.add(Reminder(task_id=t.id,offset_minutes=x)) for x in data.reminder_offsets];log(db,u,"task_created",t.id);db.commit() if commit else db.flush();return task_out(db,t)
@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at or (t.user_id!=u.id and (not t.project_id or t.project_id not in accessible_projects(db,u))):raise HTTPException(404,"Задача не найдена")
    return task_out(db,t)
@app.patch("/api/v1/tasks/{task_id}")
def patch_task(task_id:str,data:TaskPatch,u=Depends(current_user),db:Session=Depends(get_db)):
    return patch_task_service(task_id,data,u,db)

def patch_task_service(task_id,data,u,db,commit=True):
    t=db.scalar(select(Task).where(Task.id==task_id).with_for_update().execution_options(populate_existing=True))
    if not t or t.deleted_at:raise HTTPException(404,"Задача не найдена")
    if t.project_id:
        if db.get(Project,t.project_id).user_id!=u.id:membership(db,t.project_id,u,"edit_tasks")
    elif t.user_id!=u.id:raise HTTPException(404,"Задача не найдена")
    patch=data.model_dump(exclude_unset=True);expected=patch.pop("sync_version",None);deadline_changed=bool({"deadline_at","deadline_action"}&set(patch))
    if expected is not None and expected!=t.sync_version: raise HTTPException(409,"Задача была изменена на другом устройстве")
    if "goal_id" in patch:
        if t.user_id != u.id and patch["goal_id"] != t.goal_id:raise HTTPException(403,"Цель может менять только владелец задачи")
        if patch["goal_id"] and patch["goal_id"] != t.goal_id:owned_goal(db,patch["goal_id"],u)
    offsets=patch.pop("reminder_offsets",None);patch=normalize_schedule(patch,t)
    if "start_at" in patch and "postponed_at" not in patch:patch["postponed_at"]=None
    if patch.get("status") in {"completed","cancelled"}:patch["postponed_at"]=None
    if deadline_changed:patch["deadline_processed_at"]=None
    before={k:getattr(t,k) for k in patch}
    validate_assignee(db,patch.get("project_id",t.project_id),patch.get("assigned_to_id",t.assigned_to_id),u.id)
    for k,v in patch.items(): setattr(t,k,v)
    sync_task_workflow(db,t,u,status_changed="status" in patch,column_changed="column_id" in patch and "status" not in patch)
    if "status" in patch and patch["status"]=="completed":
        nxt=next_occurrence(t.start_at,t.recurrence_rule)
        if nxt and not db.scalar(select(Task).where(Task.user_id==u.id,Task.title==t.title,Task.start_at==nxt,Task.deleted_at==None)):
            shift=nxt-t.start_at;child=Task(user_id=u.id,project_id=t.project_id,column_id=t.column_id,title=t.title,description=t.description,status="planned",priority=t.priority,start_at=nxt,end_at=(t.end_at+shift) if t.end_at else None,deadline_at=(t.deadline_at+shift) if t.deadline_at else None,deadline_action=t.deadline_action,duration_minutes=t.duration_minutes,all_day=t.all_day,location=t.location,tags=t.tags,mentions=t.mentions,recurrence_rule=t.recurrence_rule);db.add(child);db.flush();[db.add(Reminder(task_id=child.id,offset_minutes=r.offset_minutes,channel=r.channel)) for r in db.scalars(select(Reminder).where(Reminder.task_id==t.id))]
    t.sync_version=(t.sync_version or 0)+1
    if offsets is not None:db.query(Reminder).filter(Reminder.task_id==t.id).delete();[db.add(Reminder(task_id=t.id,offset_minutes=x)) for x in offsets]
    if "assigned_to_id" in patch and before["assigned_to_id"]!=patch["assigned_to_id"]:
        log(db,u,"task_self_assigned" if patch["assigned_to_id"]==u.id else "task_assigned",t.id,{"assigned_to_id":patch["assigned_to_id"]})
    log(db,u,"task_updated",t.id,{k:[str(before[k]),str(v)] for k,v in patch.items() if before[k]!=v});db.commit() if commit else db.flush();return task_out(db,t)
@app.delete("/api/v1/tasks/{task_id}",status_code=204)
def delete_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at:raise HTTPException(404,"Задача не найдена")
    if t.project_id:
        if db.get(Project,t.project_id).user_id!=u.id:membership(db,t.project_id,u,"edit_tasks")
    elif t.user_id!=u.id:raise HTTPException(404,"Задача не найдена")
    t.deleted_at=datetime.now(timezone.utc);t.sync_version+=1;log(db,u,"task_deleted",t.id);db.commit()

def archive_task_access(db,task_id,u):
    t=db.get(Task,task_id)
    if not t or t.deleted_at:raise HTTPException(404,"Задача не найдена")
    if t.project_id:
        if db.get(Project,t.project_id).user_id!=u.id:membership(db,t.project_id,u,"edit_tasks")
    elif t.user_id!=u.id:raise HTTPException(404,"Задача не найдена")
    return t
@app.post("/api/v1/tasks/{task_id}/archive")
def archive_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=archive_task_access(db,task_id,u)
    if t.status not in {"completed","cancelled"}:raise HTTPException(409,"Архивировать можно только завершённую или отменённую задачу")
    if not t.archived_at:t.archived_at=datetime.now(timezone.utc);t.sync_version=(t.sync_version or 0)+1;log(db,u,"task_archived",t.id);db.commit()
    return task_out(db,t)
@app.post("/api/v1/tasks/{task_id}/restore")
def restore_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=archive_task_access(db,task_id,u)
    if t.archived_at:t.archived_at=None;t.sync_version=(t.sync_version or 0)+1;log(db,u,"task_restored",t.id);db.commit()
    return task_out(db,t)
@app.post("/api/v1/tasks/{task_id}/assign-self")
def assign_task_to_self(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at or t.archived_at or not t.project_id:raise HTTPException(404,"Проектная задача не найдена")
    p=membership(db,t.project_id,u,"edit_tasks")
    if t.status in {"completed","cancelled"}:raise HTTPException(409,"Завершённую задачу нельзя назначить")
    if t.assigned_to_id and t.assigned_to_id!=u.id:raise HTTPException(409,"У задачи уже есть исполнитель")
    if t.assigned_to_id==u.id:return task_out(db,t)
    t.assigned_to_id=u.id;t.sync_version=(t.sync_version or 0)+1
    recipients={p.user_id}
    admin_roles=list(db.scalars(select(ProjectRole.id).where(ProjectRole.project_id==p.id,ProjectRole.name.in_(["Владелец","Администратор"]))))
    if admin_roles:
        recipients.update(db.scalars(select(ProjectMember.user_id).join(ProjectMemberRole,ProjectMemberRole.member_id==ProjectMember.id).where(ProjectMember.project_id==p.id,ProjectMemberRole.role_id.in_(admin_roles))))
    for recipient in recipients-{u.id}:db.add(ActivityLog(user_id=recipient,task_id=t.id,action="notification_task_self_assigned",changes={"actor_id":u.id,"actor_name":u.name,"task_title":t.title,"project_id":p.id,"project_name":p.name}))
    log(db,u,"task_self_assigned",t.id,{"project_id":p.id});db.commit();return task_out(db,t)

@app.get("/api/v1/calendar")
def calendar(from_:datetime=Query(alias="from"),to:datetime=Query(),u=Depends(current_user),db:Session=Depends(get_db)):
    return [task_out(db,t) for t in db.scalars(select(Task).where(Task.user_id==u.id,Task.deleted_at==None,Task.archived_at==None,Task.start_at>=from_,Task.start_at<=to).order_by(Task.start_at))]

@app.get("/api/v1/projects")
def projects(u=Depends(current_user),db:Session=Depends(get_db)): return [project_out(db,p) for p in db.scalars(select(Project).where(Project.id.in_(accessible_projects(db,u)),Project.deleted_at==None))]
@app.post("/api/v1/projects",status_code=201)
def create_project(data:ProjectIn,u=Depends(current_user),db:Session=Depends(get_db)):
    return create_project_service(data,u,db)

def create_project_service(data,u,db,commit=True):
    p=Project(user_id=u.id,**data.model_dump());db.add(p);db.flush();[db.add(KanbanColumn(project_id=p.id,name=n,position=i)) for i,n in enumerate(["Идеи","Запланировано","В работе","Готово"])]
    roles=[ProjectRole(project_id=p.id,name=n,color=c,permissions=perms,position=i) for i,(n,c,perms) in enumerate([("Владелец","#ff6b45",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Администратор","#e59b35",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Участник","#5577e7",["view","edit_tasks","send_messages"]),("Наблюдатель","#7b818b",["view"])])];db.add_all(roles);db.flush();admin=next(r for r in roles if r.name=="Администратор");owner=ProjectMember(project_id=p.id,user_id=u.id,role_id=admin.id);db.add(owner);db.flush();db.add(ProjectMemberRole(member_id=owner.id,role_id=admin.id));db.add(ChatChannel(project_id=p.id,name="общий",description="Основной канал проекта",position=0));sync_team_label(db,p);db.commit() if commit else db.flush();return project_out(db,p)
@app.patch("/api/v1/projects/{project_id}")
def patch_project(project_id:str,data:ProjectIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=own(db,Project,project_id,u);[setattr(p,k,v) for k,v in data.model_dump().items()];sync_team_label(db,p);db.commit();return project_out(db,p)
@app.delete("/api/v1/projects/{project_id}",status_code=204)
def delete_project(project_id:str,u=Depends(current_user),db:Session=Depends(get_db)):delete_project_with_policy(project_id,ProjectDeleteIn(),u,db)
@app.post("/api/v1/projects/{project_id}/delete")
def delete_project_with_policy(project_id:str,data:ProjectDeleteIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=own(db,Project,project_id,u);now=datetime.now(timezone.utc);affected=0
    for task in db.scalars(select(Task).where(Task.project_id==p.id,Task.deleted_at==None)):
        if data.task_policy=="keep":
            task.project_id=None;task.column_id=None
            if task.assigned_to_id!=task.user_id:task.assigned_to_id=None
        elif data.task_policy=="archive":task.archived_at=task.archived_at or now
        else:task.deleted_at=now
        task.sync_version=(task.sync_version or 0)+1;log(db,u,f"project_deleted_task_{data.task_policy}",task.id,{"project_id":p.id});affected+=1
    p.deleted_at=now;db.commit();return {"id":p.id,"task_policy":data.task_policy,"affected_tasks":affected}
@app.post("/api/v1/projects/{project_id}/columns",status_code=201)
def create_column(project_id:str,data:ColumnIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=membership(db,project_id,u,"manage_channels");pos=data.position if data.position is not None else db.scalar(select(func.count()).select_from(KanbanColumn).where(KanbanColumn.project_id==p.id));c=KanbanColumn(project_id=p.id,name=data.name,position=pos);db.add(c);db.commit();return {"id":c.id,"name":c.name,"position":c.position}
@app.patch("/api/v1/columns/{column_id}")
def patch_column(column_id:str,data:ColumnIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(KanbanColumn,column_id);p=own(db,Project,c.project_id,u) if c else None
    if not c:raise HTTPException(404,"Колонка не найдена")
    c.name=data.name;c.position=data.position if data.position is not None else c.position;db.commit();return {"id":c.id,"name":c.name,"position":c.position}

@app.get("/api/v1/templates")
def templates(u=Depends(current_user),db:Session=Depends(get_db)):return [{"id":t.id,"name":t.name,"icon":t.icon,"description":t.description,"duration":t.duration,"priority":t.priority,"location":t.location,"project_id":t.project_id,"reminders":t.reminders or [],"task_data":t.task_data or {"title":t.name,"description":t.description,"duration_minutes":t.duration,"priority":t.priority,"location":t.location,"project_id":t.project_id,"reminder_offsets":t.reminders or []}} for t in db.scalars(select(TaskTemplate).where(TaskTemplate.user_id==u.id,TaskTemplate.deleted_at==None))]
@app.post("/api/v1/templates",status_code=201)
def create_template(data:TemplateIn,u=Depends(current_user),db:Session=Depends(get_db)):t=TaskTemplate(user_id=u.id,**data.model_dump());db.add(t);db.commit();return {"id":t.id,**data.model_dump()}
@app.patch("/api/v1/templates/{template_id}")
def patch_template(template_id:str,data:TemplateIn,u=Depends(current_user),db:Session=Depends(get_db)):
    t=own(db,TaskTemplate,template_id,u)
    for key,value in data.model_dump().items():setattr(t,key,value)
    db.commit();return {"id":t.id,**data.model_dump()}
@app.delete("/api/v1/templates/{template_id}",status_code=204)
def delete_template(template_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=own(db,TaskTemplate,template_id,u);t.deleted_at=datetime.now(timezone.utc);db.commit()
@app.get("/api/v1/activity")
def activity(u=Depends(current_user),db:Session=Depends(get_db)):return [{"id":x.id,"task_id":x.task_id,"action":x.action,"changes":x.changes,"created_at":dt(x.created_at)} for x in db.scalars(select(ActivityLog).where(ActivityLog.user_id==u.id).order_by(ActivityLog.created_at.desc()).limit(100))]
@app.get("/api/v1/notifications")
def notifications(u=Depends(current_user),db:Session=Depends(get_db)):
    return [{**item,"start_at":dt(item["start_at"])} for item in due_reminders(db,u.id)]
@app.get("/api/v1/notifications/feed")
def notification_feed(u=Depends(current_user),db:Session=Depends(get_db)):
    result=[]
    for request in db.scalars(select(Contact).where(Contact.contact_user_id==u.id,Contact.status=="pending").order_by(Contact.created_at.desc())):
        sender=db.get(User,request.owner_user_id);result.append({"id":"friend-in-"+request.id,"type":"friend_incoming","title":f"{sender.name} хочет добавить вас в друзья","request_id":request.id,"created_at":dt(request.created_at)})
    for request in db.scalars(select(Contact).where(Contact.owner_user_id==u.id,Contact.status.in_(["pending","accepted","rejected"])).order_by(Contact.created_at.desc())):
        person=db.get(User,request.contact_user_id);labels={"pending":"ожидает ответа","accepted":"принята","rejected":"отклонена"};result.append({"id":"friend-out-"+request.id,"type":"friend_outgoing","title":f"Заявка для @{person.nickname}: {labels[request.status]}","status":request.status,"created_at":dt(request.created_at)})
    for task in db.scalars(select(Task).where(Task.assigned_to_id==u.id,Task.user_id!=u.id,Task.deleted_at==None).order_by(Task.updated_at.desc()).limit(50)):
        assignment=db.scalar(select(ActivityLog).where(ActivityLog.task_id==task.id,ActivityLog.action.in_(["task_self_assigned","task_assigned"])).order_by(ActivityLog.created_at.desc()))
        if assignment and assignment.action=="task_self_assigned" and assignment.user_id==u.id:continue
        author=db.get(User,task.user_id);result.append({"id":"task-"+task.id,"type":"task_assigned","title":f"{author.name} назначил вам задачу «{task.title}»","task_id":task.id,"created_at":dt(task.updated_at)})
    for item in db.scalars(select(ActivityLog).where(ActivityLog.user_id==u.id,ActivityLog.action=="notification_task_self_assigned").order_by(ActivityLog.created_at.desc()).limit(50)):
        changes=item.changes or {};result.append({"id":"self-assigned-"+item.id,"type":"task_self_assigned","title":f"{changes.get('actor_name','Участник')} назначил себя на задачу «{changes.get('task_title','')}» в проекте «{changes.get('project_name','')}»","task_id":item.task_id,"project_id":changes.get("project_id"),"created_at":dt(item.created_at)})
    now=datetime.now(timezone.utc);shared=accessible_projects(db,u)
    relevant=or_(Task.user_id==u.id,Task.assigned_to_id==u.id,Task.project_id.in_(shared))
    for task in db.scalars(select(Task).where(relevant,Task.deadline_at!=None,Task.deadline_at>now,Task.deadline_at<=now+timedelta(minutes=15),Task.status.notin_(["completed","cancelled"]),Task.deleted_at==None,Task.archived_at==None)):
        result.append({"id":"deadline-"+task.id,"type":"deadline_soon","title":f"До дедлайна задачи «{task.title}» осталось менее 15 минут","task_id":task.id,"created_at":dt(task.deadline_at-timedelta(minutes=15))})
    for task in db.scalars(select(Task).where(relevant,Task.priority=="P1",Task.status.notin_(["completed","cancelled"]),Task.deleted_at==None,Task.archived_at==None).order_by(Task.updated_at.desc()).limit(20)):
        result.append({"id":"urgent-"+task.id,"type":"urgent_task","title":f"Срочная задача: «{task.title}»","task_id":task.id,"created_at":dt(task.updated_at)})
    return sorted(filter_notification_feed(u,result),key=lambda x:x["created_at"] or "",reverse=True)

@app.get("/api/v1/contacts")
def contacts(u=Depends(current_user),db:Session=Depends(get_db)):
    result=[]
    for c in db.scalars(select(Contact).where(Contact.owner_user_id==u.id,Contact.status=="accepted")):
        person=db.get(User,c.contact_user_id);roles=[db.get(FriendRole,x.role_id) for x in db.scalars(select(ContactFriendRole).where(ContactFriendRole.contact_id==c.id))];result.append({"id":c.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":c.nickname,"tags":c.tags or [],"role_ids":[r.id for r in roles if r],"roles":[{"id":r.id,"name":r.name,"color":r.color} for r in roles if r]})
    return result
@app.get("/api/v1/friend-requests")
def friend_requests(u=Depends(current_user),db:Session=Depends(get_db)):
    result=[]
    for request in db.scalars(select(Contact).where(Contact.contact_user_id==u.id,Contact.status=="pending").order_by(Contact.created_at.desc())):
        sender=db.get(User,request.owner_user_id)
        if sender and not sender.deleted_at:result.append({"id":request.id,"user_id":sender.id,"name":sender.name,"nickname":sender.nickname,"created_at":dt(request.created_at)})
    return result
@app.get("/api/v1/users/search")
def search_users(q:str=Query(min_length=2,max_length=40),u=Depends(current_user),db:Session=Depends(get_db)):
    pattern=f"%{q.strip().lower()}%";friends=set(db.scalars(select(Contact.contact_user_id).where(Contact.owner_user_id==u.id,Contact.status=="accepted")))
    found=db.scalars(select(User).where(User.id!=u.id,User.deleted_at==None,func.lower(User.nickname).like(pattern)).order_by(User.nickname).limit(10))
    return [{"id":x.id,"nickname":x.nickname,"name":x.name,"is_friend":x.id in friends} for x in found]
@app.post("/api/v1/contacts",status_code=201)
def add_contact(data:ContactIn,u=Depends(current_user),db:Session=Depends(get_db)):
    person=find_user(db,data.email,data.user_nickname)
    if not person:raise HTTPException(404,"Пользователь с таким ником не найден")
    if person.id==u.id:raise HTTPException(400,"Нельзя добавить себя")
    c=db.scalar(select(Contact).where(Contact.owner_user_id==u.id,Contact.contact_user_id==person.id))
    if c and c.status=="accepted":raise HTTPException(400,"Этот пользователь уже в друзьях")
    if not c:c=Contact(owner_user_id=u.id,contact_user_id=person.id,nickname=data.nickname,tags=data.tags,status="pending");db.add(c)
    else:c.nickname=data.nickname;c.tags=data.tags;c.status="pending"
    db.commit();return {"id":c.id,"user_id":person.id,"name":person.name,"user_nickname":person.nickname,"status":"pending"}
@app.post("/api/v1/friend-requests/{request_id}/accept")
def accept_friend_request(request_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    request=db.get(Contact,request_id)
    if not request or request.contact_user_id!=u.id or request.status!="pending":raise HTTPException(404,"Запрос не найден")
    request.status="accepted";reverse=db.scalar(select(Contact).where(Contact.owner_user_id==u.id,Contact.contact_user_id==request.owner_user_id))
    if not reverse:reverse=Contact(owner_user_id=u.id,contact_user_id=request.owner_user_id,status="accepted");db.add(reverse)
    else:reverse.status="accepted"
    db.commit();person=db.get(User,request.owner_user_id);return {"id":reverse.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":reverse.nickname,"tags":reverse.tags or []}
@app.post("/api/v1/friend-requests/{request_id}/reject",status_code=204)
def reject_friend_request(request_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    request=db.get(Contact,request_id)
    if not request or request.contact_user_id!=u.id or request.status!="pending":raise HTTPException(404,"Запрос не найден")
    request.status="rejected";db.commit()
@app.patch("/api/v1/contacts/{contact_id}")
def edit_contact(contact_id:str,data:ContactIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(Contact,contact_id)
    if not c or c.owner_user_id!=u.id:raise HTTPException(404,"Контакт не найден")
    person=db.get(User,c.contact_user_id)
    if data.email and data.email.lower()!=person.email.lower():raise HTTPException(400,"Email контакта менять нельзя")
    roles=list(db.scalars(select(FriendRole).where(FriendRole.owner_user_id==u.id,FriendRole.id.in_(data.role_ids)))) if data.role_ids else []
    if len(roles)!=len(set(data.role_ids)):raise HTTPException(400,"Неизвестная роль")
    c.nickname=data.nickname;c.tags=data.tags;db.query(ContactFriendRole).filter(ContactFriendRole.contact_id==c.id).delete();db.add_all([ContactFriendRole(contact_id=c.id,role_id=r.id) for r in roles]);[sync_team_label(db,p) for p in db.scalars(select(Project).where(Project.user_id==u.id,Project.deleted_at==None))];db.commit();return {"id":c.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":c.nickname,"tags":c.tags or [],"role_ids":[r.id for r in roles],"roles":[{"id":r.id,"name":r.name,"color":r.color} for r in roles]}
@app.delete("/api/v1/contacts/{contact_id}",status_code=204)
def delete_contact(contact_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(Contact,contact_id)
    if not c or c.owner_user_id!=u.id:raise HTTPException(404,"Контакт не найден")
    db.delete(c);db.commit()

@app.get("/api/v1/friend-roles")
def friend_roles(u=Depends(current_user),db:Session=Depends(get_db)):return [{"id":r.id,"name":r.name,"color":r.color} for r in db.scalars(select(FriendRole).where(FriendRole.owner_user_id==u.id).order_by(FriendRole.name))]
@app.post("/api/v1/friend-roles",status_code=201)
def create_friend_role(data:FriendRoleIn,u=Depends(current_user),db:Session=Depends(get_db)):
    r=FriendRole(owner_user_id=u.id,**data.model_dump());db.add(r);db.commit();return {"id":r.id,"name":r.name,"color":r.color}
@app.delete("/api/v1/friend-roles/{role_id}",status_code=204)
def delete_friend_role(role_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    r=db.get(FriendRole,role_id)
    if not r or r.owner_user_id!=u.id:raise HTTPException(404,"Роль не найдена")
    db.delete(r);db.commit()
@app.put("/api/v1/projects/{project_id}/role-rules")
def set_project_role_rule(project_id:str,data:RoleRuleIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=own(db,Project,project_id,u);role=db.get(FriendRole,data.role_id)
    if not role or role.owner_user_id!=u.id:raise HTTPException(400,"Роль не найдена")
    rule=db.scalar(select(ProjectRoleRule).where(ProjectRoleRule.project_id==p.id,ProjectRoleRule.role_id==role.id))
    if not rule:rule=ProjectRoleRule(project_id=p.id,role_id=role.id);db.add(rule)
    rule.denied_permissions=data.denied_permissions;db.commit();return {"role_id":role.id,"denied_permissions":rule.denied_permissions}
@app.put("/api/v1/channels/{channel_id}/role-rules")
def set_channel_role_rule(channel_id:str,data:RoleRuleIn,u=Depends(current_user),db:Session=Depends(get_db)):
    channel=db.get(ChatChannel,channel_id);p=own(db,Project,channel.project_id,u) if channel else None;role=db.get(FriendRole,data.role_id)
    if not p or not role or role.owner_user_id!=u.id:raise HTTPException(400,"Роль не найдена")
    rule=db.scalar(select(ChannelRoleRule).where(ChannelRoleRule.channel_id==channel.id,ChannelRoleRule.role_id==role.id))
    if not rule:rule=ChannelRoleRule(channel_id=channel.id,role_id=role.id);db.add(rule)
    rule.denied_permissions=data.denied_permissions;db.commit();return {"role_id":role.id,"denied_permissions":rule.denied_permissions}


@app.post("/api/v1/projects/{project_id}/roles",status_code=201)
def add_role(project_id:str,data:RoleIn,u=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,project_id,u,"manage_members");pos=db.scalar(select(func.count()).select_from(ProjectRole).where(ProjectRole.project_id==project_id));r=ProjectRole(project_id=project_id,position=pos,**data.model_dump());db.add(r);db.commit();return {"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions,"position":r.position}
@app.patch("/api/v1/roles/{role_id}")
def edit_role(role_id:str,data:RoleIn,u=Depends(current_user),db:Session=Depends(get_db)):
    r=db.get(ProjectRole,role_id)
    if not r:raise HTTPException(404,"Роль не найдена")
    membership(db,r.project_id,u,"manage_members")
    if r.name=="Владелец":raise HTTPException(400,"Роль владельца нельзя изменить")
    r.name=data.name;r.color=data.color;r.permissions=data.permissions;db.commit();return {"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions,"position":r.position}
@app.post("/api/v1/projects/{project_id}/members",status_code=201)
def add_member(project_id:str,data:MemberIn,u=Depends(current_user),db:Session=Depends(get_db)):
    if data.channel_id:
        channel=db.get(ChatChannel,data.channel_id)
        if not channel or channel.project_id!=project_id:raise HTTPException(400,"Канал не принадлежит проекту")
        channel_permission(db,channel,u,"manage_members")
    else:membership(db,project_id,u,"manage_members")
    person=find_user(db,data.email,data.user_nickname);role_ids=data.role_ids or ([data.role_id] if data.role_id else [])
    if not person:raise HTTPException(404,"Пользователь не найден")
    m=db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==person.id))
    if not m:m=ProjectMember(project_id=project_id,user_id=person.id,role_id=role_ids[0] if role_ids else "");db.add(m);db.flush()
    roles=set_member_roles(db,m,role_ids);db.commit();return {"id":m.id,"user_id":person.id,"name":person.name,"nickname":person.nickname,"email":person.email,"is_owner":person.id==membership(db,project_id,u).user_id,"role_id":roles[0].id,"role_ids":[r.id for r in roles],"role":roles[0].name,"role_color":roles[0].color,"roles":[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions} for r in roles]}
@app.patch("/api/v1/members/{member_id}")
def change_member(member_id:str,data:MemberIn,u=Depends(current_user),db:Session=Depends(get_db)):
    m=db.get(ProjectMember,member_id)
    if not m:raise HTTPException(404,"Участник не найден")
    p=membership(db,m.project_id,u,"manage_members")
    if m.user_id==p.user_id:raise HTTPException(400,"Роли администратора проекта изменять нельзя")
    roles=set_member_roles(db,m,data.role_ids or ([data.role_id] if data.role_id else []));db.commit();return {"id":m.id,"role_id":roles[0].id,"role_ids":[r.id for r in roles],"role":roles[0].name,"roles":[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions} for r in roles]}
@app.delete("/api/v1/members/{member_id}",status_code=204)
def remove_member(member_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    m=db.get(ProjectMember,member_id)
    if not m:raise HTTPException(404,"Участник не найден")
    p=membership(db,m.project_id,u,"manage_members")
    if m.user_id==p.user_id:raise HTTPException(400,"Нельзя удалить владельца")
    db.delete(m);db.commit()

@app.post("/api/v1/projects/{project_id}/channels",status_code=201)
def add_channel(project_id:str,data:ChannelIn,u=Depends(current_user),db:Session=Depends(get_db)):
    membership(db,project_id,u,"manage_channels");pos=db.scalar(select(func.count()).select_from(ChatChannel).where(ChatChannel.project_id==project_id));c=ChatChannel(project_id=project_id,position=pos,name=data.name,description=data.description);db.add(c)
    role=db.scalar(select(ProjectRole).where(ProjectRole.project_id==project_id,ProjectRole.name=="Участник")) or db.scalar(select(ProjectRole).where(ProjectRole.project_id==project_id).order_by(ProjectRole.position))
    allowed=set(db.scalars(select(Contact.contact_user_id).where(Contact.owner_user_id==u.id,Contact.contact_user_id.in_(data.contact_user_ids),Contact.status=="accepted"))) if data.contact_user_ids else set()
    if len(allowed)!=len(set(data.contact_user_ids)):raise HTTPException(400,"Один из выбранных пользователей не является другом")
    for user_id in allowed:
        member=db.scalar(select(ProjectMember).where(ProjectMember.project_id==project_id,ProjectMember.user_id==user_id))
        if not member:member=ProjectMember(project_id=project_id,user_id=user_id,role_id=role.id);db.add(member);db.flush();db.add(ProjectMemberRole(member_id=member.id,role_id=role.id))
    db.commit();return {"id":c.id,"name":c.name,"description":c.description,"position":c.position,"contacts_added":len(allowed)}
@app.patch("/api/v1/channels/{channel_id}")
def edit_channel(channel_id:str,data:ChannelIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    membership(db,c.project_id,u,"manage_channels");c.name=data.name;c.description=data.description;db.commit();return {"id":c.id,"name":c.name,"description":c.description,"position":c.position}
@app.delete("/api/v1/channels/{channel_id}",status_code=204)
def delete_channel(channel_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    membership(db,c.project_id,u,"manage_channels")
    count=db.scalar(select(func.count()).select_from(ChatChannel).where(ChatChannel.project_id==c.project_id))
    if count<=1:raise HTTPException(400,"Нельзя удалить последний канал проекта")
    db.delete(c);db.commit()
@app.get("/api/v1/channels/{channel_id}/messages")
def messages(channel_id:str,before:datetime|None=None,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    channel_permission(db,c,u,"view");q=select(ChatMessage).where(ChatMessage.channel_id==channel_id,ChatMessage.deleted_at==None)
    if before:q=q.where(ChatMessage.created_at<before)
    result=[]
    for m in reversed(list(db.scalars(q.order_by(ChatMessage.created_at.desc()).limit(100)))):
        author=db.get(User,m.user_id);task=db.get(Task,m.attached_task_id) if m.attached_task_id else None;result.append({"id":m.id,"content":m.content,"created_at":dt(m.created_at),"author":{"id":author.id,"name":author.name},"task":{"id":task.id,"title":task.title,"priority":task.priority,"status":task.status} if task and not task.deleted_at else None})
    return result
@app.post("/api/v1/channels/{channel_id}/messages",status_code=201)
def send_message(channel_id:str,data:MessageIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    channel_permission(db,c,u,"send_messages")
    if not data.content.strip() and not data.attached_task_id:raise HTTPException(400,"Сообщение пустое")
    task=None
    if data.attached_task_id:
        task=db.get(Task,data.attached_task_id)
        if not task or task.project_id!=c.project_id or task.deleted_at:raise HTTPException(400,"Задача не принадлежит проекту")
    m=ChatMessage(channel_id=channel_id,user_id=u.id,content=data.content.strip(),attached_task_id=data.attached_task_id);db.add(m);db.commit();return {"id":m.id,"content":m.content,"created_at":dt(m.created_at),"author":{"id":u.id,"name":u.name},"task":{"id":task.id,"title":task.title,"priority":task.priority,"status":task.status} if task else None}
@app.get("/api/v1/health")
def health():return {"status":"ok","database":engine.dialect.name}

@app.get("/api/v1/events")
async def events(request:Request,u=Depends(current_user)):
    async def stream():
        previous=None
        yield "event: ready\ndata: connected\n\n"
        while not await request.is_disconnected():
            with Session(engine) as db:current=realtime_revision(db,u.id)
            if previous is not None and current!=previous:yield "event: change\ndata: updated\n\n"
            else:yield ": heartbeat\n\n"
            previous=current
            await asyncio.sleep(2)
    return StreamingResponse(stream(),media_type="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

from .ai.router import make_router as make_ai_router
from .ai.gateway import PlannerGateway
app.include_router(make_ai_router(PlannerGateway(membership,create_task_service,patch_task_service,create_project_service)))

root=Path(__file__).resolve().parents[2];app.mount("/",StaticFiles(directory=root,html=True),name="frontend")
