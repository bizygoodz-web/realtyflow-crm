from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import (
    auth_router, contacts, deals, activities, documents, workflows, cma,
    ai_content, portal, showings, properties,
)
from .services.scheduler import start_scheduler
# Schema is now owned by Alembic (see /migrations) - run `alembic upgrade head`
# before starting the app instead of relying on create_all. This matters as
# soon as you have real data: create_all can only add brand-new tables, it
# will never alter an existing one, so a column/type change (like Document
# switching from a raw file_url to an S3 key) would silently do nothing here.
app = FastAPI(title="Navigation Realty API", version="0.1.0")
@app.on_event("startup")
def _launch_scheduler():
    # Set SCHEDULER_ENABLED=false in env for local dev / tests if you don't
    # want the drip-campaign job ticking every 15 minutes while you work.
    import os
    if os.getenv("SCHEDULER_ENABLED", "true").lower() != "false":
        app.state.scheduler = start_scheduler()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Agent Dashboard + Client Portal origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Agent Dashboard routers
app.include_router(auth_router.router)
app.include_router(contacts.router)
app.include_router(deals.router)
app.include_router(activities.router)
app.include_router(documents.router)
app.include_router(workflows.router)
app.include_router(cma.router)
app.include_router(ai_content.router)
app.include_router(showings.router)
app.include_router(properties.router)
# Client Portal router - all endpoints self-scope to the caller's contact_id
app.include_router(portal.router)
@app.get("/health")
def health():
    return {"status": "ok"}
