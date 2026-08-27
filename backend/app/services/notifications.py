from datetime import datetime,timezone,timedelta
from sqlalchemy import select
from ..models import Reminder,Task

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
