import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
import uvicorn
if __name__ == "__main__": uvicorn.run("app.main:app",host="127.0.0.1",port=8000,reload=True,app_dir="backend")
