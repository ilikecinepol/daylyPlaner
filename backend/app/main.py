import os
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Query
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session
from .database import Base,engine,get_db
from .models import User,Project,Task,TaskTemplate,KanbanColumn,Reminder,ActivityLog,Contact,ProjectRole,ProjectMember,ProjectMemberRole,ChatChannel,ChatMessage
from .schemas import Credentials,TaskIn,TaskPatch,ProjectIn,ColumnIn,TemplateIn,ContactIn,RoleIn,MemberIn,ChannelIn,MessageIn
from .security import hash_password,verify_password
from .services.recurrence import next_occurrence
from .services.notifications import due_reminders
from .services.bootstrap import initialize_database
from .api.dependencies import set_session_cookie as cookie,current_user,iso_utc as dt
from .api.integrations import router as integrations_router

@asynccontextmanager
async def lifespan(_app:FastAPI):
    initialize_database()
    yield

app=FastAPI(title="План API",version="1.0.0",docs_url="/api/docs",openapi_url="/api/openapi.json",lifespan=lifespan)
app.include_router(integrations_router)

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
    return p
def accessible_projects(db,user):return list(db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id==user.id)))
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
def task_out(db,t):
    reminders=list(db.scalars(select(Reminder).where(Reminder.task_id==t.id)))
    return {"id":t.id,"title":t.title,"description":t.description,"status":t.status,"priority":t.priority,"project_id":t.project_id,"column_id":t.column_id,"start_at":dt(t.start_at),"due_at":dt(t.due_at),"duration_minutes":t.duration_minutes,"all_day":t.all_day,"location":t.location,"tags":t.tags or [],"mentions":t.mentions or [],"recurrence_rule":t.recurrence_rule or "","reminder_offsets":[r.offset_minutes for r in reminders],"completed_at":dt(t.completed_at),"sync_version":t.sync_version,"created_at":dt(t.created_at),"updated_at":dt(t.updated_at)}
def project_out(db,p):
    roles=list(db.scalars(select(ProjectRole).where(ProjectRole.project_id==p.id).order_by(ProjectRole.position)));members=[]
    for m in db.scalars(select(ProjectMember).where(ProjectMember.project_id==p.id)):
        user=db.get(User,m.user_id);member_roles=[db.get(ProjectRole,x.role_id) for x in db.scalars(select(ProjectMemberRole).where(ProjectMemberRole.member_id==m.id))];member_roles=[r for r in member_roles if r]
        if not member_roles:
            legacy=db.get(ProjectRole,m.role_id)
            if legacy:member_roles=[legacy]
        primary=member_roles[0];serialized=[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions} for r in member_roles]
        members.append({"id":m.id,"user_id":m.user_id,"name":user.name,"nickname":user.nickname,"email":user.email,"is_owner":m.user_id==p.user_id,"role_id":primary.id,"role_ids":[r.id for r in member_roles],"role":primary.name,"role_color":primary.color,"roles":serialized})
    return {"id":p.id,"name":p.name,"description":p.description,"color":p.color,"priority":p.priority,"team_label":p.team_label or "","owner_id":p.user_id,"columns":[{"id":c.id,"name":c.name,"position":c.position} for c in db.scalars(select(KanbanColumn).where(KanbanColumn.project_id==p.id).order_by(KanbanColumn.position))],"roles":[{"id":r.id,"name":r.name,"color":r.color,"permissions":r.permissions,"position":r.position} for r in roles],"members":members,"channels":[{"id":c.id,"name":c.name,"description":c.description,"position":c.position} for c in db.scalars(select(ChatChannel).where(ChatChannel.project_id==p.id).order_by(ChatChannel.position))]}
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
@app.get("/api/v1/auth/me")
def me(u=Depends(current_user)): return {"id":u.id,"email":u.email,"nickname":u.nickname,"name":u.name,"timezone":u.timezone}

@app.get("/api/v1/tasks")
def tasks(q:str|None=None,status:str|None=None,priority:str|None=None,project:str|None=None,from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,u=Depends(current_user),db:Session=Depends(get_db)):
    shared=accessible_projects(db,u);s=select(Task).where(or_(Task.user_id==u.id,Task.project_id.in_(shared)),Task.deleted_at==None)
    if q:s=s.where(or_(Task.title.ilike(f"%{q}%"),Task.description.ilike(f"%{q}%"),Task.location.ilike(f"%{q}%")))
    if status:s=s.where(Task.status==status)
    if priority:s=s.where(Task.priority==priority)
    if project:s=s.where(Task.project_id==project)
    if from_:s=s.where(Task.start_at>=from_)
    if to:s=s.where(Task.start_at<=to)
    return [task_out(db,t) for t in db.scalars(s.order_by(Task.start_at.asc().nullslast(),Task.priority))]
