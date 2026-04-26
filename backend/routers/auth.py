from fastapi import APIRouter, HTTPException, Response, Request
from pydantic import BaseModel
import secrets

router = APIRouter(tags=["authentication"])

# Simple in-memory session store
# For a production Hackathon this would use Redis or JWTs
SESSIONS = set()

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    # Hardcoded credentials for Mission Commander
    if req.username == "commander" and req.password == "nsh2026":
        token = secrets.token_hex(16)
        SESSIONS.add(token)
        # Set HTTPOnly cookie for secure persistence
        response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
        return {"status": "success", "token": token}
    raise HTTPException(status_code=401, detail="Invalid Commander credentials")

@router.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token in SESSIONS:
        SESSIONS.remove(token)
    response.delete_cookie("session_token")
    return {"status": "success"}

@router.get("/api/auth/verify")
async def verify(request: Request):
    token = request.cookies.get("session_token")
    if token and token in SESSIONS:
        return {"status": "authenticated", "role": "commander"}
    raise HTTPException(status_code=401, detail="Not authenticated")
