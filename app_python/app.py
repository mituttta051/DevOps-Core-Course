"""
DevOps Info Service
Main application module
"""
import os
import socket
import platform
import json
import logging
import time
import tempfile
import threading
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_fields = getattr(record, "extra_fields", {})
        if isinstance(extra_fields, dict):
            log_record.update(extra_fields)
        return json.dumps(log_record, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("devops-info-service")
logger.setLevel(logging.INFO)
logger.handlers = [handler]
logger.propagate = False

app = FastAPI(
    title="DevOps Info Service",
    description="DevOps course info service",
    version="1.0.0"
)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
)

devops_info_endpoint_calls = Counter(
    "devops_info_endpoint_calls",
    "DevOps info service endpoint calls",
    ["endpoint"],
)

devops_info_system_collection_seconds = Histogram(
    "devops_info_system_collection_seconds",
    "Time spent collecting system info",
)

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 5000))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
VISITS_FILE = os.getenv('VISITS_FILE', os.path.join(tempfile.gettempdir(), 'visits'))

START_TIME = datetime.now(timezone.utc)

_visits_lock = threading.Lock()


def _read_visits() -> int:
    try:
        return int(Path(VISITS_FILE).read_text().strip())
    except (FileNotFoundError, ValueError):
        return 0


def _write_visits(count: int) -> None:
    path = Path(VISITS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(count))

@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    endpoint = request.url.path
    method = request.method
    start = time.perf_counter()
    http_requests_in_progress.inc()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        http_requests_in_progress.dec()
        duration = time.perf_counter() - start
        http_requests_total.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
        if endpoint not in ("/metrics",):
            devops_info_endpoint_calls.labels(endpoint=endpoint).inc()


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def get_system_info() -> Dict[str, Any]:
    return {
        'hostname': socket.gethostname(),
        'platform': platform.system(),
        'platform_version': platform.version(),
        'architecture': platform.machine(),
        'cpu_count': os.cpu_count() or 0,
        'python_version': platform.python_version()
    }


def get_uptime() -> Dict[str, Any]:
    delta = datetime.now(timezone.utc) - START_TIME
    seconds = int(delta.total_seconds())
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return {
        'seconds': seconds,
        'human': f"{hours} hour{'s' if hours != 1 else ''}, {minutes} minute{'s' if minutes != 1 else ''}"
    }


def get_runtime_info() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    uptime = get_uptime()
    return {
        'uptime_seconds': uptime['seconds'],
        'uptime_human': uptime['human'],
        'current_time': now.isoformat().replace('+00:00', 'Z'),
        'timezone': 'UTC'
    }


def get_request_info(request: Request) -> Dict[str, Any]:
    client_ip = request.client.host if request.client else 'unknown'
    user_agent = request.headers.get('user-agent', 'unknown')
    return {
        'client_ip': client_ip,
        'user_agent': user_agent,
        'method': request.method,
        'path': request.url.path
    }


@app.get("/")
async def index(request: Request) -> Dict[str, Any]:
    request_info = get_request_info(request)
    logger.info(
        "Request received",
        extra={"extra_fields": {"event": "request", **request_info}},
    )

    with _visits_lock:
        visits = _read_visits() + 1
        _write_visits(visits)

    t0 = time.perf_counter()
    system_info = get_system_info()
    devops_info_system_collection_seconds.observe(time.perf_counter() - t0)
    runtime_info = get_runtime_info()

    return {
        'service': {
            'name': 'devops-info-service',
            'version': '1.0.0',
            'description': 'DevOps course info service',
            'framework': 'FastAPI'
        },
        'system': system_info,
        'runtime': runtime_info,
        'request': request_info,
        'endpoints': [
            {'path': '/', 'method': 'GET', 'description': 'Service information'},
            {'path': '/health', 'method': 'GET', 'description': 'Health check'},
            {'path': '/visits', 'method': 'GET', 'description': 'Visit counter'},
            {'path': '/docs', 'method': 'GET', 'description': 'API documentation'},
            {'path': '/openapi.json', 'method': 'GET', 'description': 'OpenAPI schema'}
        ]
    }


@app.get("/visits")
async def visits() -> Dict[str, Any]:
    count = _read_visits()
    return {'visits': count}


@app.get("/health")
async def health() -> Dict[str, Any]:
    uptime = get_uptime()
    now = datetime.now(timezone.utc)
    logger.info(
        "Health check",
        extra={
            "extra_fields": {
                "event": "health_check",
                "uptime_seconds": uptime["seconds"],
            }
        },
    )
    return {
        'status': 'healthy',
        'timestamp': now.isoformat().replace('+00:00', 'Z'),
        'uptime_seconds': uptime['seconds']
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_info = get_request_info(request)
    logger.warning(
        "HTTP error",
        extra={
            "extra_fields": {
                "event": "http_error",
                "status_code": exc.status_code,
                "detail": exc.detail,
                **request_info,
            }
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            'error': exc.detail,
            'status_code': exc.status_code,
            'path': request.url.path
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_info = get_request_info(request)
    logger.warning(
        "Validation error",
        extra={
            "extra_fields": {
                "event": "validation_error",
                "errors": exc.errors(),
                **request_info,
            }
        },
    )
    return JSONResponse(
        status_code=422,
        content={
            'error': 'Validation Error',
            'message': 'Invalid request parameters',
            'details': exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    request_info = get_request_info(request)
    logger.error(
        "Unexpected error",
        exc_info=True,
        extra={
            "extra_fields": {
                "event": "unexpected_error",
                "error": str(exc),
                **request_info,
            }
        },
    )
    return JSONResponse(
        status_code=500,
        content={
            'error': 'Internal Server Error',
            'message': 'An unexpected error occurred'
        }
    )


if __name__ == "__main__":
    import uvicorn
    logger.info(
        "Starting DevOps Info Service",
        extra={
            "extra_fields": {
                "event": "startup",
                "host": HOST,
                "port": PORT,
                "debug": DEBUG,
            }
        },
    )
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if not DEBUG else "debug"
    )
