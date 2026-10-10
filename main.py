
import json
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, Request, Query
from fastapi.responses import Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST

app = FastAPI(title="Q8 Production Observability")

EMAIL = "25ds3000005@ds.study.iitm.ac.in"
START_TIME = time.monotonic()

REQUEST_COUNTER = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
)

logs = deque(maxlen=1000)
log_lock = Lock()


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())

    # Count every incoming request, including /metrics.
    REQUEST_COUNTER.inc()

    try:
        response = await call_next(request)
        level = "INFO"
    except Exception:
        level = "ERROR"
        raise
    finally:
        entry = {
            "level": level,
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": request.url.path,
            "request_id": request_id,
        }

        with log_lock:
            logs.append(entry)

        # Structured JSON log, one JSON object per line.
        print(json.dumps(entry), flush=True)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/work")
async def work(n: int = Query(default=1, ge=0)):
    # Perform K simple units of work.
    done = 0
    for _ in range(n):
        done += 1

    return {"email": EMAIL, "done": done}


@app.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok",
        "uptime_s": float(time.monotonic() - START_TIME),
    }


@app.get("/logs/tail")
async def logs_tail(limit: int = Query(default=10, ge=0, le=1000)):
    with log_lock:
        entries = list(logs)

    return entries[-limit:] if limit else []