@app.post("/api/v1/tasks",status_code=201)
def create_task(data:TaskIn,u=Depends(current_user),db:Session=Depends(get_db)):
    if data.project_id:membership(db,data.project_id,u,"edit_tasks")
    values=data.model_dump(exclude={"reminder_offsets"});t=Task(user_id=u.id,**values)
    db.add(t);db.flush();[db.add(Reminder(task_id=t.id,offset_minutes=x)) for x in data.reminder_offsets];log(db,u,"task_created",t.id);db.commit();return task_out(db,t)
@app.get("/api/v1/tasks/{task_id}")
def get_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at or (t.user_id!=u.id and (not t.project_id or t.project_id not in accessible_projects(db,u))):raise HTTPException(404,"Задача не найдена")
    return task_out(db,t)
@app.patch("/api/v1/tasks/{task_id}")
def patch_task(task_id:str,data:TaskPatch,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at:raise HTTPException(404,"Задача не найдена")
    if t.user_id!=u.id:membership(db,t.project_id,u,"edit_tasks")
    patch=data.model_dump(exclude_unset=True);expected=patch.pop("sync_version",None)
    if expected is not None and expected!=t.sync_version: raise HTTPException(409,"Задача была изменена на другом устройстве")
    offsets=patch.pop("reminder_offsets",None);before={k:getattr(t,k) for k in patch}
    for k,v in patch.items(): setattr(t,k,v)
    if "status" in patch and patch["status"]=="completed":
        t.completed_at=datetime.now(timezone.utc)
        nxt=next_occurrence(t.start_at,t.recurrence_rule)
        if nxt and not db.scalar(select(Task).where(Task.user_id==u.id,Task.title==t.title,Task.start_at==nxt,Task.deleted_at==None)):
            child=Task(user_id=u.id,project_id=t.project_id,column_id=t.column_id,title=t.title,description=t.description,status="planned",priority=t.priority,start_at=nxt,due_at=(t.due_at+(nxt-t.start_at)) if t.due_at else None,duration_minutes=t.duration_minutes,all_day=t.all_day,location=t.location,tags=t.tags,mentions=t.mentions,recurrence_rule=t.recurrence_rule);db.add(child);db.flush();[db.add(Reminder(task_id=child.id,offset_minutes=r.offset_minutes,channel=r.channel)) for r in db.scalars(select(Reminder).where(Reminder.task_id==t.id))]
    elif "status" in patch:t.completed_at=None
    t.sync_version=(t.sync_version or 0)+1
    if offsets is not None:db.query(Reminder).filter(Reminder.task_id==t.id).delete();[db.add(Reminder(task_id=t.id,offset_minutes=x)) for x in offsets]
    log(db,u,"task_updated",t.id,{k:[str(before[k]),str(v)] for k,v in patch.items() if before[k]!=v});db.commit();return task_out(db,t)
@app.delete("/api/v1/tasks/{task_id}",status_code=204)
def delete_task(task_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    t=db.get(Task,task_id)
    if not t or t.deleted_at:raise HTTPException(404,"Задача не найдена")
    if t.user_id!=u.id:membership(db,t.project_id,u,"edit_tasks")
    t.deleted_at=datetime.now(timezone.utc);t.sync_version+=1;log(db,u,"task_deleted",t.id);db.commit()

@app.get("/api/v1/calendar")
def calendar(from_:datetime=Query(alias="from"),to:datetime=Query(),u=Depends(current_user),db:Session=Depends(get_db)):
    return [task_out(db,t) for t in db.scalars(select(Task).where(Task.user_id==u.id,Task.deleted_at==None,Task.start_at>=from_,Task.start_at<=to).order_by(Task.start_at))]

@app.get("/api/v1/projects")
def projects(u=Depends(current_user),db:Session=Depends(get_db)): return [project_out(db,p) for p in db.scalars(select(Project).where(Project.id.in_(accessible_projects(db,u)),Project.deleted_at==None))]
@app.post("/api/v1/projects",status_code=201)
def create_project(data:ProjectIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=Project(user_id=u.id,**data.model_dump());db.add(p);db.flush();[db.add(KanbanColumn(project_id=p.id,name=n,position=i)) for i,n in enumerate(["Идеи","Запланировано","В работе","Готово"])];roles=[ProjectRole(project_id=p.id,name=n,color=c,permissions=perms,position=i) for i,(n,c,perms) in enumerate([("Владелец","#ff6b45",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Администратор","#e59b35",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Участник","#5577e7",["view","edit_tasks","send_messages"]),("Наблюдатель","#7b818b",["view"])])];db.add_all(roles);db.flush();admin=next(r for r in roles if r.name=="Администратор");owner=ProjectMember(project_id=p.id,user_id=u.id,role_id=admin.id);db.add(owner);db.flush();db.add(ProjectMemberRole(member_id=owner.id,role_id=admin.id));db.add(ChatChannel(project_id=p.id,name="общий",description="Основной канал проекта",position=0));sync_team_label(db,p);db.commit();return project_out(db,p)
@app.patch("/api/v1/projects/{project_id}")
def patch_project(project_id:str,data:ProjectIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=own(db,Project,project_id,u);[setattr(p,k,v) for k,v in data.model_dump().items()];sync_team_label(db,p);db.commit();return project_out(db,p)
@app.delete("/api/v1/projects/{project_id}",status_code=204)
def delete_project(project_id:str,u=Depends(current_user),db:Session=Depends(get_db)):p=own(db,Project,project_id,u);p.deleted_at=datetime.now(timezone.utc);db.commit()
@app.post("/api/v1/projects/{project_id}/columns",status_code=201)
def create_column(project_id:str,data:ColumnIn,u=Depends(current_user),db:Session=Depends(get_db)):
    p=membership(db,project_id,u,"manage_channels");pos=data.position if data.position is not None else db.scalar(select(func.count()).select_from(KanbanColumn).where(KanbanColumn.project_id==p.id));c=KanbanColumn(project_id=p.id,name=data.name,position=pos);db.add(c);db.commit();return {"id":c.id,"name":c.name,"position":c.position}
@app.patch("/api/v1/columns/{column_id}")
def patch_column(column_id:str,data:ColumnIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(KanbanColumn,column_id);p=own(db,Project,c.project_id,u) if c else None
    if not c:raise HTTPException(404,"Колонка не найдена")
    c.name=data.name;c.position=data.position if data.position is not None else c.position;db.commit();return {"id":c.id,"name":c.name,"position":c.position}

@app.get("/api/v1/templates")
def templates(u=Depends(current_user),db:Session=Depends(get_db)):return [{"id":t.id,"name":t.name,"icon":t.icon,"description":t.description,"duration":t.duration,"priority":t.priority,"location":t.location,"project_id":t.project_id,"reminders":t.reminders or []} for t in db.scalars(select(TaskTemplate).where(TaskTemplate.user_id==u.id,TaskTemplate.deleted_at==None))]
@app.post("/api/v1/templates",status_code=201)
def create_template(data:TemplateIn,u=Depends(current_user),db:Session=Depends(get_db)):t=TaskTemplate(user_id=u.id,**data.model_dump());db.add(t);db.commit();return {"id":t.id,**data.model_dump()}
@app.get("/api/v1/activity")
def activity(u=Depends(current_user),db:Session=Depends(get_db)):return [{"id":x.id,"task_id":x.task_id,"action":x.action,"changes":x.changes,"created_at":dt(x.created_at)} for x in db.scalars(select(ActivityLog).where(ActivityLog.user_id==u.id).order_by(ActivityLog.created_at.desc()).limit(100))]
@app.get("/api/v1/notifications")
def notifications(u=Depends(current_user),db:Session=Depends(get_db)):
    return [{**item,"start_at":dt(item["start_at"])} for item in due_reminders(db,u.id)]

@app.get("/api/v1/contacts")
def contacts(u=Depends(current_user),db:Session=Depends(get_db)):
    result=[]
    for c in db.scalars(select(Contact).where(Contact.owner_user_id==u.id,Contact.status=="accepted")):
        person=db.get(User,c.contact_user_id);result.append({"id":c.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":c.nickname,"tags":c.tags or []})
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
    if not c:c=Contact(owner_user_id=u.id,contact_user_id=person.id,nickname=data.nickname,tags=data.tags,status="accepted");db.add(c)
    else:c.nickname=data.nickname;c.tags=data.tags;c.status="accepted"
    if not db.scalar(select(Contact).where(Contact.owner_user_id==person.id,Contact.contact_user_id==u.id)):db.add(Contact(owner_user_id=person.id,contact_user_id=u.id,status="accepted"))
    db.flush();[sync_team_label(db,p) for p in db.scalars(select(Project).where(Project.user_id==u.id,Project.deleted_at==None))];db.commit();return {"id":c.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":c.nickname,"tags":c.tags or []}
@app.patch("/api/v1/contacts/{contact_id}")
def edit_contact(contact_id:str,data:ContactIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(Contact,contact_id)
    if not c or c.owner_user_id!=u.id:raise HTTPException(404,"Контакт не найден")
    person=db.get(User,c.contact_user_id)
    if data.email and data.email.lower()!=person.email.lower():raise HTTPException(400,"Email контакта менять нельзя")
    c.nickname=data.nickname;c.tags=data.tags;[sync_team_label(db,p) for p in db.scalars(select(Project).where(Project.user_id==u.id,Project.deleted_at==None))];db.commit();return {"id":c.id,"user_id":person.id,"name":person.name,"email":person.email,"user_nickname":person.nickname,"nickname":c.nickname,"tags":c.tags or []}
@app.delete("/api/v1/contacts/{contact_id}",status_code=204)
def delete_contact(contact_id:str,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(Contact,contact_id)
    if not c or c.owner_user_id!=u.id:raise HTTPException(404,"Контакт не найден")
    db.delete(c);db.commit()

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
    membership(db,project_id,u,"manage_members");person=find_user(db,data.email,data.user_nickname);role_ids=data.role_ids or ([data.role_id] if data.role_id else [])
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
    membership(db,project_id,u,"manage_channels");pos=db.scalar(select(func.count()).select_from(ChatChannel).where(ChatChannel.project_id==project_id));c=ChatChannel(project_id=project_id,position=pos,**data.model_dump());db.add(c);db.commit();return {"id":c.id,"name":c.name,"description":c.description,"position":c.position}
@app.get("/api/v1/channels/{channel_id}/messages")
def messages(channel_id:str,before:datetime|None=None,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    membership(db,c.project_id,u);q=select(ChatMessage).where(ChatMessage.channel_id==channel_id,ChatMessage.deleted_at==None)
    if before:q=q.where(ChatMessage.created_at<before)
    result=[]
    for m in reversed(list(db.scalars(q.order_by(ChatMessage.created_at.desc()).limit(100)))):
        author=db.get(User,m.user_id);task=db.get(Task,m.attached_task_id) if m.attached_task_id else None;result.append({"id":m.id,"content":m.content,"created_at":dt(m.created_at),"author":{"id":author.id,"name":author.name},"task":{"id":task.id,"title":task.title,"priority":task.priority,"status":task.status} if task and not task.deleted_at else None})
    return result
@app.post("/api/v1/channels/{channel_id}/messages",status_code=201)
def send_message(channel_id:str,data:MessageIn,u=Depends(current_user),db:Session=Depends(get_db)):
    c=db.get(ChatChannel,channel_id)
    if not c:raise HTTPException(404,"Канал не найден")
    membership(db,c.project_id,u,"send_messages")
    if not data.content.strip() and not data.attached_task_id:raise HTTPException(400,"Сообщение пустое")
    task=None
    if data.attached_task_id:
        task=db.get(Task,data.attached_task_id)
        if not task or task.project_id!=c.project_id or task.deleted_at:raise HTTPException(400,"Задача не принадлежит проекту")
    m=ChatMessage(channel_id=channel_id,user_id=u.id,content=data.content.strip(),attached_task_id=data.attached_task_id);db.add(m);db.commit();return {"id":m.id,"content":m.content,"created_at":dt(m.created_at),"author":{"id":u.id,"name":u.name},"task":{"id":task.id,"title":task.title,"priority":task.priority,"status":task.status} if task else None}
@app.get("/api/v1/health")
def health():return {"status":"ok","database":engine.dialect.name}

root=Path(__file__).resolve().parents[2];app.mount("/",StaticFiles(directory=root,html=True),name="frontend")
