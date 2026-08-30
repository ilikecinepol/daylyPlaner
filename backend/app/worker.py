"""One-shot background jobs; invoke from cron/systemd/Kubernetes CronJob."""
from sqlalchemy import select
from .database import SessionLocal
from .models import User
from .services.notifications import due_reminders
from .services.deadlines import process_deadlines
from .services.archives import process_archives

def run_reminders():
    sent=0
    with SessionLocal() as db:
        for user_id in db.scalars(select(User.id).where(User.deleted_at==None)):
            sent+=len(due_reminders(db,user_id))
    return sent

def run_jobs():
    with SessionLocal() as db:
        deadlines=process_deadlines(db)
        archives=process_archives(db)
    return {"reminders":run_reminders(),**deadlines,**archives}

if __name__=="__main__":
    print(f"processed jobs: {run_jobs()}")
