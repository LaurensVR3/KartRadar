import asyncio
import datetime
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from . import config, render
from .cache import CACHE
from .scheduler import refresh_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(refresh_loop())
    yield
    task.cancel()


app = FastAPI(title="KartRadar", lifespan=lifespan)


def _days() -> list[datetime.date]:
    today = datetime.date.today()
    return [today + datetime.timedelta(days=i) for i in range(config.DAYS_AHEAD)]


@app.get("/", response_class=HTMLResponse)
async def home():
    rows = CACHE.get_rows()
    return render.render_home(rows, _days(), CACHE.last_updated)


@app.get("/api/tracks")
async def api_tracks():
    return JSONResponse({
        "last_updated": CACHE.last_updated,
        "rows": CACHE.get_rows(),
    })


@app.get("/healthz")
async def health():
    return {"status": "ok", "last_updated": CACHE.last_updated}
