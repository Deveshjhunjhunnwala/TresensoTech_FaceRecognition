from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from secrets import token_urlsafe

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.auth import authenticate_admin, get_admin_credentials
from src.v2.schemas import (
    ArchitectureNote,
    AttendanceRow,
    DeleteAttendanceResult,
    DeleteWorkerResult,
    DetectionResult,
    EnrollmentResult,
    IndexStats,
    RecognitionResult,
    ServiceStatus,
    WorkerRead,
)
from src.v2.service import ScalableAttendanceService


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST_DIR / "index.html"
SESSION_TTL_HOURS = 12


@dataclass
class SessionState:
    username: str
    expires_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    expires_at: datetime


class MeResponse(BaseModel):
    username: str
    expires_at: datetime


app = FastAPI(
    title="Industrial Facial Attendance API",
    version="3.0.0",
    description="FastAPI backend for the operator-facing React attendance application.",
)
service = ScalableAttendanceService()
sessions: dict[str, SessionState] = {}


if (FRONTEND_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets")


def _purge_expired_sessions() -> None:
    now = datetime.utcnow()
    expired = [token for token, state in sessions.items() if state.expires_at <= now]
    for token in expired:
        del sessions[token]


def _extract_token(authorization: str | None, x_auth_token: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    if x_auth_token:
        return x_auth_token.strip()
    return None


def require_auth(
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
) -> SessionState:
    _purge_expired_sessions()
    token = _extract_token(authorization, x_auth_token)
    if not token or token not in sessions:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return sessions[token]


@app.get("/", response_class=HTMLResponse, response_model=None)
def root() -> Response:
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return HTMLResponse(
        """
        <html>
            <head><title>Facial Attendance App</title></head>
            <body style="font-family:Segoe UI,Arial,sans-serif;padding:40px;background:#f5f7fa;">
                <h1>Frontend Not Built Yet</h1>
                <p>Run <code>npm install</code> and <code>npm run build</code> inside the <code>frontend</code> folder.</p>
            </body>
        </html>
        """
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/v2/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    if not authenticate_admin(payload.username, payload.password):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    sessions[token] = SessionState(username=payload.username, expires_at=expires_at)
    return LoginResponse(token=token, username=payload.username, expires_at=expires_at)


@app.get("/api/v2/auth/me", response_model=MeResponse)
def me(session: SessionState = Depends(require_auth)) -> MeResponse:
    return MeResponse(username=session.username, expires_at=session.expires_at)


@app.post("/api/v2/auth/logout")
def logout(
    authorization: str | None = Header(default=None),
    x_auth_token: str | None = Header(default=None),
) -> dict[str, bool]:
    token = _extract_token(authorization, x_auth_token)
    if token and token in sessions:
        del sessions[token]
    return {"ok": True}


@app.get("/api/v2/auth/default-admin")
def default_admin_hint(session: SessionState = Depends(require_auth)) -> dict[str, str]:
    username, _password = get_admin_credentials()
    return {"username": username}


@app.get("/api/v2/status", response_model=ServiceStatus)
def status(_: SessionState = Depends(require_auth)) -> ServiceStatus:
    return service.status()


@app.get("/api/v2/architecture", response_model=ArchitectureNote)
def architecture(_: SessionState = Depends(require_auth)) -> ArchitectureNote:
    return service.architecture_note()


@app.get("/api/v2/workers", response_model=list[WorkerRead])
def list_workers(_: SessionState = Depends(require_auth)) -> list[WorkerRead]:
    return service.list_workers()


@app.post("/api/v2/workers/enroll", response_model=EnrollmentResult)
async def enroll_worker(
    employee_code: str = Form(...),
    name: str = Form(...),
    images: list[UploadFile] = File(...),
    replace_existing: bool = Form(True),
    _: SessionState = Depends(require_auth),
) -> EnrollmentResult:
    image_bytes = [await image.read() for image in images]
    return service.enroll_worker(
        employee_code=employee_code,
        name=name,
        image_bytes_list=image_bytes,
        replace_existing=replace_existing,
    )


@app.delete("/api/v2/workers/{employee_code}", response_model=DeleteWorkerResult)
def delete_worker(employee_code: str, _: SessionState = Depends(require_auth)) -> DeleteWorkerResult:
    return service.delete_worker(employee_code=employee_code)


@app.post("/api/v2/recognitions", response_model=RecognitionResult)
async def recognize(
    camera_id: str = Form(...),
    image: UploadFile = File(...),
    top_k: int = Form(3),
    _: SessionState = Depends(require_auth),
) -> RecognitionResult:
    image_bytes = await image.read()
    return service.recognize(image_bytes=image_bytes, camera_id=camera_id, top_k=top_k)


@app.post("/api/v2/detections", response_model=DetectionResult)
async def detect(image: UploadFile = File(...), _: SessionState = Depends(require_auth)) -> DetectionResult:
    image_bytes = await image.read()
    return service.detect(image_bytes=image_bytes)


@app.get("/api/v2/attendance", response_model=list[AttendanceRow])
def list_attendance(
    limit: int = Query(default=100, ge=1, le=500),
    _: SessionState = Depends(require_auth),
) -> list[AttendanceRow]:
    return service.list_attendance(limit=limit)


@app.delete("/api/v2/attendance/{attendance_id}", response_model=DeleteAttendanceResult)
def delete_attendance(attendance_id: int, _: SessionState = Depends(require_auth)) -> DeleteAttendanceResult:
    return service.delete_attendance(attendance_id=attendance_id)


@app.post("/api/v2/index/rebuild", response_model=IndexStats)
def rebuild_index(_: SessionState = Depends(require_auth)) -> IndexStats:
    return service.rebuild_index()


@app.get("/{full_path:path}", response_model=None)
def spa_fallback(full_path: str) -> Response:
    if full_path.startswith("api/"):
        return JSONResponse({"detail": "Not Found"}, status_code=404)
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)
    return JSONResponse(
        {"detail": "Frontend not built. Run npm install && npm run build in the frontend folder."},
        status_code=404,
    )
