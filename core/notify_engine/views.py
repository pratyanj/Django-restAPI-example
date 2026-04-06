"""
notify_engine/views.py

API views providing full Swagger-documented CRUD for the notification engine
models plus the demo enquiry endpoint.

ViewSets:
    EmailMasterViewSet      – CRUD for email notification rules.
    EmailTemplateTagViewSet – CRUD for template tag mappings.
    EmailLogViewSet         – Read-only access to email audit logs.
    EnquiryCreateView       – Demo POST that triggers a notification.
"""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import filters, generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .crm_models import Enquiry
from .filters import EmailLogFilter, EmailMasterFilter
from .models import EmailLog, EmailMaster, EmailTemplateTag
from .serializers import (
    EmailLogSerializer,
    EmailMasterSerializer,
    EmailTemplateTagSerializer,
    EnquirySerializer,
)
from .services.engine import trigger_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EmailMaster — full CRUD
# ---------------------------------------------------------------------------


class EmailMasterViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for email notification rules.

    list:    List all email rules with filtering & search.
    create:  Create a new email rule.
    read:    Retrieve a specific email rule.
    update:  Full update of an email rule.
    partial_update: Partial update of an email rule.
    destroy: Delete an email rule.
    """

    queryset = EmailMaster.objects.all()
    serializer_class = EmailMasterSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmailMasterFilter
    search_fields = ["event_name", "module_name", "subject_template"]
    ordering_fields = ["event_name", "module_name", "created_at", "updated_at"]
    ordering = ["module_name", "event_name"]

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        """Toggle the is_active flag on an email rule."""
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active", "updated_at"])
        serializer = self.get_serializer(rule)
        return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# EmailTemplateTag — full CRUD
# ---------------------------------------------------------------------------


class EmailTemplateTagViewSet(viewsets.ModelViewSet):
    """
    CRUD operations for email template tag mappings.

    list:    List all template tags with search.
    create:  Create a new template tag mapping.
    read:    Retrieve a specific template tag.
    update:  Full update of a template tag.
    partial_update: Partial update of a template tag.
    destroy: Delete a template tag.
    """

    queryset = EmailTemplateTag.objects.all()
    serializer_class = EmailTemplateTagSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["module_name", "source_table"]
    search_fields = ["tag_name", "source_table", "source_field", "module_name"]
    ordering_fields = ["tag_name", "module_name"]
    ordering = ["module_name", "tag_name"]


# ---------------------------------------------------------------------------
# EmailLog — read-only
# ---------------------------------------------------------------------------


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only access to the email audit log.

    list:    List all email logs with filtering, search & ordering.
    read:    Retrieve a specific email log entry.
    """

    queryset = EmailLog.objects.all()
    serializer_class = EmailLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmailLogFilter
    search_fields = ["event_name", "to_email", "subject"]
    ordering_fields = ["created_at", "status", "event_name"]
    ordering = ["-created_at"]


# ---------------------------------------------------------------------------
# Enquiry — demo endpoint (triggers notification)
# ---------------------------------------------------------------------------


class EnquiryCreateView(generics.CreateAPIView):
    """
    Create a new enquiry and trigger an email notification.

    This endpoint creates an enquiry record and automatically sends
    an email notification based on configured email rules.
    """

    serializer_class = EnquirySerializer
    queryset = Enquiry.objects.all()

    @swagger_auto_schema(
        operation_description="Create a new enquiry and trigger email notification.",
        responses={
            201: openapi.Response("Enquiry created successfully", EnquirySerializer),
            400: "Bad Request — Invalid data",
        },
        tags=["Enquiry"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Save via serializer (single create) then fire the notification event."""
        enquiry = serializer.save()
        logger.info("Enquiry created: id=%s, email=%s", enquiry.pk, enquiry.email)
        trigger_event("enquiry_created", "crm", enquiry)