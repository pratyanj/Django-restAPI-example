"""
notify_engine/admin.py

Django admin configuration for the notification engine models.
"""

from django.contrib import admin

from .models import EmailLog, EmailMaster, EmailTemplateTag


@admin.register(EmailMaster)
class EmailMasterAdmin(admin.ModelAdmin):
    list_display = (
        "event_name",
        "module_name",
        "is_active",
        "to_send",
        "to_type",
        "is_cc",
        "updated_at",
    )
    list_filter = ("is_active", "to_send", "module_name", "to_type")
    search_fields = ("event_name", "module_name", "subject_template")
    list_editable = ("is_active", "to_send")
    list_per_page = 25
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (
            "Event Binding",
            {"fields": ("event_name", "module_name", "is_active", "to_send")},
        ),
        (
            "Recipient",
            {"fields": ("to_type", "to_value", "is_cc", "cc_type", "cc_value")},
        ),
        (
            "Template",
            {"fields": ("subject_template", "body_template")},
        ),
        (
            "PDF Attachment",
            {
                "classes": ("collapse",),
                "fields": ("attach_pdf", "pdf_template_code"),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(EmailTemplateTag)
class EmailTemplateTagAdmin(admin.ModelAdmin):
    list_display = ("tag_name", "source_table", "source_field", "module_name")
    list_filter = ("module_name",)
    search_fields = ("tag_name", "source_table", "module_name")
    list_per_page = 25


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("event_name", "to_email", "status", "subject", "created_at")
    list_filter = ("status", "event_name", "created_at")
    search_fields = ("to_email", "subject", "event_name")
    readonly_fields = ("created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        """Logs are created by the engine, not manually."""
        return False

    def has_change_permission(self, request, obj=None):
        """Logs are immutable audit records."""
        return False
