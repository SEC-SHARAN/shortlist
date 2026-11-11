import os
from functools import lru_cache


class Settings:
    def __init__(self):
        is_vercel = bool(os.getenv("VERCEL"))
        self.env = os.getenv("ENV", "development")
        default_db = "sqlite:////tmp/ats_dev.db" if is_vercel else "sqlite:///./ats_dev.db"
        default_storage = "/tmp/resumes" if is_vercel else "./data/resumes"
        self.database_url = os.getenv("DATABASE_URL", default_db)
        self.secret_key = os.getenv("SECRET_KEY", "vercel-ats-default-secret-key-32chars-minimum")
        self.token_minutes = int(os.getenv("TOKEN_MINUTES", "480"))
        self.storage_dir = os.getenv("STORAGE_DIR", default_storage)
        self.max_upload_mb = int(os.getenv("MAX_UPLOAD_MB", "10"))
        self.max_files_per_request = int(os.getenv("MAX_FILES_PER_REQUEST", "50"))
        cors_default = "*" if is_vercel else "http://localhost:5173"
        self.cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", cors_default).split(",") if o.strip()]
        self.admin_email = os.getenv("ADMIN_EMAIL", "kvarunasharan05@gmail.com")
        self.admin_password = os.getenv("ADMIN_PASSWORD", "1234")
        self.use_spacy = os.getenv("USE_SPACY", "0") == "1"
        if self.env == "production" and (self.secret_key == "dev-only-change-me" or len(self.secret_key) < 32):
            raise RuntimeError("Set SECRET_KEY (>=32 chars) in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
