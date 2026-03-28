import os

from fastapi import Cookie, HTTPException

APP_PASSWORD = os.getenv("APP_PASSWORD", "changeme")


def verify_password(password: str):
    if password != APP_PASSWORD:
        raise HTTPException(status_code=401, detail="invalid password")


def require_auth(session: str = Cookie(default=None)):
    if session != "authenticated":
        raise HTTPException(status_code=401, detail="not authenticated")