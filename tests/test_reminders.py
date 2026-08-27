from datetime import datetime,timezone,timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.database import Base
from app.models import User,Task,Reminder
from app.services.notifications import due_reminders

def test_due_reminder_is_marked_and_not_repeated():
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);now=datetime.now(timezone.utc)
    with Session(engine,expire_on_commit=False) as db:
        user=User(email="r@example.com",password_hash="x",name="R");db.add(user);db.flush();task=Task(user_id=user.id,title="Soon",start_at=now+timedelta(minutes=5));db.add(task);db.flush();reminder=Reminder(task_id=task.id,offset_minutes=10);db.add(reminder);db.commit()
        assert len(due_reminders(db,user.id,now))==1
        assert reminder.sent_at is not None
        assert due_reminders(db,user.id,now)==[]

def test_future_reminder_is_not_due():
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);now=datetime.now(timezone.utc)
    with Session(engine) as db:
        user=User(email="f@example.com",password_hash="x",name="F");db.add(user);db.flush();task=Task(user_id=user.id,title="Later",start_at=now+timedelta(hours=2));db.add(task);db.flush();db.add(Reminder(task_id=task.id,offset_minutes=10));db.commit()
        assert due_reminders(db,user.id,now)==[]
