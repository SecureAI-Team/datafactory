from fastapi import HTTPException, Header
from jose import jwt
from .config import settings

def require_role(required_roles: list):
    def checker(authorization: str = Header(None), x_api_key: str = Header(None)):
        token = authorization.replace("Bearer ", "") if authorization else x_api_key
        if not token:
            raise HTTPException(status_code=401, detail="Auth required")
        try:
            payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algo])
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        role = payload.get("role")
        if role not in required_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    return checker
