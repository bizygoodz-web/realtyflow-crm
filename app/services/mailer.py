"""
Thin sending layer for workflow steps. This intentionally does NOT call a
real email/SMS provider yet — swap `_send_email` / `_send_sms` for
SendGrid/Twilio/SES calls when you're ready to go live. Keeping it stubbed
means the scheduler logic below can be tested without burning provider
credits or accidentally emailing real people during development.
"""
import logging

logger = logging.getLogger("realtyflow.mailer")

# Built-in fallback copy for common templates. Swap this for content pulled
# from a `templates` table once the agent needs to customize wording.
TEMPLATES = {
    "new_lead_day0": "Hi {first_name}, thanks for reaching out! I'm excited to help you find the right home — I'll follow up shortly with a few options that match what you're looking for.",
    "new_lead_day3": "Hi {first_name}, just checking in — happy to answer any questions about the process or set up a time to chat.",
    "new_lead_day7": "Hi {first_name}, wanted to make sure you saw the listings I sent over. Let me know if any of them are worth a closer look!",
    "post_showing_feedback": "Hi {first_name}, thanks for touring with us! Any thoughts on the property? I'd love to hear your feedback.",
    "anniversary_checkin": "Hi {first_name}, it's been a year since your closing — hope you're loving the home! Let me know if you ever need anything, or if you know someone else looking to buy or sell.",
}


def render_template(template_id: str, contact) -> str:
    body = TEMPLATES.get(template_id, "Hi {first_name}, just checking in!")
    return body.format(first_name=contact.first_name)


def send_message(channel: str, contact, body: str) -> bool:
    """Returns True on (simulated) success. Replace internals with a real provider call."""
    if channel == "email":
        return _send_email(contact, body)
    if channel == "sms":
        return _send_sms(contact, body)
    logger.warning("Unknown channel %s for contact %s", channel, contact.id)
    return False


def _send_email(contact, body: str) -> bool:
    if not contact.email:
        logger.warning("No email on file for contact %s, skipping", contact.id)
        return False
    # TODO: replace with SendGrid/SES call
    logger.info("EMAIL -> %s: %s", contact.email, body)
    return True


def _send_sms(contact, body: str) -> bool:
    if not contact.phone:
        logger.warning("No phone on file for contact %s, skipping", contact.id)
        return False
    # TODO: replace with Twilio call
    logger.info("SMS -> %s: %s", contact.phone, body)
    return True
