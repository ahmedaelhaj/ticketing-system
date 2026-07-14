import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.routers import auth, users, teams, tickets, approvals, reports, attachments, notifications
from app.seed import seed_super_admin, seed_demo_data

app = FastAPI(title="SME Ticketing System", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(teams.router)
app.include_router(tickets.router)
app.include_router(approvals.router)
app.include_router(reports.router)
app.include_router(attachments.router)
app.include_router(notifications.router)


@app.on_event("startup")
def on_startup():
    # v1: create_all is used instead of Alembic migrations for simplicity.
    # Swap to `alembic upgrade head` before this line once migrations are introduced.
    Base.metadata.create_all(bind=engine)
    os.makedirs(settings.upload_root, exist_ok=True)
    db = SessionLocal()
    try:
        seed_super_admin(db)
        seed_demo_data(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
