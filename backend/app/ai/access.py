import os
from datetime import datetime, timezone
from fastapi import HTTPException
from .models import AIAccess

def provider_name(): return os.getenv("AI_PROVIDER", "demo")

def allowed(db, user):
    if os.getenv("AI_ENABLED", "0") != "1": return False
    grant = db.get(AIAccess, user.id)
    if grant:
        expiry = grant.expires_at
        if expiry and expiry.tzinfo is None: expiry = expiry.replace(tzinfo=timezone.utc)
        return grant.enabled and (not expiry or expiry > datetime.now(timezone.utc))
    if (os.getenv("AI_LOCAL_ACCESS", "0") == "1"
            and os.getenv("APP_ENV", "development").lower() not in {"production", "prod"}):
        return True
    return (provider_name() == "demo" and os.getenv("APP_ENV", "development") not in {"production", "prod"}
            and os.getenv("AI_DEMO_ACCESS", "0") == "1")

def require_access(db, user):
    if not allowed(db, user): raise HTTPException(403, "AI-модуль не подключён для этого пользователя")

if __name__ == "__main__":
    import argparse
    from ..database import SessionLocal
    from ..models import User
    parser=argparse.ArgumentParser(description="Manually grant/revoke AI access; no payments")
    parser.add_argument("user_id"); parser.add_argument("state", choices=["enable","disable"])
    args=parser.parse_args()
    with SessionLocal() as db:
        user=db.get(User,args.user_id)
        if not user or user.deleted_at: raise SystemExit("User not found")
        grant=db.get(AIAccess,args.user_id) or AIAccess(user_id=args.user_id)
        grant.enabled=args.state=="enable"; db.add(grant); db.commit()
        print("AI access updated")
