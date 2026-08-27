import os
from datetime import timezone
from fastapi import Depends,HTTPException,Request,Response
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..security import token,decode_token

def set_session_cookie(response:Response,user_id:str):
    production=os.getenv("APP_ENV","development").lower() in {"production","prod"}
    response.set_cookie("plan_session",token(user_id),httponly=True,samesite="lax",secure=production or os.getenv("COOKIE_SECURE","0")=="1",max_age=604800,path="/")

def current_user(request:Request,db:Session=Depends(get_db)):
    user_id=decode_token(request.cookies.get("plan_session",""));user=db.get(User,user_id) if user_id else None
    if not user or user.deleted_at:raise HTTPException(401,"Требуется авторизация")
    return user

def iso_utc(value):
    if not value:return None
    if value.tzinfo is None:value=value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00","Z")
