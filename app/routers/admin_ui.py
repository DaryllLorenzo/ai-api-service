import base64
import hashlib
import hmac
import json
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth.api_keys import api_key_manager
from app.config import settings
from app.models.loader import model_loader
from app.templates_config import templates

router = APIRouter(prefix="/panel", tags=["Admin Panel"])
SESSION_COOKIE = "fastneural_panel"
_sessions: dict[str, str] = {}


def _sign(value: str) -> str:
    encoded = base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")
    signature = hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _unsign(value: str) -> Optional[str]:
    try:
        encoded, signature = value.rsplit(".", 1)
        expected = hmac.new(settings.secret_key.encode(), encoded.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def _session_key(request: Request) -> Optional[str]:
    token = _unsign(request.cookies.get(SESSION_COOKIE, ""))
    key = _sessions.get(token or "")
    if not key:
        return None
    try:
        api_key_manager.validate_key(key, endpoint="*", require_admin=True)
    except Exception:
        _sessions.pop(token or "", None)
        return None
    return key


def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/panel/login", status_code=303)


def _context(request: Request, **values):
    return {"request": request, "active": "dashboard", **values}


async def _proxy(request: Request, path: str, *, json_body=None, form=None, upload=None):
    key = _session_key(request)
    if not key:
        return None
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://fastneural") as client:
        if upload:
            response = await client.post(path, headers={"X-API-Key": key}, data=form or {}, files={"file": upload})
        elif json_body is not None:
            response = await client.post(path, headers={"X-API-Key": key}, json=json_body)
        else:
            response = await client.post(path, headers={"X-API-Key": key}, data=form or {})
    try:
        body = response.json()
    except ValueError:
        body = {"detail": response.text}
    return response.status_code, body


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login", response_class=HTMLResponse)
async def login(request: Request, api_key: str = Form(...)):
    try:
        api_key_manager.validate_key(api_key, endpoint="*", require_admin=True)
    except Exception:
        return templates.TemplateResponse("login.html", {"request": request, "error": "La clave administrativa no es válida."}, status_code=401)
    token = secrets.token_urlsafe(24)
    _sessions[token] = api_key
    response = RedirectResponse("/panel", status_code=303)
    response.set_cookie(SESSION_COOKIE, _sign(token), httponly=True, samesite="lax", secure=not settings.debug, max_age=28800)
    return response


@router.post("/logout")
async def logout(request: Request):
    token = _unsign(request.cookies.get(SESSION_COOKIE, ""))
    _sessions.pop(token or "", None)
    response = RedirectResponse("/panel/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@router.get("", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _session_key(request): return _login_redirect()
    return templates.TemplateResponse("dashboard.html", _context(request, active="dashboard", stats=api_key_manager.get_key_stats(), models_loaded=model_loader.models_loaded))


@router.get("/operation/{operation}", response_class=HTMLResponse)
async def operation_page(request: Request, operation: str):
    if not _session_key(request): return _login_redirect()
    allowed = {"chat", "transcribe", "embeddings", "ocr", "classify", "sentiment", "entities", "summarize", "translate", "comprehensive", "business-health"}
    if operation not in allowed: return RedirectResponse("/panel", status_code=303)
    return templates.TemplateResponse(f"{operation}.html", _context(request, active=operation, result=None, error=None))


@router.post("/operation/{operation}", response_class=HTMLResponse)
async def operation_submit(request: Request, operation: str, text: str = Form(""), categories: str = Form(""), source_lang: str = Form("es"), target_lang: str = Form("en"), max_length: int = Form(150), file: UploadFile | None = File(None)):
    if not _session_key(request): return HTMLResponse("Session expired", status_code=401)
    payload = None
    path = ""
    form = None
    upload = None
    if operation == "chat":
        path, payload = "/generate/chat", {"messages": [{"role": "user", "content": text}], "stream": False}
    elif operation == "embeddings":
        path, payload = "/embeddings/", {"texts": [line for line in text.splitlines() if line.strip()]}
    elif operation == "classify":
        path, payload = "/business/classify", {"text": text, "categories": [c.strip() for c in categories.split(",") if c.strip()]}
    elif operation == "sentiment": path, payload = "/business/sentiment", {"text": text}
    elif operation == "entities": path, payload = "/business/entities", {"text": text}
    elif operation == "summarize": path, payload = "/business/summarize", {"text": text, "max_length": max_length}
    elif operation == "translate": path, payload = "/business/translate", {"text": text, "source_lang": source_lang, "target_lang": target_lang}
    elif operation == "comprehensive": path, payload = "/business/analyze/comprehensive", {"text": text}
    elif operation == "transcribe" and file:
        path, upload = "/transcribe/", (file.filename, await file.read(), file.content_type or "application/octet-stream")
    elif operation == "ocr" and file:
        path, upload = "/ocr/recognize", (file.filename, await file.read(), file.content_type or "image/jpeg")
    elif operation == "business-health":
        if not _session_key(request): return HTMLResponse("Session expired", status_code=401)
        key = _session_key(request)
        transport = httpx.ASGITransport(app=request.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://fastneural") as client: response = await client.get("/business/health", headers={"X-API-Key": key})
        try: result = response.json()
        except ValueError: result = {"detail": response.text}
        return templates.TemplateResponse("result.html", {"request": request, "result": result, "error": None})
    else:
        return templates.TemplateResponse("result.html", {"request": request, "result": None, "error": "Selecciona un archivo válido."}, status_code=400)
    response = await _proxy(request, path, json_body=payload, form=form, upload=upload)
    status, result = response
    return templates.TemplateResponse("result.html", {"request": request, "result": result if status < 400 else None, "error": result.get("detail", "La operación falló.") if status >= 400 else None}, status_code=200)


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request):
    if not _session_key(request): return _login_redirect()
    return templates.TemplateResponse("keys.html", _context(request, active="keys", keys=api_key_manager.list_keys(), created_key=None, form_error=None, selected_permissions=[]))


@router.post("/keys/create", response_class=HTMLResponse)
async def create_key(request: Request, name: str = Form(...), description: str = Form(""), rate_limit: int = Form(60), expires_in_days: Optional[int] = Form(None), permissions: list[str] = Form([])):
    if not _session_key(request): return HTMLResponse("Session expired", status_code=401)
    permissions = [value for value in permissions if value.strip()]
    if not permissions:
        return templates.TemplateResponse("keys.html", _context(request, active="keys", keys=api_key_manager.list_keys(), created_key=None, form_error="Selecciona al menos un permiso para crear una clave.", selected_permissions=permissions), status_code=422)
    if "*" in permissions:
        permissions = ["*"]
    is_admin = "*" in permissions
    key = api_key_manager.create_key(name=name, description=description, rate_limit=rate_limit, expires_in_days=expires_in_days, allowed_endpoints=permissions, is_admin=is_admin)
    return templates.TemplateResponse("keys.html", _context(request, active="keys", keys=api_key_manager.list_keys(), created_key=key, form_error=None, selected_permissions=[]))


@router.post("/keys/{key_prefix}/{action}", response_class=HTMLResponse)
async def key_action(request: Request, key_prefix: str, action: str):
    if not _session_key(request): return HTMLResponse("Session expired", status_code=401)
    if action == "revoke": api_key_manager.revoke_key(key_prefix)
    elif action == "activate": api_key_manager.activate_key(key_prefix)
    return templates.TemplateResponse("key_rows.html", {"request": request, "keys": api_key_manager.list_keys()})
