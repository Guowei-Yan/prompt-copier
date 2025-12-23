import os

AUTH_USERNAME = os.environ.get("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "changeme")

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-to-a-random-string")

DATABASE_PATH = os.environ.get("DATABASE_PATH", "/data/prompts.db")
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATABASE_PATH}"
