"""
notify_engine/serializers.py

DRF serializers for every model in the notification engine.

Serializers:
    EmailMasterSerializer      – Full CRUD for email rules.
    EmailTemplateTagSerializer – Full CRUD for template tags.
    EmailLogSerializer         – Read-only audit log serializer.
    EnquirySerializer          – Demo enquiry creation (triggers notification).
"""

from rest_framework import serializers

from .crm_models import Enquiry
from .models import EmailLog, EmailMaster, EmailTemplateTag


# ---------------------------------------------------------------------------
# Core notification model serializers
# ---------------------------------------------------------------------------


class EmailMasterSerializer(serializers.ModelSerializer):
    """Serializer for email notification rules (EmailMaster)."""

    class Meta:
        model = EmailMaster
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        """Cross-field validation for CC and PDF configuration."""
        # If is_cc is True, cc_type and cc_value are required
        if attrs.get("is_cc", False):
            if not attrs.get("cc_type"):
                raise serializers.ValidationError(
                    {"cc_type": "CC type is required when CC is enabled."}
                )
            if not attrs.get("cc_value"):
                raise serializers.ValidationError(
                    {"cc_value": "CC value is required when CC is enabled."}
                )

        # If attach_pdf is True, pdf_template_code is required
        if attrs.get("attach_pdf", False):
            if not attrs.get("pdf_template_code"):
                raise serializers.ValidationError(
                    {
                        "pdf_template_code": "PDF template code is required when PDF attachment is enabled."
                    }
                )

        return attrs


class EmailTemplateTagSerializer(serializers.ModelSerializer):
    """Serializer for template tag mappings (EmailTemplateTag)."""

    class Meta:
        model = EmailTemplateTag
        fields = "__all__"
        read_only_fields = ("id",)


class EmailLogSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for email audit logs.

    Logs are created internally by the engine and should never be
    created or modified through the API.
    """

    class Meta:
        model = EmailLog
        fields = "__all__"
        read_only_fields = [f.name for f in EmailLog._meta.get_fields()]


# ---------------------------------------------------------------------------
# Demo / CRM serializers
# ---------------------------------------------------------------------------


class EnquirySerializer(serializers.ModelSerializer):
    """Serializer for the demo Enquiry model — triggers a notification on create."""

    class Meta:
        model = Enquiry
        fields = "__all__"
        read_only_fields = ("id", "created_at")
