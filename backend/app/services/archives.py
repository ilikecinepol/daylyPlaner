from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import ActivityLog, Task, User

def _aware(value):
    if value is None:return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

def _should_archive(task, user, current):
    policy=user.completed_task_archive_policy or "never"
    completed=_aware(task.completed_at)
    if not completed or policy=="never":return False
    if policy=="immediate":return completed<=current
    if policy=="after_days":return completed<=current-timedelta(days=max(1,user.completed_task_archive_days or 7))
    if policy=="end_of_day":
        try:zone=ZoneInfo(user.timezone or "UTC")
        except ZoneInfoNotFoundError:zone=timezone.utc
        return completed.astimezone(zone).date()<current.astimezone(zone).date()
    return False

def process_archives(db:Session,now=None):
    current=_aware(now) or datetime.now(timezone.utc)
    users={user.id:user for user in db.scalars(select(User).where(User.deleted_at==None,User.completed_task_archive_policy!="never"))}
    if not users:return {"auto_archived":0}
    count=0
    tasks=db.scalars(select(Task).where(Task.user_id.in_(list(users)),Task.status=="completed",Task.completed_at!=None,Task.archived_at==None,Task.deleted_at==None))
    for task in tasks:
        if not _should_archive(task,users[task.user_id],current):continue
        task.archived_at=current;task.sync_version=(task.sync_version or 0)+1
        db.add(ActivityLog(user_id=task.user_id,task_id=task.id,action="task_auto_archived",changes={"policy":users[task.user_id].completed_task_archive_policy}))
        count+=1
    if count:db.commit()
    return {"auto_archived":count}
