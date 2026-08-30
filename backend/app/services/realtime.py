from datetime import datetime,timezone
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from ..models import Goal, ActivityLog, ChatChannel, ChatMessage, Contact, Project, ProjectMember, Task, TaskTemplate


def _stamp(value):
    return value.isoformat() if value else ""


def revision(db:Session,user_id:str):
    project_ids=list(db.scalars(select(ProjectMember.project_id).join(Project,Project.id==ProjectMember.project_id).where(ProjectMember.user_id==user_id,Project.deleted_at==None)))
    task_filter=or_(Task.user_id==user_id,Task.project_id.in_(project_ids))
    task_count,task_updated=db.execute(select(func.count(Task.id),func.max(Task.updated_at)).where(task_filter)).one()
    project_count,project_updated=db.execute(select(func.count(Project.id),func.max(Project.updated_at)).where(Project.id.in_(project_ids),Project.deleted_at==None)).one() if project_ids else (0,None)
    channel_ids=list(db.scalars(select(ChatChannel.id).where(ChatChannel.project_id.in_(project_ids)))) if project_ids else []
    message_count,message_updated=db.execute(select(func.count(ChatMessage.id),func.max(ChatMessage.updated_at)).where(ChatMessage.channel_id.in_(channel_ids))).one() if channel_ids else (0,None)
    activity_count,activity_updated=db.execute(select(func.count(ActivityLog.id),func.max(ActivityLog.created_at)).where(ActivityLog.user_id==user_id)).one()
    contact_count,contact_updated=db.execute(select(func.count(Contact.id),func.max(Contact.created_at)).where(or_(Contact.owner_user_id==user_id,Contact.contact_user_id==user_id))).one()
    template_count,template_updated=db.execute(select(func.count(TaskTemplate.id),func.max(TaskTemplate.updated_at)).where(TaskTemplate.user_id==user_id,TaskTemplate.deleted_at==None)).one()
    goal_count,goal_updated=db.execute(select(func.count(Goal.id),func.max(Goal.updated_at)).where(Goal.user_id==user_id)).one()
    minute=datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    return "|".join(map(str,[goal_count,_stamp(goal_updated),task_count,_stamp(task_updated),project_count,_stamp(project_updated),message_count,_stamp(message_updated),activity_count,_stamp(activity_updated),contact_count,_stamp(contact_updated),template_count,_stamp(template_updated),minute]))
