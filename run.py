import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
import uvicorn
if __name__ == "__main__":
    uvicorn.run("app.main:app",host=os.getenv("HOST","0.0.0.0"),port=int(os.getenv("PORT","8000")),reload=os.getenv("RELOAD","1")=="1",app_dir="backend")
