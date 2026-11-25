"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import dispose_db, init_db
from app.routers import admin_auth, exam_taking, exams, questions
from app.services import autosubmit


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    await autosubmit.restore_timers()  # task 6.3: recover unfinished exams after restart
    yield
    autosubmit.cancel_all()
    await dispose_db()


app = FastAPI(title="Online Interview Exam System", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(admin_auth.router)
app.include_router(questions.router)
app.include_router(exams.router)
app.include_router(exam_taking.router)
