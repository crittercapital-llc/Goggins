import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import database
from routers import profile, plans, workouts, recovery, logs, feedback


@asynccontextmanager
async def lifespan(app: FastAPI):
    await database.init_db()
    yield


app = FastAPI(title="Goggins Training AI", version="1.0.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(profile.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(workouts.router, prefix="/api/v1")
app.include_router(recovery.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    return FileResponse("static/index.html")
