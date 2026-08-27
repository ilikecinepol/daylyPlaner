import base64, hashlib, hmac, json, os, secrets, time

SECRET = os.getenv("SECRET_KEY", "change-me-in-production")
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16); digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return base64.b64encode(salt + digest).decode()
def verify_password(password: str, encoded: str) -> bool:
    raw = base64.b64decode(encoded); return hmac.compare_digest(raw[16:], hashlib.pbkdf2_hmac("sha256", password.encode(), raw[:16], 210_000))
def token(user_id: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"sub":user_id,"exp":int(time.time())+604800}).encode()).decode().rstrip("=")
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest(); return payload+"."+sig
def decode_token(value: str) -> str | None:
    try:
        payload,sig=value.split("."); expected=hmac.new(SECRET.encode(),payload.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig,expected): return None
        data=json.loads(base64.urlsafe_b64decode(payload+"="*(-len(payload)%4)))
        return data["sub"] if data["exp"]>time.time() else None
    except Exception: return None
