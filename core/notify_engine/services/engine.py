"""
notify_engine/services/engine.py

Central orchestrator for the notification engine.

When a business event fires (e.g. enquiry created), call `trigger_event()`
with the event name, module, and the model instance. The engine will:

    1. Look up matching active rules in EmailMaster.
    2. Build a template context from the instance fields.
    3. Resolve recipient (TO / CC) addresses.
    4. Resolve {{tag}} placeholders in subject & body.
    5. Queue the email for async sending (Celery) or send synchronously.

Usage:
    from notify_engine.services.engine import trigger_event
    trigger_event('enquiry_created', 'crm', enquiry_obj)
"""

import logging
from typing import Any, Optional

from ..models import EmailMaster
from .recipient import resolve_cc, resolve_recipient
from .tag_resolver import build_context_from_instance, resolve_tags

logger = logging.getLogger(__name__)


def _send_email(
    event_name: str,
    to_email: str,
    cc_email: str,
    subject: str,
    body: str,
    attach_pdf: bool,
    pdf_template_code: str,
    context: dict[str, Any],
) -> None:
    """
    Dispatch email via Celery if available, otherwise send synchronously.

    This graceful fallback ensures the engine works in development
    environments where Celery/Redis may not be running.
    """
    try:
        from .queue import send_email_task

        send_email_task.delay(
            event_name=event_name,
            to_email=to_email,
            cc_email=cc_email,
            subject=subject,
            body=body,
            attach_pdf=attach_pdf,
            pdf_template_code=pdf_template_code,
            context=context,
        )
        logger.info("Email queued (Celery): event=%s, to=%s", event_name, to_email)
    except Exception as exc:
        logger.warning(
            "Celery unavailable (%s). Sending synchronously for event=%s.",
            exc,
            event_name,
        )
        from .queue import send_email_sync

        send_email_sync(
            event_name=event_name,
            to_email=to_email,
            cc_email=cc_email,
            subject=subject,
            body=body,
            attach_pdf=attach_pdf,
            pdf_template_code=pdf_template_code,
            context=context,
        )


def trigger_event(
    event_name: str,
    module_name: str,
    instance: Any,
    extra_context: Optional[dict] = None,
) -> None:
    """
    Fire a business event and send any configured email notifications.

    Args:
        event_name:    Unique event key, e.g. 'enquiry_created'.
        module_name:   Module that owns the event, e.g. 'crm'.
        instance:      The Django model instance associated with the event.
        extra_context: Additional key-value pairs merged into the template context.
    """
    logger.debug(
        "trigger_event called: event=%s, module=%s, instance=%r",
        event_name,
        module_name,
        instance,
    )

    try:
        rule = EmailMaster.objects.get(
            event_name=event_name,
            module_name=module_name,
            is_active=True,
            to_send=True,
        )
    except EmailMaster.DoesNotExist:
        logger.info(
            "No active email rule for event=%s, module=%s — skipping.",
            event_name,
            module_name,
        )
        return
    except EmailMaster.MultipleObjectsReturned:
        logger.error(
            "Multiple active rules found for event=%s, module=%s. "
            "Check unique_together constraint. Using first match.",
            event_name,
            module_name,
        )
        rule = EmailMaster.objects.filter(
            event_name=event_name,
            module_name=module_name,
            is_active=True,
            to_send=True,
        ).first()

    # Build template context from the model instance
    context = build_context_from_instance(instance, extra_context)

    # Resolve addresses
    to_email = resolve_recipient(rule, instance, context)
    if not to_email:
        logger.warning(
            "Could not resolve TO address for event=%s. Rule: %s. Skipping.",
            event_name,
            rule,
        )
        return

    cc_email = resolve_cc(rule, instance, context) if rule.is_cc else ""

    # Resolve template tags in subject & body
    subject = resolve_tags(rule.subject_template, context)
    body = resolve_tags(rule.body_template, context)

    logger.info(
        "Dispatching email: event=%s, to=%s, cc=%s, subject=%s",
        event_name,
        to_email,
        cc_email or "(none)",
        subject[:80],
    )

    _send_email(
        event_name=event_name,
        to_email=to_email,
        cc_email=cc_email,
        subject=subject,
        body=body,
        attach_pdf=rule.attach_pdf,
        pdf_template_code=rule.pdf_template_code,
        context=context,
    )