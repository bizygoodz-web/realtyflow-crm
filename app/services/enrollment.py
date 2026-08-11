"""
Auto-enrollment: when a trigger event happens (new lead created, a showing
gets feedback, a deal closes a year ago), find any active workflow this
agent has configured for that trigger and enroll the contact — unless
they're already enrolled in it.
"""
from sqlalchemy.orm import Session

from .. import models


def auto_enroll(db: Session, contact: "models.Contact", trigger_event: str) -> list:
    workflows = (
        db.query(models.Workflow)
        .filter(
            models.Workflow.agent_id == contact.agent_id,
            models.Workflow.trigger_event == trigger_event,
            models.Workflow.is_active.is_(True),
        )
        .all()
    )

    new_enrollments = []
    for workflow in workflows:
        already_enrolled = (
            db.query(models.WorkflowEnrollment)
            .filter(
                models.WorkflowEnrollment.contact_id == contact.id,
                models.WorkflowEnrollment.workflow_id == workflow.id,
                models.WorkflowEnrollment.status == "active",
            )
            .first()
        )
        if already_enrolled:
            continue

        enrollment = models.WorkflowEnrollment(contact_id=contact.id, workflow_id=workflow.id)
        db.add(enrollment)
        new_enrollments.append(enrollment)

    if new_enrollments:
        db.flush()
    return new_enrollments
