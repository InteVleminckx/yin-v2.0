from __future__ import annotations
import os, secrets, hashlib
from functools import wraps
import streamlit as st
from db.repositories import UserRepository
from db.database import Database
from .exceptions import AuthError

ITERATIONS = 150_000

def _hash_password(password: str, salt: bytes) -> str:
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, ITERATIONS)
    return dk.hex()

def create_user_if_missing(db: Database, username: str, plain_password: str) -> None:
    repo = UserRepository(db)
    if repo.get_by_username(username):
        return
    salt = secrets.token_bytes(16)
    pwd_hash = _hash_password(plain_password, salt)
    repo.create(username, pwd_hash, salt.hex())

def verify_password(db: Database, username: str, password: str) -> bool:
    repo = UserRepository(db)
    user = repo.get_by_username(username)
    if not user:
        return False
    salt = bytes.fromhex(user.salt)
    return _hash_password(password, salt) == user.pwd_hash

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("user"):
            st.error("Please log in to view this page.")
            st.stop()
        return fn(*args, **kwargs)
    return wrapper

# Bootstrapping default admin from Streamlit secrets or fallback
# Add in .streamlit/secrets.toml: ADMIN_USERNAME="admin" ADMIN_PASSWORD="strongpass"

def bootstrap_admin(db: Database):
    username = st.secrets.get("ADMIN_USERNAME", "admin")
    password = st.secrets.get("ADMIN_PASSWORD", "changeme")
    create_user_if_missing(db, username, password)