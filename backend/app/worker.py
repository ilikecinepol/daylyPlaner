"""One-shot background jobs; invoke from cron/systemd/Kubernetes CronJob."""
from sqlalchemy import select
from .database import SessionLocal
from .models import User
from .services.notifications import due_reminders

def run_reminders():
    sent=0
    with SessionLocal() as db:
        for user_id in db.scalars(select(User.id).where(User.deleted_at==None)):
            sent+=len(due_reminders(db,user_id))
    return sent

if __name__=="__main__":
    print(f"processed reminders: {run_reminders()}")
