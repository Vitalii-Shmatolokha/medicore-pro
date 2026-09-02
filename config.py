import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    # Secret key must be set via environment in production
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.environ.get('FLASK_SECRET_KEY') or 'dev-insecure-key-local-only-never-use-in-production'
    
    # Database Configuration (PostgreSQL / Supabase support with SQLite fallback)
    raw_db_url = os.environ.get('DATABASE_URL')
    
    if raw_db_url:
        # Normalize postgres:// to postgresql:// for SQLAlchemy compatibility
        if raw_db_url.startswith('postgres://'):
            raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = raw_db_url
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': int(os.environ.get('DB_POOL_SIZE', 10)),
            'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 20)),
            'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
            'pool_pre_ping': True,
        }
    else:
        DB_DIR = os.path.join(BASE_DIR, 'instance')
        os.makedirs(DB_DIR, exist_ok=True)
        DB_PATH = os.path.join(DB_DIR, 'healthcare.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{DB_PATH}'
        SQLALCHEMY_ENGINE_OPTIONS = {}

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session & Security Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds
    
    # Socket.IO / CORS Configuration
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', '*').split(',')