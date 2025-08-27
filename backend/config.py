import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    ORA_HOST = os.getenv("ORA_HOST", "127.0.0.1")
    ORA_PORT = int(os.getenv("ORA_PORT", "1521"))
    ORA_SERVICE = os.getenv("ORA_SERVICE", "xe")
    ORA_USER = os.getenv("ORA_USER", "SYSTEM")
    ORA_PASSWORD = os.getenv("ORA_PASSWORD", "admin")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    @property
    def dsn(self) -> str:
        return f"{self.ORA_HOST}:{self.ORA_PORT}/{self.ORA_SERVICE}"

