import os

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-prod")
    DATABASE_URL = os.environ.get("DATABASE_URL", None)  # e.g. sqlite:///local.db or postgresql://...

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

# Easy lookup by name
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}