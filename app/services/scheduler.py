"""
The actual engine that makes drip campaigns fire. Two jobs, both driven by
APScheduler (no separate worker process/Redis needed — fine for a single
Render web service; move to Celery+Redis if you outgrow this):

  - process_enrollments   every 15 minutes: for each active enrollment,
    figure out if the next step is due (enrolled_at + cumulative delay_days),
    send it, log it to the ledger, and advance current_step.

  - enroll_anniversaries  once a day: finds deals that closed ~365 days ago
    and enrolls those contacts in any "anniversary" workflow, so the
    "Past Client Anniversary Check-in" example from the brief actually runs.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from .mailer import render_template, send_message
from .enrollment import auto_enroll

logger = logging.getLogger("realtyflow.scheduler")


def _cumulative_delay(steps: list, up_to_step: int) -> int:
    """Sum of delay_days for every step from 0..up_to_step inclusive."""
    return sum(step["delay_days"] for step in steps[: up_to_step + 1])


def process_enrollments(db: Session = None):
    owns_session = db is None
    db = db or SessionLocal()
    try:
        enrollments = (
            db.query(models.WorkflowEnrollment)
            .filter(models.WorkflowEnrollment.status == "active")
            .all()
        )
        now = datetime.utcnow()

        for enrollment in enrollments:
            workflow = db.query(models.Workflow).get(enrollment.workflow_id)
            if not workflow or not workflow.is_active:
                continue

            steps = workflow.steps
            step_index = enrollment.current_step
            if step_index >= len(steps):
                enrollment.status = "completed"
                continue

            due_at = enrollment.enrolled_at + timedelta(days=_cumulative_delay(steps, step_index))
            if now < due_at:
                continue  # not due yet

            contact = db.query(models.Contact).get(enrollment.contact_id)
            if not contact:
                enrollment.status = "completed"
                continue

            step = steps[step_index]
            body = render_template(step["template_id"], contact)
            sent = send_message(step["channel"], contact, body)

            db.add(models.Activity(
                contact_id=contact.id,
                agent_id=contact.agent_id,
                type=models.ActivityType.email if step["channel"] == "email" else models.ActivityType.sms,
                content=f"[{workflow.name}] step {step_index + 1}/{len(steps)}: {body}" if sent
                        else f"[{workflow.name}] step {step_index + 1}/{len(steps)} skipped - no {step['channel']} on file",
                is_automated=True,
            ))

            enrollment.current_step += 1
            if enrollment.current_step >= len(steps):
                enrollment.status = "completed"

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("process_enrollments failed")
    finally:
        if owns_session:
            db.close()


def enroll_anniversaries(db: Session = None):
    owns_session = db is None
    db = db or SessionLocal()
    try:
        window_start = datetime.utcnow() - timedelta(days=366)
        window_end = datetime.utcnow() - timedelta(days=364)

        closed_deals = (
            db.query(models.Deal)
            .filter(
                models.Deal.stage == models.DealStage.closed,
                models.Deal.close_date >= window_start,
                models.Deal.close_date <= window_end,
            )
            .all()
        )

        for deal in closed_deals:
            contact = db.query(models.Contact).get(deal.contact_id)
            if contact:
                auto_enroll(db, contact, trigger_event="anniversary")

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("enroll_anniversaries failed")
    finally:
        if owns_session:
            db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(process_enrollments, "interval", minutes=15, id="process_enrollments")
    scheduler.add_job(enroll_anniversaries, "cron", hour=6, id="enroll_anniversaries")
    scheduler.start()
    logger.info("Workflow scheduler started (process_enrollments every 15m, enroll_anniversaries daily at 06:00 UTC)")
    return scheduler
