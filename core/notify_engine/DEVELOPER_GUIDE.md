# Notify Engine — Complete Developer Build Guide

> This guide walks a developer through building the `notify_engine` module from absolute scratch.  
> Follow every step in order. Do not skip the Settings section.

---

## Table of Contents

1. [Prerequisites & Stack](#1-prerequisites--stack)
2. [Project Bootstrap](#2-project-bootstrap)
3. [Phase 1 — Project Setup & Dependencies](#3-phase-1--project-setup--dependencies)
4. [Phase 2 — Core Database Models](#4-phase-2--core-database-models)
5. [Phase 3 — Services Layer](#5-phase-3--services-layer)
6. [Phase 4 — REST API (Serializers, Views, URLs)](#6-phase-4--rest-api-serializers-views-urls)
7. [Phase 5 — Filters & Admin](#7-phase-5--filters--admin)
8. [Phase 6 — Swagger Integration](#8-phase-6--swagger-integration)
9. [Settings Reference (Complete)](#9-settings-reference-complete)
10. [Running & Verifying](#10-running--verifying)
11. [Using the Engine from Other Apps](#11-using-the-engine-from-other-apps)
12. [API Endpoint Reference](#12-api-endpoint-reference)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Prerequisites & Stack

### Required Software

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Python | 3.12+ | [python.org](https://python.org) |
| uv (package manager) | latest | `pip install uv` |
| Git | any | [git-scm.com](https://git-scm.com) |

### Python Dependencies

| Package | Purpose |
|---------|---------|
| `django` | Web framework |
| `djangorestframework` | REST API |
| `drf-yasg` | Swagger / OpenAPI docs |
| `django-filter` | Query filtering for API |
| `celery` | Async task queue (optional) |
| `redis` | Celery broker (optional) |
| `reportlab` | PDF generation (ReportLab renderer) |
| `xhtml2pdf` | PDF generation (HTML renderer) |

---

## 2. Project Bootstrap

If starting from zero, create the Django project first. Skip to [Phase 1](#3-phase-1--project-setup--dependencies) if you already have a project.

```powershell
# Create project directory
mkdir Django-restAPI-example
cd Django-restAPI-example

# Initialize uv project
uv init
uv add django djangorestframework drf-yasg django-filter

# Create Django project inside a 'core' subfolder
uv run django-admin startproject core .

# Verify structure
ls
# manage.py  core/  pyproject.toml
```

---

## 3. Phase 1 — Project Setup & Dependencies

### Step 1.1 — Install all dependencies

```powershell
uv add django djangorestframework drf-yasg django-filter
uv add celery        # optional — for async email sending
uv add reportlab     # optional — for PDF generation
uv add xhtml2pdf     # optional — for HTML-to-PDF
```

> **Note:** `celery` and `reportlab` are optional. The engine gracefully degrades:
> - Without Celery → emails send synchronously
> - Without reportlab → PDF features raise `ImportError` at runtime only when used

### Step 1.2 — Create the notify_engine app

```powershell
uv run python manage.py startapp notify_engine
```

This creates:
```
notify_engine/
├── __init__.py
├── admin.py
├── apps.py
├── migrations/__init__.py
├── models.py
├── tests.py
└── views.py
```

### Step 1.3 — Create the services directory

```powershell
mkdir notify_engine/services
New-Item notify_engine/services/__init__.py
New-Item notify_engine/services/engine.py
New-Item notify_engine/services/queue.py
New-Item notify_engine/services/tag_resolver.py
New-Item notify_engine/services/recipient.py
New-Item notify_engine/services/pdf_generator.py
```

Also create:
```powershell
New-Item notify_engine/filters.py
New-Item notify_engine/crm_models.py   # demo CRM model
New-Item notify_engine/serializers.py
New-Item notify_engine/urls.py
```

### Step 1.4 — Register the app in settings

Open `core/settings.py` and add to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'drf_yasg',
    'django_filters',

    # Local apps
    'notify_engine',
]
```

---

## 4. Phase 2 — Core Database Models

### Step 2.1 — Write `notify_engine/models.py`

Create three models: `EmailMaster`, `EmailTemplateTag`, `EmailLog`.

```python
# notify_engine/models.py
from django.db import models


class EmailMaster(models.Model):
    class ToType(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        USER     = "user",     "User"
        DYNAMIC  = "dynamic",  "Dynamic"
        STATIC   = "static",   "Static"

    class CcType(models.TextChoices):
        STATIC  = "static",  "Static"
        DYNAMIC = "dynamic", "Dynamic"

    event_name       = models.CharField(max_length=100, db_index=True,
                           help_text="Business event identifier, e.g. 'enquiry_created'.")
    module_name      = models.CharField(max_length=100,
                           help_text="Module/app that owns this event, e.g. 'crm'.")
    is_active        = models.BooleanField(default=True)
    to_send          = models.BooleanField(default=True)
    to_type          = models.CharField(max_length=20, choices=ToType.choices)
    to_value         = models.CharField(max_length=255,
                           help_text="Dotted field path or static email address.")
    is_cc            = models.BooleanField(default=False)
    cc_type          = models.CharField(max_length=20, choices=CcType.choices,
                           blank=True, default="")
    cc_value         = models.CharField(max_length=500, blank=True, default="")
    subject_template = models.CharField(max_length=500)
    body_template    = models.TextField()
    attach_pdf       = models.BooleanField(default=False)
    pdf_template_code = models.CharField(max_length=100, blank=True, default="")
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("event_name", "module_name")
        ordering = ["module_name", "event_name"]
        verbose_name = "Email Rule"
        verbose_name_plural = "Email Rules"

    def __str__(self):
        return f"[{'✓' if self.is_active else '✗'}] {self.module_name}/{self.event_name}"


class EmailTemplateTag(models.Model):
    tag_name     = models.CharField(max_length=100, unique=True)
    source_table = models.CharField(max_length=100)
    source_field = models.CharField(max_length=100)
    relation_key = models.CharField(max_length=100, blank=True, default="")
    module_name  = models.CharField(max_length=100)

    class Meta:
        ordering = ["module_name", "tag_name"]
        verbose_name = "Template Tag"
        verbose_name_plural = "Template Tags"

    def __str__(self):
        return f"{self.tag_name} → {self.source_table}.{self.source_field}"


class EmailLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT    = "sent",    "Sent"
        FAILED  = "failed",  "Failed"

    event_name      = models.CharField(max_length=100, db_index=True)
    to_email        = models.EmailField()
    cc_email        = models.TextField(blank=True, default="")
    subject         = models.CharField(max_length=500)
    body            = models.TextField()
    attachment_path = models.CharField(max_length=500, blank=True, default="")
    status          = models.CharField(max_length=20, choices=Status.choices,
                          default=Status.PENDING, db_index=True)
    error_message   = models.TextField(blank=True, default="")
    created_at      = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"

    def __str__(self):
        return f"[{self.status}] {self.event_name} → {self.to_email}"
```

### Step 2.2 — Write `notify_engine/crm_models.py` (Demo Model)

```python
# notify_engine/crm_models.py
from django.db import models

class Enquiry(models.Model):
    name       = models.CharField(max_length=100)
    email      = models.EmailField()
    phone      = models.CharField(max_length=20, blank=True)
    message    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.email}"
```

### Step 2.3 — Run migrations

```powershell
uv run python manage.py makemigrations notify_engine
uv run python manage.py migrate
```

Expected output:
```
Migrations for 'notify_engine':
  notify_engine/migrations/0001_initial.py
    - Create model EmailLog
    - Create model EmailTemplateTag
    - Create model EmailMaster

Operations to perform:
  Apply all migrations: admin, auth, ...
Running migrations:
  Applying notify_engine.0001_initial... OK
```

### Step 2.4 — Verify models in Django shell

```powershell
uv run python manage.py shell
```

```python
from notify_engine.models import EmailMaster, EmailTemplateTag, EmailLog
print(EmailMaster.objects.count())   # 0
print(EmailLog.objects.count())      # 0
exit()
```

---

## 5. Phase 3 — Services Layer

Build the 5 service files in this order: `tag_resolver` → `recipient` → `pdf_generator` → `queue` → `engine`

### Step 3.1 — `services/tag_resolver.py`

```python
# notify_engine/services/tag_resolver.py
import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Supports {{name}}, {{customer.email}}, {{order_number}}
_TAG_PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def resolve_tags(template: str, context: dict[str, Any]) -> str:
    """Replace {{tag}} placeholders using a flat context dict."""
    def _replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        value = context.get(key)
        if value is None:
            logger.debug("Unresolved template tag: {{%s}}", key)
            return match.group(0)   # keep it intact so you can spot it
        return str(value)
    return _TAG_PATTERN.sub(_replacer, template)


def build_context_from_instance(instance: Any, extra: Optional[dict] = None) -> dict[str, Any]:
    """Auto-build context dict from a Django model instance + optional extras."""
    context: dict[str, Any] = {}

    if instance is None:
        if extra:
            context.update(extra)
        return context

    for field in instance._meta.get_fields():
        if not hasattr(field, "attname") and not hasattr(field, "name"):
            continue
        field_name = getattr(field, "name", None)
        if field_name is None:
            continue
        try:
            value = getattr(instance, field_name, None)
            if callable(value) and not isinstance(value, str):
                continue
            if value is not None:
                context[field_name] = value
                # FK traversal — one level deep
                if hasattr(field, "related_model") and field.related_model is not None:
                    for rf in value._meta.get_fields():
                        rfn = getattr(rf, "name", None)
                        if rfn is None:
                            continue
                        try:
                            rv = getattr(value, rfn, None)
                            if rv is not None and not callable(rv):
                                context[f"{field_name}.{rfn}"] = rv
                        except Exception:
                            pass
        except Exception:
            logger.debug("Could not read field '%s'", field_name)

    if extra:
        context.update(extra)
    return context
```

### Step 3.2 — `services/recipient.py`

```python
# notify_engine/services/recipient.py
import logging
from functools import reduce
from typing import Any, Optional

logger = logging.getLogger(__name__)


def resolve_recipient(rule: Any, instance: Any, context: dict) -> str:
    if rule.to_type == "static":
        return rule.to_value
    if rule.to_type in ("customer", "user", "dynamic"):
        email = _dotted_get(instance, rule.to_value)
        if not email:
            logger.warning("Could not resolve TO via '%s' on %r", rule.to_value, instance)
            return ""
        return str(email)
    logger.warning("Unknown to_type '%s'", rule.to_type)
    return ""


def resolve_cc(rule: Any, instance: Any, context: dict) -> str:
    if rule.cc_type == "static":
        return rule.cc_value
    if rule.cc_type == "dynamic":
        email = _dotted_get(instance, rule.cc_value)
        return str(email) if email else ""
    return ""


def _dotted_get(obj: Any, path: str) -> Optional[Any]:
    """Traverse dotted path: 'customer.email' → obj.customer.email"""
    if not path:
        return None
    try:
        return reduce(getattr, path.split("."), obj)
    except AttributeError:
        logger.debug("Path '%s' not found on %r", path, obj)
        return None
```

### Step 3.3 — `services/pdf_generator.py`

This file is long (~470 lines). Key sections:

```python
# notify_engine/services/pdf_generator.py

# 1. Configure output directory (reads from Django settings)
from django.conf import settings
PDF_OUTPUT_DIR = getattr(settings, 'NOTIFY_ENGINE_PDF_DIR',
                          os.path.join(tempfile.gettempdir(), 'notify_engine_pdfs'))
os.makedirs(PDF_OUTPUT_DIR, exist_ok=True)

# 2. BasePDFRenderer — abstract base class
class BasePDFRenderer(ABC):
    def _output_path(self, prefix='pdf') -> str: ...
    @abstractmethod
    def render(self, context: dict) -> str: ...

# 3. ReportLabRenderer — subclass and override build_story()
class ReportLabRenderer(BasePDFRenderer):
    title = 'Document'
    filename_prefix = 'doc'
    def build_story(self, context, styles) -> list: ...
    def render(self, context) -> str: ...

# 4. HTMLRenderer — set template_name or override get_html()
class HTMLRenderer(BasePDFRenderer):
    template_name = ''
    backend = 'xhtml2pdf'   # or 'weasyprint'
    def render(self, context) -> str: ...

# 5. Built-in renderers
class EnquiryPDFRenderer(ReportLabRenderer): ...
class QuotationPDFRenderer(ReportLabRenderer): ...
class InvoicePDFRenderer(ReportLabRenderer): ...

# 6. Registry
PDF_REGISTRY = {
    'enquiry_pdf':   EnquiryPDFRenderer(),
    'quotation_pdf': QuotationPDFRenderer(),
    'invoice_pdf':   InvoicePDFRenderer(),
}

# 7. Public API
def generate_pdf(template_code: str, context: dict) -> str:
    """Returns absolute path to generated PDF file."""
    renderer = PDF_REGISTRY.get(template_code)
    if renderer is None:
        raise ValueError(f"No renderer for '{template_code}'")
    ...
```

> See the full file at `notify_engine/services/pdf_generator.py`

### Step 3.4 — `services/queue.py`

```python
# notify_engine/services/queue.py
import logging
from typing import Any
from django.core.mail import EmailMessage
from ..models import EmailLog
from .pdf_generator import generate_pdf

logger = logging.getLogger(__name__)


def _build_and_send(event_name, to_email, cc_email, subject, body,
                    attach_pdf=False, pdf_template_code='', context=None):
    """Core send logic — creates log, sends, updates log."""
    log = EmailLog.objects.create(
        event_name=event_name, to_email=to_email, cc_email=cc_email,
        subject=subject, body=body, status=EmailLog.Status.PENDING,
    )
    try:
        cc_list = [a.strip() for a in cc_email.split(',') if a.strip()]
        msg = EmailMessage(subject=subject, body=body, to=[to_email], cc=cc_list)
        msg.content_subtype = 'html'
        if attach_pdf and pdf_template_code:
            pdf_path = generate_pdf(pdf_template_code, context=context or {})
            msg.attach_file(pdf_path)
            log.attachment_path = pdf_path
        msg.send()
        log.status = EmailLog.Status.SENT
    except Exception as exc:
        log.status = EmailLog.Status.FAILED
        log.error_message = str(exc)
        raise
    finally:
        log.save()
    return log


# --- Celery async task (optional) ---
try:
    from celery import shared_task

    @shared_task(bind=True, max_retries=3, default_retry_delay=60)
    def send_email_task(self, event_name, to_email, cc_email, subject, body,
                        attach_pdf=False, pdf_template_code='', context=None):
        try:
            _build_and_send(event_name, to_email, cc_email, subject, body,
                            attach_pdf, pdf_template_code, context)
        except Exception as exc:
            raise self.retry(exc=exc)

except ImportError:
    send_email_task = None


# --- Synchronous fallback ---
def send_email_sync(event_name, to_email, cc_email, subject, body,
                    attach_pdf=False, pdf_template_code='', context=None):
    return _build_and_send(event_name, to_email, cc_email, subject, body,
                           attach_pdf, pdf_template_code, context)
```

### Step 3.5 — `services/engine.py`

```python
# notify_engine/services/engine.py
import logging
from typing import Any, Optional
from ..models import EmailMaster
from .recipient import resolve_cc, resolve_recipient
from .tag_resolver import build_context_from_instance, resolve_tags

logger = logging.getLogger(__name__)


def trigger_event(event_name: str, module_name: str,
                  instance: Any, extra_context: Optional[dict] = None) -> None:
    """
    Main public function — call this from any Django view/signal/task.
    """
    logger.debug("trigger_event: event=%s, module=%s", event_name, module_name)

    try:
        rule = EmailMaster.objects.get(
            event_name=event_name, module_name=module_name,
            is_active=True, to_send=True,
        )
    except EmailMaster.DoesNotExist:
        logger.info("No rule for event=%s, module=%s — skipping", event_name, module_name)
        return
    except EmailMaster.MultipleObjectsReturned:
        logger.error("Multiple rules for event=%s, module=%s", event_name, module_name)
        rule = EmailMaster.objects.filter(
            event_name=event_name, module_name=module_name,
            is_active=True, to_send=True,
        ).first()

    context  = build_context_from_instance(instance, extra_context)
    to_email = resolve_recipient(rule, instance, context)
    if not to_email:
        logger.warning("Empty TO for event=%s — skipping", event_name)
        return

    cc_email = resolve_cc(rule, instance, context) if rule.is_cc else ""
    subject  = resolve_tags(rule.subject_template, context)
    body     = resolve_tags(rule.body_template, context)

    # Try Celery → fall back to sync
    try:
        from .queue import send_email_task
        send_email_task.delay(
            event_name=event_name, to_email=to_email, cc_email=cc_email,
            subject=subject, body=body, attach_pdf=rule.attach_pdf,
            pdf_template_code=rule.pdf_template_code, context=context,
        )
    except Exception as exc:
        logger.warning("Celery unavailable (%s), sending synchronously", exc)
        from .queue import send_email_sync
        send_email_sync(
            event_name=event_name, to_email=to_email, cc_email=cc_email,
            subject=subject, body=body, attach_pdf=rule.attach_pdf,
            pdf_template_code=rule.pdf_template_code, context=context,
        )
```

### Step 3.6 — `services/__init__.py`

```python
# notify_engine/services/__init__.py
from .engine import trigger_event  # noqa: F401
__all__ = ["trigger_event"]
```

---

## 6. Phase 4 — REST API (Serializers, Views, URLs)

### Step 4.1 — `notify_engine/serializers.py`

```python
# notify_engine/serializers.py
from rest_framework import serializers
from .crm_models import Enquiry
from .models import EmailLog, EmailMaster, EmailTemplateTag


class EmailMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailMaster
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")

    def validate(self, attrs):
        if attrs.get("is_cc", False):
            if not attrs.get("cc_type"):
                raise serializers.ValidationError(
                    {"cc_type": "CC type is required when CC is enabled."})
            if not attrs.get("cc_value"):
                raise serializers.ValidationError(
                    {"cc_value": "CC value is required when CC is enabled."})
        if attrs.get("attach_pdf", False):
            if not attrs.get("pdf_template_code"):
                raise serializers.ValidationError(
                    {"pdf_template_code": "PDF template code required when attach_pdf=True."})
        return attrs


class EmailTemplateTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplateTag
        fields = "__all__"
        read_only_fields = ("id",)


class EmailLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailLog
        fields = "__all__"
        read_only_fields = [f.name for f in EmailLog._meta.get_fields()]


class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = "__all__"
        read_only_fields = ("id", "created_at")
```

### Step 4.2 — `notify_engine/views.py`

```python
# notify_engine/views.py
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
from .serializers import (EmailLogSerializer, EmailMasterSerializer,
                           EmailTemplateTagSerializer, EnquirySerializer)
from .services.engine import trigger_event

logger = logging.getLogger(__name__)


class EmailMasterViewSet(viewsets.ModelViewSet):
    queryset = EmailMaster.objects.all()
    serializer_class = EmailMasterSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmailMasterFilter
    search_fields = ["event_name", "module_name", "subject_template"]
    ordering_fields = ["event_name", "module_name", "created_at", "updated_at"]

    @action(detail=True, methods=["post"], url_path="toggle-active")
    def toggle_active(self, request, pk=None):
        rule = self.get_object()
        rule.is_active = not rule.is_active
        rule.save(update_fields=["is_active", "updated_at"])
        return Response(self.get_serializer(rule).data)


class EmailTemplateTagViewSet(viewsets.ModelViewSet):
    queryset = EmailTemplateTag.objects.all()
    serializer_class = EmailTemplateTagSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["module_name", "source_table"]
    search_fields = ["tag_name", "source_table", "source_field", "module_name"]
    ordering_fields = ["tag_name", "module_name"]


class EmailLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmailLog.objects.all()
    serializer_class = EmailLogSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EmailLogFilter
    search_fields = ["event_name", "to_email", "subject"]
    ordering_fields = ["created_at", "status", "event_name"]
    ordering = ["-created_at"]


class EnquiryCreateView(generics.CreateAPIView):
    serializer_class = EnquirySerializer
    queryset = Enquiry.objects.all()

    @swagger_auto_schema(
        operation_description="Create enquiry + trigger email notification.",
        responses={201: openapi.Response("Created", EnquirySerializer), 400: "Bad Request"},
        tags=["Enquiry"],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        enquiry = serializer.save()
        logger.info("Enquiry created: id=%s, email=%s", enquiry.pk, enquiry.email)
        trigger_event("enquiry_created", "crm", enquiry)
```

### Step 4.3 — `notify_engine/urls.py`

```python
# notify_engine/urls.py
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import (EmailLogViewSet, EmailMasterViewSet,
                    EmailTemplateTagViewSet, EnquiryCreateView)

router = DefaultRouter()
router.register(r"email-rules",   EmailMasterViewSet,      basename="email-rules")
router.register(r"template-tags", EmailTemplateTagViewSet, basename="template-tags")
router.register(r"email-logs",    EmailLogViewSet,         basename="email-logs")

urlpatterns = [
    path("", include(router.urls)),
    path("enquiry/", EnquiryCreateView.as_view(), name="enquiry-create"),
]
```

### Step 4.4 — Register in project `core/urls.py`

```python
# core/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Django REST API",
        default_version="v1",
        description="API documentation with dynamic email notification system",
        contact=openapi.Contact(email="contact@api.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/",          include("API.urls")),         # your other apps
    path("api/notify/",   include("notify_engine.urls")),

    # Swagger docs
    re_path(r"^swagger(?P<format>\.json|\.yaml)$",
            schema_view.without_ui(cache_timeout=0), name="schema-json"),
    path("swagger/", schema_view.with_ui("swagger", cache_timeout=0), name="schema-swagger-ui"),
    path("redoc/",   schema_view.with_ui("redoc",   cache_timeout=0), name="schema-redoc"),
]
```

---

## 7. Phase 5 — Filters & Admin

### Step 5.1 — `notify_engine/filters.py`

```python
# notify_engine/filters.py
import django_filters
from .models import EmailLog, EmailMaster


class EmailMasterFilter(django_filters.FilterSet):
    event_name    = django_filters.CharFilter(lookup_expr="icontains")
    module_name   = django_filters.CharFilter(lookup_expr="iexact")
    is_active     = django_filters.BooleanFilter()
    to_send       = django_filters.BooleanFilter()
    to_type       = django_filters.ChoiceFilter(choices=EmailMaster.ToType.choices)
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = EmailMaster
        fields = ["event_name", "module_name", "is_active", "to_send",
                  "to_type", "created_after", "created_before"]


class EmailLogFilter(django_filters.FilterSet):
    event_name    = django_filters.CharFilter(lookup_expr="icontains")
    status        = django_filters.ChoiceFilter(choices=EmailLog.Status.choices)
    to_email      = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.DateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = EmailLog
        fields = ["event_name", "status", "to_email", "created_after", "created_before"]
```

### Step 5.2 — `notify_engine/admin.py`

```python
# notify_engine/admin.py
from django.contrib import admin
from .models import EmailLog, EmailMaster, EmailTemplateTag


@admin.register(EmailMaster)
class EmailMasterAdmin(admin.ModelAdmin):
    list_display  = ("event_name", "module_name", "is_active", "to_send",
                     "to_type", "is_cc", "updated_at")
    list_filter   = ("is_active", "to_send", "module_name", "to_type")
    search_fields = ("event_name", "module_name", "subject_template")
    list_editable = ("is_active", "to_send")
    list_per_page = 25
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Event Binding", {"fields": ("event_name", "module_name", "is_active", "to_send")}),
        ("Recipient",     {"fields": ("to_type", "to_value", "is_cc", "cc_type", "cc_value")}),
        ("Template",      {"fields": ("subject_template", "body_template")}),
        ("PDF Attachment", {"classes": ("collapse",),
                            "fields": ("attach_pdf", "pdf_template_code")}),
        ("Timestamps",    {"classes": ("collapse",),
                            "fields": ("created_at", "updated_at")}),
    )


@admin.register(EmailTemplateTag)
class EmailTemplateTagAdmin(admin.ModelAdmin):
    list_display  = ("tag_name", "source_table", "source_field", "module_name")
    list_filter   = ("module_name",)
    search_fields = ("tag_name", "source_table", "module_name")
    list_per_page = 25


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display  = ("event_name", "to_email", "status", "subject", "created_at")
    list_filter   = ("status", "event_name", "created_at")
    search_fields = ("to_email", "subject", "event_name")
    readonly_fields = ("created_at",)
    list_per_page = 25
    date_hierarchy = "created_at"

    def has_add_permission(self, request):    return False
    def has_change_permission(self, request, obj=None): return False
```

---

## 8. Phase 6 — Swagger Integration

Swagger is already configured in `core/urls.py` above.

### Verify it works

```powershell
uv run python manage.py runserver
```

Open: `http://127.0.0.1:8000/swagger/`

You should see all `notify` endpoints under a **notify** section:
- `GET/POST /api/notify/email-rules/`
- `GET/PUT/PATCH/DELETE/POST /api/notify/email-rules/{id}/`
- `POST /api/notify/email-rules/{id}/toggle-active/`
- `GET/POST /api/notify/template-tags/`
- `GET/PUT/PATCH/DELETE /api/notify/template-tags/{id}/`
- `GET /api/notify/email-logs/`
- `GET /api/notify/email-logs/{id}/`
- `POST /api/notify/enquiry/`

---

## 9. Settings Reference (Complete)

Add ALL of these to your `core/settings.py`:

```python
# ============================================================
# INSTALLED APPS — required third-party
# ============================================================
INSTALLED_APPS = [
    # Django built-ins
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party — ALL are required
    'rest_framework',       # Django REST framework
    'drf_yasg',             # Swagger UI
    'django_filters',       # API filtering

    # Your apps
    'notify_engine',        # The notification engine
    # 'your_other_app',
]


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================
REST_FRAMEWORK = {
    # Default filter backend — required for ?is_active=true etc.
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    # Pagination — all list endpoints return paginated results
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}


# ============================================================
# EMAIL CONFIGURATION
# Choose ONE backend based on your environment.
# ============================================================

# --- OPTION A: Development — print emails to console (no SMTP needed)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# --- OPTION B: Development — save emails to files
# EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
# EMAIL_FILE_PATH = BASE_DIR / 'sent_emails'

# --- OPTION C: Production — Gmail SMTP (requires App Password, not account password)
# EMAIL_BACKEND      = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST         = 'smtp.gmail.com'
# EMAIL_PORT         = 587
# EMAIL_USE_TLS      = True
# EMAIL_HOST_USER    = 'your-email@gmail.com'
# EMAIL_HOST_PASSWORD = 'your-16-char-app-password'  # Google App Password
# DEFAULT_FROM_EMAIL = 'your-email@gmail.com'

# --- OPTION D: Production — SendGrid / Mailgun / SES
# Use their SMTP relay credentials in the same format as Option C,
# or install their official Django package.


# ============================================================
# CELERY — ASYNC EMAIL QUEUE (optional but recommended)
# Requires: pip install celery redis
# Requires: Redis server running on localhost:6379
# ============================================================
CELERY_BROKER_URL       = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND   = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT   = ['json']
CELERY_TASK_SERIALIZER  = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE         = 'UTC'
# Without Celery → emails send synchronously. The engine handles this automatically.


# ============================================================
# NOTIFY ENGINE — custom settings
# ============================================================

# PDF output directory — where generated PDFs are saved temporarily
# Defaults to system temp dir if not set.
NOTIFY_ENGINE_PDF_DIR = BASE_DIR / 'media' / 'email_pdfs'


# ============================================================
# MEDIA FILES — needed if storing PDF attachments
# ============================================================
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# DATABASE
# ============================================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # For production, use PostgreSQL:
        # 'ENGINE': 'django.db.backends.postgresql',
        # 'NAME': 'your_db_name',
        # 'USER': 'your_db_user',
        # 'PASSWORD': 'your_db_password',
        # 'HOST': 'localhost',
        # 'PORT': '5432',
    }
}


# ============================================================
# SECURITY — update before going to production
# ============================================================
SECRET_KEY = 'django-insecure-...'   # Change this! Use env var in production.
DEBUG = True                          # Set to False in production
ALLOWED_HOSTS = []                    # Add your domain in production
```

### Gmail App Password Setup (for production email)

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Security → 2-Step Verification (must be ON)
3. Security → App passwords → Select app: Mail → Select device: Other
4. Copy the 16-character password → use as `EMAIL_HOST_PASSWORD`

> **Never use your Gmail account password directly.** Always use an App Password.

---

## 10. Running & Verifying

### Run migrations

```powershell
uv run python manage.py makemigrations notify_engine
uv run python manage.py migrate
```

### Create a superuser (for Admin access)

```powershell
uv run python manage.py createsuperuser
```

### Start the dev server

```powershell
uv run python manage.py runserver
```

### Run the Django system check (catches config errors)

```powershell
uv run python manage.py check
# Expected: System check identified no issues (0 silenced).
```

### Verify in browser

| URL | Expected |
|-----|----------|
| `http://127.0.0.1:8000/swagger/` | Swagger UI with all `notify` endpoints |
| `http://127.0.0.1:8000/redoc/` | ReDoc docs |
| `http://127.0.0.1:8000/admin/` | Admin login |
| `http://127.0.0.1:8000/api/notify/email-rules/` | `{"count": 0, "results": []}` |
| `http://127.0.0.1:8000/api/notify/email-logs/` | `{"count": 0, "results": []}` |

### Test with the `.http` file

Open `notify_engine/tests_api.http` in VS Code (requires **REST Client** extension).

**Quick smoke test — run in order:**

1. `1.1` — Create an email rule  
2. `1.3` — List rules → should return 1 result  
3. `4.1` — POST an enquiry → should appear in email-logs (console backend prints the email)  
4. `3.1` — List email logs → should show 1 record with `status=sent`  

---

## 11. Using the Engine from Other Apps

### Minimal usage (existing model)

```python
# your_app/views.py
from notify_engine.services.engine import trigger_event

class OrderCreateView(generics.CreateAPIView):
    def perform_create(self, serializer):
        order = serializer.save()
        trigger_event('order_placed', 'sales', order)
```

### With extra context

```python
trigger_event(
    'invoice_generated', 'billing', invoice,
    extra_context={
        'download_url': f'https://app.example.com/invoices/{invoice.pk}/download/',
        'support_email': 'support@example.com',
    }
)
```

### From a Django signal

```python
# your_app/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from notify_engine.services.engine import trigger_event
from .models import Order

@receiver(post_save, sender=Order)
def on_order_created(sender, instance, created, **kwargs):
    if created:
        trigger_event('order_created', 'sales', instance)
```

### Required: Create a matching EmailMaster rule

```
POST /api/notify/email-rules/
Content-Type: application/json

{
    "event_name": "order_placed",
    "module_name": "sales",
    "is_active": true,
    "to_send": true,
    "to_type": "dynamic",
    "to_value": "customer.email",
    "is_cc": false,
    "subject_template": "Order #{{order_number}} Confirmed",
    "body_template": "<h2>Hi {{customer.name}},</h2><p>Your order is confirmed.</p>",
    "attach_pdf": false,
    "pdf_template_code": ""
}
```

---

## 12. API Endpoint Reference

**Base URL:** `http://127.0.0.1:8000/api/notify/`

### Email Rules

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/email-rules/` | — | List all rules |
| `POST` | `/email-rules/` | — | Create a rule |
| `GET` | `/email-rules/{id}/` | — | Get one rule |
| `PUT` | `/email-rules/{id}/` | — | Full update |
| `PATCH` | `/email-rules/{id}/` | — | Partial update |
| `DELETE` | `/email-rules/{id}/` | — | Delete |
| `POST` | `/email-rules/{id}/toggle-active/` | — | Flip is_active |

**List query params:** `event_name`, `module_name`, `is_active`, `to_send`, `to_type`, `created_after`, `created_before`, `search`, `ordering`, `page`

### Template Tags

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/template-tags/` | List all tags |
| `POST` | `/template-tags/` | Create a tag |
| `GET` | `/template-tags/{id}/` | Get one tag |
| `PUT` | `/template-tags/{id}/` | Full update |
| `PATCH` | `/template-tags/{id}/` | Partial update |
| `DELETE` | `/template-tags/{id}/` | Delete |

**List query params:** `module_name`, `source_table`, `search`, `ordering`, `page`

### Email Logs (Read-Only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/email-logs/` | List all logs |
| `GET` | `/email-logs/{id}/` | Get one log |

**List query params:** `status`, `event_name`, `to_email`, `created_after`, `created_before`, `search`, `ordering`, `page`

### Enquiry (Demo)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/enquiry/` | Create enquiry + fire notification |

**Request body:**
```json
{
    "name": "string (required)",
    "email": "email (required)",
    "phone": "string (optional)",
    "message": "string (required)"
}
```

### Swagger / Docs

| URL | Description |
|-----|-------------|
| `/swagger/` | Interactive Swagger UI |
| `/redoc/` | ReDoc documentation |
| `/swagger.json` | Raw JSON schema |
| `/swagger.yaml` | Raw YAML schema |

---

## 13. Troubleshooting

### `No module named 'django_filters'`

```powershell
uv add django-filter
# Note: install name is 'django-filter', import name is 'django_filters'
```

### `OperationalError: no such table: notify_engine_emailmaster`

```powershell
uv run python manage.py makemigrations notify_engine
uv run python manage.py migrate
```

### Emails not sending (silent)

1. Check `EMAIL_BACKEND` in settings — use `console` backend during dev
2. Check logs — is there a `No rule for event=...` info message?
3. Verify the `EmailMaster` rule exists with `is_active=True, to_send=True`
4. Check `EmailLog` for `status=failed` and read `error_message`
5. Make sure `to_value` resolves to a valid email attribute on your instance

### `AttributeError: delay` on `send_email_task`

Celery is not configured. Either:
- Install and configure Celery + Redis
- Or ignore — the engine automatically falls back to synchronous sending

### `ValueError: No PDF renderer registered for template_code='...'`

The `pdf_template_code` you used doesn't exist in `PDF_REGISTRY`. Either:
- Use one of the built-in codes: `enquiry_pdf`, `quotation_pdf`, `invoice_pdf`
- Register a custom renderer in your app's `AppConfig.ready()`

### Swagger UI shows no `notify` endpoints

Check that `notify_engine.urls` is included in `core/urls.py`:
```python
path("api/notify/", include("notify_engine.urls")),
```
And `notify_engine` is in `INSTALLED_APPS`.

### `ImportError: No module named 'reportlab'`

```powershell
uv add reportlab
```
PDF generation is optional. The error only happens at runtime when you try to generate a PDF.
