"""
notify_engine/models.py

Core models for the dynamic email notification engine.

Models:
    EmailMaster       – Rules that map business events to email templates.
    EmailTemplateTag  – Lookup for template tag → source field resolution.
    EmailLog          – Audit log of every email sent (or failed) through the engine.
"""

from django.db import models


class EmailMaster(models.Model):
    """
    Defines an email notification rule.

    Each rule binds a (event_name, module_name) pair to a recipient type,
    subject/body templates, and optional PDF attachment configuration.
    When a business event fires, the engine looks up matching active rules
    and composes/sends the email accordingly.
    """

    class ToType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        USER = "user", "User"
        DYNAMIC = "dynamic", "Dynamic"
        STATIC = "static", "Static"

    class CcType(models.TextChoices):
        STATIC = "static", "Static"
        DYNAMIC = "dynamic", "Dynamic"

    event_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Business event identifier, e.g. 'enquiry_created'.",
    )
    module_name = models.CharField(
        max_length=100,
        help_text="Module/app that owns this event, e.g. 'crm'.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Disabled rules are ignored by the engine.",
    )
    to_send = models.BooleanField(
        default=True,
        help_text="Master toggle — set to False to suppress sending.",
    )
    to_type = models.CharField(
        max_length=20,
        choices=ToType.choices,
        help_text="How the TO address is resolved.",
    )
    to_value = models.CharField(
        max_length=255,
        help_text="Dotted field path (e.g. 'customer.email') or a static email address.",
    )
    is_cc = models.BooleanField(
        default=False,
        help_text="Whether CC recipients should be included.",
    )
    cc_type = models.CharField(
        max_length=20,
        choices=CcType.choices,
        blank=True,
        default="",
        help_text="How the CC address is resolved.",
    )
    cc_value = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="CC field path or comma-separated static emails.",
    )
    subject_template = models.CharField(
        max_length=500,
        help_text="Subject line with {{tag}} placeholders.",
    )
    body_template = models.TextField(
        help_text="HTML body with {{tag}} placeholders.",
    )
    attach_pdf = models.BooleanField(
        default=False,
        help_text="Whether to attach a PDF to the email.",
    )
    pdf_template_code = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Key into the PDF_REGISTRY, e.g. 'enquiry_pdf'.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event_name", "module_name")
        ordering = ["module_name", "event_name"]
        verbose_name = "Email Rule"
        verbose_name_plural = "Email Rules"

    def __str__(self) -> str:
        status = "✓" if self.is_active else "✗"
        return f"[{status}] {self.module_name}/{self.event_name}"


class EmailTemplateTag(models.Model):
    """
    Maps a template tag name to its data source.

    The tag_resolver uses these records to understand where each {{tag}}
    fetches its value from (which table, which field, via which relation).
    """

    tag_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Tag identifier used in templates, e.g. 'customer_name'.",
    )
    source_table = models.CharField(
        max_length=100,
        help_text="Django model (app_label.ModelName) that holds the data.",
    )
    source_field = models.CharField(
        max_length=100,
        help_text="Field name on the source model.",
    )
    relation_key = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="FK/relation path to traverse from the event instance.",
    )
    module_name = models.CharField(
        max_length=100,
        help_text="Module this tag belongs to.",
    )

    class Meta:
        ordering = ["module_name", "tag_name"]
        verbose_name = "Template Tag"
        verbose_name_plural = "Template Tags"

    def __str__(self) -> str:
        return f"{self.tag_name} → {self.source_table}.{self.source_field}"


class EmailLog(models.Model):
    """
    Immutable audit record for every email the engine processes.

    Created as 'pending' before sending; updated to 'sent' or 'failed'
    after the send attempt completes.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    event_name = models.CharField(
        max_length=100,
        db_index=True,
        help_text="The event that triggered this email.",
    )
    to_email = models.EmailField(help_text="Recipient email address.")
    cc_email = models.TextField(
        blank=True,
        default="",
        help_text="Comma-separated CC addresses.",
    )
    subject = models.CharField(max_length=500)
    body = models.TextField()
    attachment_path = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Filesystem path to the attached PDF, if any.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Populated when status is 'failed'.",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"

    def __str__(self) -> str:
        return f"[{self.status}] {self.event_name} → {self.to_email}"