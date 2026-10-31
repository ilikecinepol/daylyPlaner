import os,tempfile

os.environ.setdefault("DATABASE_URL","sqlite:///"+tempfile.NamedTemporaryFile(suffix=".db",delete=False).name.replace("\\","/"))
os.environ.setdefault("SECRET_KEY","test-secret")
os.environ["MODULE_ACCESS_CODE"]="test-module-code"
