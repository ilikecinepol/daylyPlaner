import hmac
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.orm import Session

from .api.dependencies import current_user
from .database import get_db
from .models import ModuleEntitlement

MODULES = {
    "ai": {
        "title": "ИИ-помощник",
        "description": "Диалоги по задачам, планирование проектов и предложения изменений с подтверждением.",
        "icon": "✦",
    },
    "finance": {
        "title": "Финансы",
        "description": "Счета, операции, бюджеты, финансовые цели и запланированные платежи.",
        "icon": "₽",
    },
    "crace": {
        "title": "CRACE",
        "description": "Персональный тренировочный план, тренировки, пульс и питание.",
        "icon": "♥",
    },
}

MAX_FAILED_ATTEMPTS = 5
ATTEMPT_WINDOW_SECONDS = 15 * 60
_failed_attempts = defaultdict(deque)


class AccessCodeIn(BaseModel):
    code: SecretStr = Field(min_length=6, max_length=128)


def _aware(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def entitlement(db: Session, user_id: str, module: str):
    return db.get(ModuleEntitlement, (user_id, module))


def module_connected(db: Session, user, module: str) -> bool:
    grant = entitlement(db, user.id, module)
    return bool(grant and grant.enabled and (not grant.expires_at or _aware(grant.expires_at) > datetime.now(timezone.utc)))


def ensure_module(db: Session, user, module: str):
    if module not in MODULES:
        raise HTTPException(404, "Модуль не найден")
    if not module_connected(db, user, module):
        raise HTTPException(403, "Модуль не подключён. Откройте «Дополнительные возможности».")


def require_module(module: str):
    def dependency(db: Session = Depends(get_db), user=Depends(current_user)):
        ensure_module(db, user, module)
    return dependency


def _codes(module: str):
    values = [os.getenv(f"MODULE_ACCESS_CODE_{module.upper()}", ""), os.getenv("MODULE_ACCESS_CODE", "")]
    return [value for value in values if value]


def _attempt_key(user_id: str, module: str):
    return f"{user_id}:{module}"


def _prune_attempts(key: str, now: float):
    attempts = _failed_attempts[key]
    while attempts and attempts[0] <= now - ATTEMPT_WINDOW_SECONDS:
        attempts.popleft()
    return attempts


def _module_out(db: Session, user, key: str):
    grant = entitlement(db, user.id, key)
    connected = module_connected(db, user, key)
    return {
        "key": key,
        **MODULES[key],
        "connected": connected,
        "source": grant.source if connected else None,
        "expires_at": _aware(grant.expires_at).isoformat().replace("+00:00", "Z") if connected and grant.expires_at else None,
        "unlock_available": bool(_codes(key)),
    }


router = APIRouter(prefix="/api/v1/modules", tags=["optional modules"])


@router.get("")
def list_modules(db: Session = Depends(get_db), user=Depends(current_user)):
    return [_module_out(db, user, key) for key in MODULES]


@router.post("/{module}/unlock")
def unlock_module(module: str, data: AccessCodeIn, db: Session = Depends(get_db), user=Depends(current_user)):
    if module not in MODULES:
        raise HTTPException(404, "Модуль не найден")
    codes = _codes(module)
    if not codes:
        raise HTTPException(503, "Код подключения ещё не настроен администратором")
    now = time.monotonic()
    key = _attempt_key(user.id, module)
    attempts = _prune_attempts(key, now)
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(429, "Слишком много попыток. Повторите через 15 минут.")
    supplied = data.code.get_secret_value()
    if not any(hmac.compare_digest(supplied, expected) for expected in codes):
        attempts.append(now)
        raise HTTPException(403, "Неверный код подключения")
    attempts.clear()
    grant = entitlement(db, user.id, module) or ModuleEntitlement(user_id=user.id, module=module)
    grant.enabled = True
    grant.source = "access_code"
    grant.expires_at = None
    db.add(grant)
    if module == "ai":
        # Keep the AI provider-level grant compatible with the existing AI controls.
        from .ai.models import AIAccess
        ai_grant = db.get(AIAccess, user.id) or AIAccess(user_id=user.id)
        ai_grant.enabled = True
        ai_grant.expires_at = None
        db.add(ai_grant)
    db.commit()
    return _module_out(db, user, module)
