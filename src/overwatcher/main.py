from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from overwatcher import db, scheduler
from overwatcher.config import get_settings
from overwatcher.logging_setup import configure_logging
from overwatcher.routes import health, sms


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    db.init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="overwatcher", lifespan=lifespan)
app.include_router(health.router)
app.include_router(sms.router)
