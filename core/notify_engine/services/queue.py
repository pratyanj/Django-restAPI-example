"""
notify_engine/services/queue.py

Email sending — Celery async task and synchronous fallback.

The engine dispatches emails through `send_email_task` (Celery) when
available, or through `send_email_sync` as a fallback when Celery/Redis
is not running (e.g. during development).

Both paths:
    1. Create an EmailLog record with status='pending'.
    2. Build and send the EmailMessage.
    3. Optionally attach a PDF.
    4. Update the log to 'sent' or 'failed'.
"""

import logging
from typing import Any

from django.core.mail import EmailMessage

from ..models import EmailLog
from .pdf_generator import generate_pdf

logger = logging.getLogger(__name__)


def _build_and_send(
    event_name: str,
    to_email: str,
    cc_email: str,
    subject: str,
    body: str,
    attach_pdf: bool = False,
    pdf_template_code: str = "",
    context: dict[str, Any] | None = None,
) -> EmailLog:
    """
    Core send logic shared by async and sync paths.

    Creates the audit log, builds the message, attaches PDFs,
    sends the message, and updates the log status.
    """
    log = EmailLog.objects.create(
        event_name=event_name,
        to_email=to_email,
        cc_email=cc_email,
        subject=subject,
        body=body,
        status=EmailLog.Status.PENDING,
    )

    try:
        cc_list = [addr.strip() for addr in cc_email.split(",") if addr.strip()]

        msg = EmailMessage(
            subject=subject,
            body=body,
            to=[to_email],
            cc=cc_list,
        )
        msg.content_subtype = "html"

        # Attach PDF if configured — pass the actual context, not empty dict
        if attach_pdf and pdf_template_code:
            pdf_context = context or {}
            pdf_path = generate_pdf(pdf_template_code, context=pdf_context)
            msg.attach_file(pdf_path)
            log.attachment_path = pdf_path
            logger.info("PDF attached: %s", pdf_path)

        msg.send()
        log.status = EmailLog.Status.SENT
        logger.info("Email sent: event=%s, to=%s", event_name, to_email)

    except Exception as exc:
        log.status = EmailLog.Status.FAILED
        log.error_message = str(exc)
        logger.exception("Email send failed: event=%s, to=%s", event_name, to_email)
        raise

    finally:
        log.save()

    return log


# ---------------------------------------------------------------------------
# Celery async task
# ---------------------------------------------------------------------------

try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def send_email_task(
        self,
        event_name: str,
        to_email: str,
        cc_email: str,
        subject: str,
        body: str,
        attach_pdf: bool = False,
        pdf_template_code: str = "",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Celery task wrapper — delegates to _build_and_send with retry logic."""
        try:
            _build_and_send(
                event_name=event_name,
                to_email=to_email,
                cc_email=cc_email,
                subject=subject,
                body=body,
                attach_pdf=attach_pdf,
                pdf_template_code=pdf_template_code,
                context=context,
            )
        except Exception as exc:
            raise self.retry(exc=exc)

except ImportError:
    logger.info("Celery not installed — async email sending disabled.")
    send_email_task = None


# ---------------------------------------------------------------------------
# Synchronous fallback
# ---------------------------------------------------------------------------


def send_email_sync(
    event_name: str,
    to_email: str,
    cc_email: str,
    subject: str,
    body: str,
    attach_pdf: bool = False,
    pdf_template_code: str = "",
    context: dict[str, Any] | None = None,
) -> EmailLog:
    """
    Synchronous email send — used when Celery is unavailable.

    Returns the EmailLog record for the sent (or failed) email.
    """
    return _build_and_send(
        event_name=event_name,
        to_email=to_email,
        cc_email=cc_email,
        subject=subject,
        body=body,
        attach_pdf=attach_pdf,
        pdf_template_code=pdf_template_code,
        context=context,
    )