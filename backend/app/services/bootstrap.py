import os,sqlite3
from datetime import datetime
from pathlib import Path
from sqlalchemy import select,func
from ..database import Base,engine,SessionLocal,DEFAULT_DB_PATH
from ..migrations import migrate_legacy
from ..models import User,Project,KanbanColumn,ProjectRole,ProjectMember,ProjectMemberRole,ChatChannel

ROLE_DEFINITIONS=[("Владелец","#ff6b45",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Администратор","#e59b35",["view","edit_tasks","send_messages","manage_channels","manage_members"]),("Участник","#5577e7",["view","edit_tasks","send_messages"]),("Наблюдатель","#7b818b",["view"])]

def backup_local_database():
    if os.getenv("DATABASE_URL") or not DEFAULT_DB_PATH.exists() or not DEFAULT_DB_PATH.stat().st_size:return
    backup_dir=DEFAULT_DB_PATH.parent/"backups";backup_dir.mkdir(exist_ok=True)
    target=backup_dir/f"planner-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.db"
    with sqlite3.connect(DEFAULT_DB_PATH) as source,sqlite3.connect(target) as destination:source.backup(destination)

def initialize_database():
    backup_local_database();migrate_legacy();Base.metadata.create_all(engine)
    with SessionLocal() as db:
        used=set()
        for user in db.scalars(select(User).order_by(User.created_at)):
            base=(user.nickname or user.email.split("@")[0]).lower();candidate=base;suffix=2
            while candidate in used:candidate=f"{base}{suffix}";suffix+=1
            user.nickname=candidate;used.add(candidate)
        for project in db.scalars(select(Project).where(Project.deleted_at==None)):
            if not db.scalar(select(func.count()).select_from(KanbanColumn).where(KanbanColumn.project_id==project.id)):
                db.add_all([KanbanColumn(project_id=project.id,name=name,position=i) for i,name in enumerate(["Идеи","Запланировано","В работе","Готово"])])
            roles=list(db.scalars(select(ProjectRole).where(ProjectRole.project_id==project.id)))
            if not roles:roles=[ProjectRole(project_id=project.id,name=name,color=color,permissions=permissions,position=i) for i,(name,color,permissions) in enumerate(ROLE_DEFINITIONS)];db.add_all(roles);db.flush()
            admin=next((role for role in roles if role.name=="Администратор"),roles[0]);member=db.scalar(select(ProjectMember).where(ProjectMember.project_id==project.id,ProjectMember.user_id==project.user_id))
            if not member:member=ProjectMember(project_id=project.id,user_id=project.user_id,role_id=admin.id);db.add(member);db.flush()
            if not db.scalar(select(ProjectMemberRole).where(ProjectMemberRole.member_id==member.id,ProjectMemberRole.role_id==admin.id)):db.add(ProjectMemberRole(member_id=member.id,role_id=admin.id))
            if not db.scalar(select(ChatChannel).where(ChatChannel.project_id==project.id)):db.add(ChatChannel(project_id=project.id,name="общий",description="Основной канал проекта",position=0))
        db.flush()
        for member in db.scalars(select(ProjectMember)):
            if not db.scalar(select(ProjectMemberRole).where(ProjectMemberRole.member_id==member.id,ProjectMemberRole.role_id==member.role_id)):db.add(ProjectMemberRole(member_id=member.id,role_id=member.role_id))
        db.commit()
