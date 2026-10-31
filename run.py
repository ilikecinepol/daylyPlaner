import os, sys

ROOT=os.path.dirname(__file__)

def load_local_env():
    path=os.path.join(ROOT,".env")
    if not os.path.exists(path):return
    with open(path,encoding="utf-8") as source:
        for raw in source:
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:continue
            key,value=line.split("=",1);key=key.strip();value=value.strip()
            if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
            os.environ.setdefault(key,value)

load_local_env()
sys.path.insert(0, os.path.join(ROOT, "backend"))
import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app",host=os.getenv("HOST","0.0.0.0"),port=int(os.getenv("PORT","8000")),reload=os.getenv("RELOAD","1")=="1",app_dir="backend")
