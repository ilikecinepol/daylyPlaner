from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from ..models import Reminder,Task

DEFAULT_NOTIFICATION_SETTINGS={
    "friend_incoming":{"enabled":True,"channel":"bell","priority":"normal"},
    "friend_outgoing":{"enabled":True,"channel":"bell","priority":"normal"},
    "task_assigned":{"enabled":True,"channel":"bell","priority":"high"},
    "task_self_assigned":{"enabled":True,"channel":"bell","priority":"high"},
    "deadline_soon":{"enabled":True,"channel":"sound","priority":"high"},
    "urgent_task":{"enabled":True,"channel":"alarm","priority":"urgent"},
}

def notification_settings(user):
    stored=user.notification_settings or {}
    return {event:{**rule,**stored.get(event,{})} for event,rule in DEFAULT_NOTIFICATION_SETTINGS.items()}

def filter_notification_feed(user,items):
    settings=notification_settings(user);cleared=user.notifications_cleared_at
    if cleared and cleared.tzinfo is None:cleared=cleared.replace(tzinfo=timezone.utc)
    result=[]
    for item in items:
        rule=settings.get(item["type"],{"enabled":True,"channel":"bell","priority":"normal"})
        created=datetime.fromisoformat(item["created_at"].replace("Z","+00:00")) if item.get("created_at") else None
        if not rule.get("enabled",True) or cleared and created and created<=cleared:continue
        result.append({**item,"channel":rule["channel"],"priority":rule["priority"]})
    return result

def due_reminders(db,user_id:str,now:datetime|None=None,mark_sent:bool=True):
    current=now or datetime.now(timezone.utc);result=[]
    rows=db.execute(select(Reminder,Task).join(Task,Reminder.task_id==Task.id).where(Task.user_id==user_id,Task.deleted_at==None,Task.completed_at==None,Reminder.sent_at==None,Task.start_at!=None))
    for reminder,task in rows:
        start=task.start_at.replace(tzinfo=timezone.utc) if task.start_at.tzinfo is None else task.start_at
        if start-timedelta(minutes=reminder.offset_minutes)<=current<=start:
            result.append({"id":reminder.id,"task_id":task.id,"title":task.title,"start_at":start,"offset_minutes":reminder.offset_minutes,"channel":reminder.channel})
            if mark_sent:reminder.sent_at=current
    if mark_sent and result:db.commit()
    return result
