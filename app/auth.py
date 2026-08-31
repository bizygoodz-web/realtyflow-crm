"""
Auth + RBAC.

Two token "roles" exist:
  - agent  -> full access to everything scoped to their own agent_id
  - client -> access ONLY to their own contact_id (buyer or seller in the portal)

Every router that serves the Client Portal must depend on `require_client`
and filter every query by `current.contact_id`. Every router that serves
the Agent Dashboard must depend on `require_agent` and filter by
`current.agent_id`. Never trust a contact_id / agent_id passed in the
request body or query string over the one embedded in the JWT.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

SECRET_KEY = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES =  60 * 24 * 7 # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/agent/login")


class TokenData(BaseModel):
    sub: str  # agent_id or contact_id
    role: str  # "agent" | "admin" | "client"
    agent_id: Optional[str] = None  # present on client tokens too, for scoping lookups


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(**payload)
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_token(token: str = Depends(oauth2_scheme)) -> TokenData:
    return decode_token(token)


def require_agent(current: TokenData = Depends(get_current_token)) -> TokenData:
    if current.role not in ("agent", "admin"):
        raise HTTPException(status_code=403, detail="Agent access required")
    return current


def require_admin(current: TokenData = Depends(get_current_token)) -> TokenData:
    if current.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current


def require_client(current: TokenData = Depends(get_current_token)) -> TokenData:
    if current.role != "client":
        raise HTTPException(status_code=403, detail="Client portal access required")
    return current
