"""
notify_engine/urls.py

URL configuration for the notification engine API.

Registers DRF router-based ViewSets for full CRUD on notification models
and the demo enquiry endpoint.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EmailLogViewSet,
    EmailMasterViewSet,
    EmailTemplateTagViewSet,
    EnquiryCreateView,
)

router = DefaultRouter()
router.register(r"email-rules", EmailMasterViewSet, basename="email-rules")
router.register(r"template-tags", EmailTemplateTagViewSet, basename="template-tags")
router.register(r"email-logs", EmailLogViewSet, basename="email-logs")

urlpatterns = [
    path("", include(router.urls)),
    path("enquiry/", EnquiryCreateView.as_view(), name="enquiry-create"),
]
