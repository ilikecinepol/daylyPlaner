from datetime import datetime,timezone,timedelta
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from .. import google_calendar as google
from ..database import get_db
from ..models import User,CalendarConnection,ExternalCalendarEvent
from ..security import decode_token
from ..services.calendar_sync import sync as sync_google
from .dependencies import current_user,iso_utc

router=APIRouter(prefix="/api/v1",tags=["calendar integrations"])

@router.get("/calendar-connections")
def connections(user=Depends(current_user),db:Session=Depends(get_db)):
    return [{"id":item.id,"provider":item.provider,"account":item.external_account_id,"status":item.status,"last_synced_at":iso_utc(item.last_synced_at)} for item in db.scalars(select(CalendarConnection).where(CalendarConnection.user_id==user.id,CalendarConnection.deleted_at==None))]

@router.get("/external-calendar-events")
def external_events(from_:datetime|None=Query(None,alias="from"),to:datetime|None=None,user=Depends(current_user),db:Session=Depends(get_db)):
    connection_ids=select(CalendarConnection.id).where(CalendarConnection.user_id==user.id,CalendarConnection.deleted_at==None)
    query=select(ExternalCalendarEvent).where(ExternalCalendarEvent.calendar_connection_id.in_(connection_ids),ExternalCalendarEvent.deleted_at==None,ExternalCalendarEvent.cancelled==False)
    if from_:query=query.where(ExternalCalendarEvent.start_at>=from_)
    if to:query=query.where(ExternalCalendarEvent.start_at<=to)
    return [{"id":item.id,"external_event_id":item.external_event_id,"title":item.title,"description":item.description,"location":item.location,"start_at":iso_utc(item.start_at),"end_at":iso_utc(item.end_at),"all_day":item.all_day,"read_only":True} for item in db.scalars(query.order_by(ExternalCalendarEvent.start_at))]

@router.post("/google/sync")
def synchronize(user=Depends(current_user),db:Session=Depends(get_db)):
    connection=db.scalar(select(CalendarConnection).where(CalendarConnection.user_id==user.id,CalendarConnection.provider=="google",CalendarConnection.deleted_at==None))
    if not connection:raise HTTPException(404,"Google Calendar не подключён")
    try:return sync_google(db,connection,user.id)
    except ValueError as exc:db.commit();raise HTTPException(401,str(exc))

@router.get("/google/authorize")
def authorize(user=Depends(current_user)):
    if not google.configured():raise HTTPException(503,"Google OAuth credentials не настроены")
    return {"url":google.authorization_url(user.id)}

@router.get("/google/callback")
def callback(code:str,state:str,db:Session=Depends(get_db)):
    user_id=decode_token(state);user=db.get(User,user_id) if user_id else None
    if not user:raise HTTPException(400,"Некорректный OAuth state")
    data=google.exchange(code);connection=db.scalar(select(CalendarConnection).where(CalendarConnection.user_id==user.id,CalendarConnection.provider=="google",CalendarConnection.deleted_at==None)) or CalendarConnection(user_id=user.id,provider="google")
    connection.access_token_encrypted=google.encrypt(data.get("access_token",""))
    if data.get("refresh_token"):connection.refresh_token_encrypted=google.encrypt(data["refresh_token"])
    connection.token_expires_at=datetime.now(timezone.utc)+timedelta(seconds=int(data.get("expires_in",3600)));connection.status="connected";db.add(connection);db.commit();return RedirectResponse("/?calendar=connected")
