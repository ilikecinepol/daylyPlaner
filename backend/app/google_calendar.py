import base64,hashlib,os
from urllib.parse import urlencode
import httpx
from cryptography.fernet import Fernet
from .security import SECRET,token,decode_token

CLIENT_ID=os.getenv("GOOGLE_CLIENT_ID","");CLIENT_SECRET=os.getenv("GOOGLE_CLIENT_SECRET","");REDIRECT_URI=os.getenv("GOOGLE_REDIRECT_URI","http://127.0.0.1:8000/api/v1/google/callback")
fernet=Fernet(base64.urlsafe_b64encode(hashlib.sha256(SECRET.encode()).digest()))
def configured():return bool(CLIENT_ID and CLIENT_SECRET)
def authorization_url(user_id):
    params={"client_id":CLIENT_ID,"redirect_uri":REDIRECT_URI,"response_type":"code","scope":"openid email https://www.googleapis.com/auth/calendar.events","access_type":"offline","prompt":"consent","state":token(user_id)}
    return "https://accounts.google.com/o/oauth2/v2/auth?"+urlencode(params)
def exchange(code):
    r=httpx.post("https://oauth2.googleapis.com/token",data={"code":code,"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"redirect_uri":REDIRECT_URI,"grant_type":"authorization_code"},timeout=20);r.raise_for_status();return r.json()
def refresh(refresh_token):
    r=httpx.post("https://oauth2.googleapis.com/token",data={"refresh_token":refresh_token,"client_id":CLIENT_ID,"client_secret":CLIENT_SECRET,"grant_type":"refresh_token"},timeout=20);r.raise_for_status();return r.json()
def encrypt(value):return fernet.encrypt((value or "").encode()).decode()
def decrypt(value):return fernet.decrypt(value.encode()).decode()
def list_events(access_token,updated_min=None):
    params={"singleEvents":"true","maxResults":250};
    if updated_min:params["updatedMin"]=updated_min
    r=httpx.get("https://www.googleapis.com/calendar/v3/calendars/primary/events",headers={"Authorization":f"Bearer {access_token}"},params=params,timeout=30);r.raise_for_status();return r.json().get("items",[])
def upsert_event(access_token,event,event_id=None):
    url="https://www.googleapis.com/calendar/v3/calendars/primary/events"+(f"/{event_id}" if event_id else "");r=httpx.request("PATCH" if event_id else "POST",url,headers={"Authorization":f"Bearer {access_token}"},json=event,timeout=30);r.raise_for_status();return r.json()
def delete_event(access_token,event_id):
    r=httpx.delete(f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}",headers={"Authorization":f"Bearer {access_token}"},timeout=30)
    if r.status_code not in (204,404,410):r.raise_for_status()
