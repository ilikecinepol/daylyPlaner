from datetime import datetime,timezone,timedelta
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.database import SessionLocal
from app.models import User,CalendarConnection,ExternalCalendarEvent

def test_external_events_are_read_only_and_scoped_to_current_user():
    with TestClient(app) as client:
        response=client.post("/api/v1/auth/register",json={"email":"external-api@example.com","password":"StrongPass123","name":"Calendar"})
        user_id=response.json()["id"];now=datetime.now(timezone.utc)
        with SessionLocal() as db:
            connection=CalendarConnection(user_id=user_id,provider="google");db.add(connection);db.flush()
            db.add(ExternalCalendarEvent(calendar_connection_id=connection.id,external_event_id="foreign-1",title="External meeting",start_at=now,end_at=now+timedelta(hours=1)));db.commit()
        events=client.get("/api/v1/external-calendar-events").json()
        assert len(events)==1;assert events[0]["title"]=="External meeting";assert events[0]["read_only"] is True
        assert client.post("/api/v1/external-calendar-events",json={}).status_code==405
