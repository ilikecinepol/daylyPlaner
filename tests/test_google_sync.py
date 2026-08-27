from datetime import datetime,timezone,timedelta
from sqlalchemy import create_engine,select
from sqlalchemy.orm import Session
from app.database import Base
from app.models import User,Task,CalendarConnection,CalendarEventLink,ExternalCalendarEvent
from app.services import calendar_sync
from app import google_calendar as google

def setup_db():
    engine=create_engine("sqlite:///:memory:");Base.metadata.create_all(engine);return Session(engine,expire_on_commit=False)

def test_expired_token_refresh_preserves_refresh_token(monkeypatch):
    with setup_db() as db:
        c=CalendarConnection(user_id="u",access_token_encrypted=google.encrypt("old"),refresh_token_encrypted=google.encrypt("refresh"),token_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1));before=c.refresh_token_encrypted
        monkeypatch.setattr(google,"refresh",lambda value:{"access_token":"new","expires_in":3600})
        assert calendar_sync.access_token(c)=="new";assert c.refresh_token_encrypted==before

def test_invalid_refresh_requires_reauthorization(monkeypatch):
    import httpx,pytest
    c=CalendarConnection(user_id="u",access_token_encrypted=google.encrypt("old"),refresh_token_encrypted=google.encrypt("bad"),token_expires_at=datetime.now(timezone.utc)-timedelta(seconds=1))
    monkeypatch.setattr(google,"refresh",lambda value:(_ for _ in ()).throw(httpx.HTTPError("invalid_grant")))
    with pytest.raises(ValueError):calendar_sync.access_token(c)
    assert c.status=="reauthorization_required"

def test_pull_before_push_conflict_external_and_local_delete(monkeypatch):
    calls=[];now=datetime.now(timezone.utc)
    with setup_db() as db:
        user=User(email="g@example.com",password_hash="x",name="G");db.add(user);db.flush();connection=CalendarConnection(user_id=user.id,access_token_encrypted=google.encrypt("token"),refresh_token_encrypted=google.encrypt("refresh"),token_expires_at=now+timedelta(hours=1));db.add(connection);task=Task(user_id=user.id,title="Local",start_at=now,updated_at=now-timedelta(hours=1));db.add(task);db.flush();link=CalendarEventLink(task_id=task.id,calendar_connection_id=connection.id,external_event_id="owned",last_synced_at=now-timedelta(hours=2));db.add(link);deleted=Task(user_id=user.id,title="Deleted",start_at=now,deleted_at=now);db.add(deleted);db.flush();db.add(CalendarEventLink(task_id=deleted.id,calendar_connection_id=connection.id,external_event_id="delete-me"));db.commit()
        events=[{"id":"owned","updated":now.isoformat(),"summary":"Remote wins","start":{"dateTime":now.isoformat()},"end":{"dateTime":(now+timedelta(hours=1)).isoformat()},"extendedProperties":{"private":{"plan_task_id":task.id}}},{"id":"external","updated":now.isoformat(),"summary":"External","start":{"dateTime":now.isoformat()},"end":{"dateTime":(now+timedelta(hours=1)).isoformat()}}]
        monkeypatch.setattr(google,"list_events",lambda *a,**k:(calls.append("pull") or events));monkeypatch.setattr(google,"upsert_event",lambda *a,**k:(calls.append("push") or {"id":"owned","updated":now.isoformat()}));monkeypatch.setattr(google,"delete_event",lambda *a,**k:calls.append("delete"))
        result=calendar_sync.sync(db,connection,user.id)
        assert task.title=="Remote wins";assert calls[0]=="pull";assert "delete" in calls;assert result["external"]==1
        assert db.scalar(select(ExternalCalendarEvent).where(ExternalCalendarEvent.external_event_id=="external")) is not None
