from datetime import datetime,timezone,timedelta
import httpx
from sqlalchemy import select
from .. import google_calendar as google
from ..models import Task,CalendarEventLink,ExternalCalendarEvent

def aware(value):
    if not value:return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def remote_time(event):
    value=event.get("updated")
    return datetime.fromisoformat(value.replace("Z","+00:00")) if value else None

def event_start(event):
    start=event.get("start",{});value=start.get("dateTime") or start.get("date")
    return (datetime.fromisoformat(value.replace("Z","+00:00")) if value else None),"date" in start

def event_end(event):
    end=event.get("end",{});value=end.get("dateTime") or end.get("date")
    return datetime.fromisoformat(value.replace("Z","+00:00")) if value else None

def access_token(connection):
    expires=aware(connection.token_expires_at)
    if expires and expires>datetime.now(timezone.utc)+timedelta(seconds=60):return google.decrypt(connection.access_token_encrypted)
    if not connection.refresh_token_encrypted:connection.status="reauthorization_required";raise ValueError("Google Calendar требует повторного подключения")
    try:data=google.refresh(google.decrypt(connection.refresh_token_encrypted))
    except httpx.HTTPError as exc:
        connection.status="reauthorization_required";raise ValueError("Google refresh token недействителен") from exc
    connection.access_token_encrypted=google.encrypt(data["access_token"])
    if data.get("refresh_token"):connection.refresh_token_encrypted=google.encrypt(data["refresh_token"])
    connection.token_expires_at=datetime.now(timezone.utc)+timedelta(seconds=int(data.get("expires_in",3600)))
    connection.status="connected"
    return data["access_token"]

def payload(task):
    start=aware(task.start_at);event={"summary":task.title,"description":task.description,"location":task.location,"extendedProperties":{"private":{"plan_task_id":task.id}}}
    if task.all_day:return event|{"start":{"date":start.date().isoformat()},"end":{"date":(start.date()+timedelta(days=1)).isoformat()}}
    end=aware(task.end_at) or start+timedelta(minutes=task.duration_minutes)
    return event|{"start":{"dateTime":start.isoformat()},"end":{"dateTime":end.isoformat()}}

def apply_remote(task,event):
    start,all_day=event_start(event);end=event_end(event);task.start_at=start;task.end_at=None if all_day else end;task.all_day=all_day
    if start and end and not all_day:task.duration_minutes=max(0,round((end-start).total_seconds()/60))
    task.title=event.get("summary") or task.title;task.description=event.get("description",task.description);task.location=event.get("location",task.location);task.sync_version=(task.sync_version or 0)+1

def save_external(db,connection,event):
    item=db.scalar(select(ExternalCalendarEvent).where(ExternalCalendarEvent.calendar_connection_id==connection.id,ExternalCalendarEvent.external_event_id==event["id"])) or ExternalCalendarEvent(calendar_connection_id=connection.id,external_event_id=event["id"])
    start,all_day=event_start(event);end_data=event.get("end",{});end_value=end_data.get("dateTime") or end_data.get("date")
    item.title=event.get("summary","");item.description=event.get("description","");item.location=event.get("location","");item.start_at=start;item.end_at=datetime.fromisoformat(end_value.replace("Z","+00:00")) if end_value else None;item.all_day=all_day;item.external_updated_at=remote_time(event);item.cancelled=event.get("status")=="cancelled";db.add(item)

def sync(db,connection,user_id):
    token=access_token(connection);imported=exported=deleted=external=0;now=datetime.now(timezone.utc)
    # Pull first. A remote event is only a Task when it carries our id and belongs to this user.
    for event in google.list_events(token,aware(connection.last_synced_at).isoformat() if connection.last_synced_at else None):
        task_id=event.get("extendedProperties",{}).get("private",{}).get("plan_task_id");task=db.get(Task,task_id) if task_id else None
        if not task or task.user_id!=user_id:
            save_external(db,connection,event);external+=1;continue
        link=db.scalar(select(CalendarEventLink).where(CalendarEventLink.task_id==task.id,CalendarEventLink.calendar_connection_id==connection.id))
        if not link:link=CalendarEventLink(task_id=task.id,calendar_connection_id=connection.id,external_event_id=event["id"]);db.add(link)
        updated=remote_time(event);local=aware(task.updated_at);baseline=aware(link.last_synced_at)
        if event.get("status")=="cancelled":
            task.deleted_at=updated or now;deleted+=1
        else:
            remote_changed=bool(updated and (not baseline or updated>baseline));local_changed=bool(local and (not baseline or local>baseline))
            if remote_changed and (not local_changed or updated>=local):apply_remote(task,event);imported+=1
        link.external_updated_at=updated;link.last_synced_at=now
    # Push local changes and deletion tombstones only for linked daylyPlaner events.
    for task in db.scalars(select(Task).where(Task.user_id==user_id,Task.start_at!=None)):
        link=db.scalar(select(CalendarEventLink).where(CalendarEventLink.task_id==task.id,CalendarEventLink.calendar_connection_id==connection.id))
        if task.deleted_at:
            if link and link.external_event_id and link.sync_status!="deleted":google.delete_event(token,link.external_event_id);link.sync_status="deleted";link.last_synced_at=now;deleted+=1
            continue
        local=aware(task.updated_at);baseline=aware(link.last_synced_at) if link else None
        if link and baseline and local and local<=baseline:continue
        remote=google.upsert_event(token,payload(task),link.external_event_id if link else None)
        if not link:link=CalendarEventLink(task_id=task.id,calendar_connection_id=connection.id,external_event_id=remote["id"]);db.add(link)
        link.external_updated_at=remote_time(remote);link.last_synced_at=now;link.sync_status="synced";exported+=1
    connection.last_synced_at=now;connection.status="connected";db.commit()
    return {"exported":exported,"imported":imported,"deleted":deleted,"external":external,"synced_at":now.isoformat()}
