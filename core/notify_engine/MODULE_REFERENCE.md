# Notify Engine — Module Reference

> **App:** `notify_engine`  
> **Location:** `core/notify_engine/`  
> **Purpose:** A dynamic, rule-based email notification engine. Fires emails automatically when business events occur anywhere in the Django project.

---

## Table of Contents

1. [What This Module Does](#1-what-this-module-does)
2. [Directory Structure](#2-directory-structure)
3. [Data Models](#3-data-models)
4. [Services Layer](#4-services-layer)
5. [API Endpoints](#5-api-endpoints)
6. [Serializers & Validation](#6-serializers--validation)
7. [Filters](#7-filters)
8. [Admin Panel](#8-admin-panel)
9. [PDF Generation](#9-pdf-generation)
10. [How the Engine Works — Flow Diagram](#10-how-the-engine-works--flow-diagram)
11. [How to Trigger a Notification from Any App](#11-how-to-trigger-a-notification-from-any-app)
12. [Template Tag System](#12-template-tag-system)
13. [Known Design Decisions](#13-known-design-decisions)

---

## 1. What This Module Does

`notify_engine` is a **database-driven** notification rules engine. Instead of hardcoding email logic inside views or signals, every team member can configure email rules via:

- The **Django Admin panel**
- The **REST API** (Swagger-documented)

When any part of the application calls `trigger_event('event_name', 'module', instance)`, the engine:

1. Looks up a matching active rule in `EmailMaster`
2. Builds a context dict from the model instance fields
3. Resolves `{{tag}}` placeholders in the subject and body
4. Resolves the TO and CC email addresses
5. Sends the email via Celery (async) or synchronously as a fallback
6. Writes an immutable audit record to `EmailLog`

---

## 2. Directory Structure

```
notify_engine/
│
├── __init__.py
├── apps.py                  # App config — name: 'notify_engine'
├── models.py                # EmailMaster, EmailTemplateTag, EmailLog
├── crm_models.py            # Demo: Enquiry model (CRM use-case)
├── serializers.py           # ModelSerializers for all models
├── views.py                 # DRF ViewSets + EnquiryCreateView
├── urls.py                  # Router-based URL registration
├── filters.py               # DjangoFilterBackend filter classes
├── admin.py                 # Admin config for all 3 models
├── tests.py                 # (placeholder — extend with pytest)
├── tests_api.http           # REST Client test file (30 requests)
│
├── migrations/
│   ├── 0001_initial.py
│   └── 0002_enquiry_alter_emaillog_options_and_more.py
│
└── services/
    ├── __init__.py          # Exports trigger_event
    ├── engine.py            # trigger_event() — main orchestrator
    ├── queue.py             # Celery task + sync fallback
    ├── tag_resolver.py      # {{tag}} replacement logic
    ├── recipient.py         # TO/CC address resolution
    └── pdf_generator.py     # ReportLab + xhtml2pdf PDF renderer
```

---

## 3. Data Models

### 3.1 `EmailMaster` — Notification Rules

The core configuration table. Each row = one email rule for one event.

| Field | Type | Description |
|-------|------|-------------|
| `event_name` | `CharField(100)` | Event key, e.g. `enquiry_created`. Indexed. |
| `module_name` | `CharField(100)` | App that owns the event, e.g. `crm`. |
| `is_active` | `BooleanField` | Disabled rules are ignored by the engine. |
| `to_send` | `BooleanField` | Master toggle — False suppresses all sending. |
| `to_type` | `CharField` choice | `customer`, `user`, `dynamic`, `static` |
| `to_value` | `CharField(255)` | Dotted field path or static email address. |
| `is_cc` | `BooleanField` | Whether to include CC recipients. |
| `cc_type` | `CharField` choice | `static` or `dynamic` |
| `cc_value` | `CharField(500)` | CC field path or comma-separated static emails. |
| `subject_template` | `CharField(500)` | Subject with `{{tag}}` placeholders. |
| `body_template` | `TextField` | HTML body with `{{tag}}` placeholders. |
| `attach_pdf` | `BooleanField` | Whether to attach a generated PDF. |
| `pdf_template_code` | `CharField(100)` | Key into `PDF_REGISTRY`, e.g. `enquiry_pdf`. |
| `created_at` | `DateTimeField` | Auto-set on create. |
| `updated_at` | `DateTimeField` | Auto-updated on every save. |

**Constraints:**
- `unique_together = ("event_name", "module_name")` — one rule per event per module.
- `ordering = ["module_name", "event_name"]`

**`ToType` choices:**

| Value | Meaning |
|-------|---------|
| `static` | Use `to_value` literally as the email address |
| `dynamic` | Traverse `to_value` as a dotted path on the instance |
| `customer` | Same as `dynamic` — semantic label for customer emails |
| `user` | Same as `dynamic` — semantic label for user emails |

---

### 3.2 `EmailTemplateTag` — Tag Metadata

Maps a `{{tag_name}}` to its data source for documentation and tooling purposes.

| Field | Type | Description |
|-------|------|-------------|
| `tag_name` | `CharField(100)` | Unique tag, e.g. `customer_name`. Used in `{{customer_name}}`. |
| `source_table` | `CharField(100)` | Django model label, e.g. `crm.Customer`. |
| `source_field` | `CharField(100)` | Field on the model, e.g. `full_name`. |
| `relation_key` | `CharField(100)` | FK path from the event instance, blank if direct. |
| `module_name` | `CharField(100)` | Module this tag belongs to. |

> **Note:** This model is a documentation/registry table. The actual tag resolution at runtime reads directly from the model instance via `build_context_from_instance()` — it does not query this table. This table is for team reference and future tooling (e.g. a template editor that shows available tags).

---

### 3.3 `EmailLog` — Audit Trail

Immutable record of every email the engine processes, regardless of success or failure.

| Field | Type | Description |
|-------|------|-------------|
| `event_name` | `CharField(100)` | The event that triggered this email. Indexed. |
| `to_email` | `EmailField` | Recipient address. |
| `cc_email` | `TextField` | Comma-separated CC addresses. |
| `subject` | `CharField(500)` | Resolved subject (after tag replacement). |
| `body` | `TextField` | Resolved HTML body (after tag replacement). |
| `attachment_path` | `CharField(500)` | Filesystem path to attached PDF, if any. |
| `status` | `CharField` choice | `pending`, `sent`, `failed`. Indexed. |
| `error_message` | `TextField` | Exception message when `status=failed`. |
| `created_at` | `DateTimeField` | Timestamp. Indexed. |

**Status lifecycle:**
```
pending → sent      (success)
pending → failed    (SMTP error or exception)
```

**Design decision:** Logs can **never be created, edited, or deleted** via the API or Admin. They are written exclusively by `queue.py`.

---

### 3.4 `Enquiry` (in `crm_models.py`) — Demo Model

A simple CRM enquiry model used to demonstrate the engine. Calling `trigger_event('enquiry_created', 'crm', enquiry)` from any view will fire an email if a matching `EmailMaster` rule exists.

| Field | Type |
|-------|------|
| `name` | `CharField(100)` |
| `email` | `EmailField` |
| `phone` | `CharField(20)` (optional) |
| `message` | `TextField` |
| `created_at` | `DateTimeField` |

---

## 4. Services Layer

### 4.1 `engine.py` — `trigger_event()`

The **single public function** other apps call. Everything else is internal.

```python
from notify_engine.services.engine import trigger_event

trigger_event(
    event_name='enquiry_created',   # str — must match EmailMaster.event_name
    module_name='crm',              # str — must match EmailMaster.module_name
    instance=enquiry_obj,           # Django model instance
    extra_context={'key': 'value'}  # optional — merged into template context
)
```

**Internal flow:**
1. Query `EmailMaster` for `(event_name, module_name, is_active=True, to_send=True)`
2. `DoesNotExist` → log info, return silently (no crash)
3. `MultipleObjectsReturned` → log error, use first match
4. Call `build_context_from_instance(instance, extra_context)` → flat dict
5. Call `resolve_recipient(rule, instance, context)` → TO email string
6. If TO email is empty → log warning, return silently
7. Call `resolve_cc(rule, instance, context)` if `rule.is_cc`
8. Call `resolve_tags(rule.subject_template, context)` → resolved subject
9. Call `resolve_tags(rule.body_template, context)` → resolved HTML body
10. Call `_send_email(...)` → tries Celery, falls back to sync

---

### 4.2 `queue.py` — Email Sending

Two paths, same underlying logic via `_build_and_send()`:

| Path | When Used |
|------|-----------|
| `send_email_task.delay()` | Celery is installed and Redis is available |
| `send_email_sync()` | Celery unavailable (dev environment) |

**`_build_and_send()` steps:**
1. Create `EmailLog` with `status=pending`
2. Build `EmailMessage` with HTML content subtype
3. Optionally generate and attach PDF via `generate_pdf(code, context)`
4. Call `msg.send()` → Django's email backend (SMTP)
5. Update log: `status=sent` on success, `status=failed` on exception
6. Always call `log.save()` in `finally` block

**Celery retry config:** `max_retries=3`, `default_retry_delay=60` seconds.

---

### 4.3 `tag_resolver.py`

#### `resolve_tags(template, context) → str`

Replaces `{{tag}}` placeholders in a string using a context dict.

- Pattern: `r"\{\{\s*([\w.]+)\s*\}\}"` — matches `{{name}}`, `{{customer.email}}`, `{{order_number}}`
- Unresolved tags are **left untouched** (not blanked) for easy debugging
- The resolver is pure Python — no database queries

#### `build_context_from_instance(instance, extra=None) → dict`

Auto-generates a flat context dict from any Django model instance:

- Adds all concrete field values: `{"name": "John", "email": "john@x.com", ...}`
- Traverses FK relations **one level deep** with dot notation: `{"customer.email": "...", "customer.name": "..."}`
- Merges `extra` dict last (extra values take precedence)
- Skips callables, reverse relations, `None` values

---

### 4.4 `recipient.py`

#### `resolve_recipient(rule, instance, context) → str`

Resolves the TO email address:

| `to_type` | Behaviour |
|-----------|-----------|
| `static` | Returns `rule.to_value` directly |
| `dynamic` / `customer` / `user` | Calls `_dotted_get(instance, rule.to_value)` |

#### `resolve_cc(rule, instance, context) → str`

Same logic using `cc_type` and `cc_value`. Returns comma-separated string.

#### `_dotted_get(obj, path) → Any`

Traverses "customer.email" → `getattr(getattr(obj, 'customer'), 'email')` using `functools.reduce`.

---

### 4.5 `pdf_generator.py`

A pluggable PDF generation system using a registry pattern.

#### Renderers

| Class | Backend | Use Case |
|-------|---------|----------|
| `ReportLabRenderer` | `reportlab` | Programmatic layouts — tables, grids |
| `HTMLRenderer` | `xhtml2pdf` or `weasyprint` | Render a Django HTML template to PDF |
| `EnquiryPDFRenderer` | ReportLab | Pre-built enquiry summary sheet |
| `QuotationPDFRenderer` | ReportLab | Line-item quotation with grand total |
| `InvoicePDFRenderer` | ReportLab | Tax invoice with subtotal/tax/total rows |

#### Registry

```python
PDF_REGISTRY = {
    'enquiry_pdf':   EnquiryPDFRenderer(),
    'quotation_pdf': QuotationPDFRenderer(),
    'invoice_pdf':   InvoicePDFRenderer(),
}
```

#### Adding a Custom Renderer

```python
# In your app's apps.py → ready()
from notify_engine.services.pdf_generator import register_renderer

class PurchaseOrderRenderer(ReportLabRenderer):
    title = 'Purchase Order'
    filename_prefix = 'po'

register_renderer('purchase_order_pdf', PurchaseOrderRenderer())
```

#### Output Directory

PDFs are saved to `NOTIFY_ENGINE_PDF_DIR` setting (defaults to system temp dir).

```python
# settings.py
NOTIFY_ENGINE_PDF_DIR = BASE_DIR / 'media' / 'email_pdfs'
```

---

## 5. API Endpoints

**Base path:** `http://127.0.0.1:8000/api/notify/`

### 5.1 Email Rules (`/email-rules/`)

Full CRUD — manages `EmailMaster` records.

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/notify/email-rules/` | List all rules |
| `POST` | `/api/notify/email-rules/` | Create a new rule |
| `GET` | `/api/notify/email-rules/{id}/` | Retrieve one rule |
| `PUT` | `/api/notify/email-rules/{id}/` | Full update |
| `PATCH` | `/api/notify/email-rules/{id}/` | Partial update |
| `DELETE` | `/api/notify/email-rules/{id}/` | Delete a rule |
| `POST` | `/api/notify/email-rules/{id}/toggle-active/` | Flip `is_active` on/off |

**Query Parameters (list endpoint):**

| Param | Type | Example | Notes |
|-------|------|---------|-------|
| `event_name` | string | `?event_name=enquiry` | Case-insensitive contains |
| `module_name` | string | `?module_name=crm` | Exact match (case-insensitive) |
| `is_active` | bool | `?is_active=true` | |
| `to_send` | bool | `?to_send=false` | |
| `to_type` | choice | `?to_type=dynamic` | |
| `created_after` | datetime | `?created_after=2026-01-01T00:00:00Z` | |
| `created_before` | datetime | `?created_before=2026-12-31T23:59:59Z` | |
| `search` | string | `?search=enquiry` | Searches `event_name`, `module_name`, `subject_template` |
| `ordering` | string | `?ordering=-created_at` | `-` prefix = descending |
| `page` | int | `?page=2` | Page number (page_size=20) |

---

### 5.2 Template Tags (`/template-tags/`)

Full CRUD — manages `EmailTemplateTag` records.

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/notify/template-tags/` | List all tags |
| `POST` | `/api/notify/template-tags/` | Create a tag mapping |
| `GET` | `/api/notify/template-tags/{id}/` | Retrieve one tag |
| `PUT` | `/api/notify/template-tags/{id}/` | Full update |
| `PATCH` | `/api/notify/template-tags/{id}/` | Partial update |
| `DELETE` | `/api/notify/template-tags/{id}/` | Delete a tag |

**Query Parameters:**

| Param | Type | Notes |
|-------|------|-------|
| `module_name` | string | Exact filter |
| `source_table` | string | Exact filter |
| `search` | string | Searches `tag_name`, `source_table`, `source_field`, `module_name` |
| `ordering` | string | `tag_name`, `module_name` |

---

### 5.3 Email Logs (`/email-logs/`)

Read-only — `POST`, `PUT`, `PATCH`, `DELETE` all return **405 Method Not Allowed**.

| Method | URL | Description |
|--------|-----|-------------|
| `GET` | `/api/notify/email-logs/` | List all log entries |
| `GET` | `/api/notify/email-logs/{id}/` | Retrieve one log entry |

**Query Parameters:**

| Param | Type | Example |
|-------|------|---------|
| `status` | choice | `?status=failed` |
| `event_name` | string | `?event_name=enquiry` (icontains) |
| `to_email` | string | `?to_email=john@` (icontains) |
| `created_after` | datetime | `?created_after=2026-04-01T00:00:00Z` |
| `created_before` | datetime | `?created_before=2026-04-30T23:59:59Z` |
| `search` | string | Searches `event_name`, `to_email`, `subject` |
| `ordering` | string | `created_at`, `status`, `event_name` |

---

### 5.4 Enquiry (`/enquiry/`)

Demo endpoint — creates an `Enquiry` record and triggers `enquiry_created` notification.

| Method | URL | Description |
|--------|-----|-------------|
| `POST` | `/api/notify/enquiry/` | Create enquiry + fire notification |

**Request Body:**
```json
{
    "name": "Pratyanj Kumar",
    "email": "pratyanj@example.com",
    "phone": "+91-9876543210",
    "message": "I need more information about your services."
}
```

---

### 5.5 Swagger / ReDoc

| URL | Description |
|-----|-------------|
| `/swagger/` | Swagger UI — interactive |
| `/redoc/` | ReDoc UI — read-only |
| `/swagger.json` | Raw OpenAPI JSON |
| `/swagger.yaml` | Raw OpenAPI YAML |

---

## 6. Serializers & Validation

### `EmailMasterSerializer`

Cross-field validation rules:

| Condition | Validation Error |
|-----------|-----------------|
| `is_cc=True` + `cc_type` is empty | `{"cc_type": "CC type is required when CC is enabled."}` |
| `is_cc=True` + `cc_value` is empty | `{"cc_value": "CC value is required when CC is enabled."}` |
| `attach_pdf=True` + `pdf_template_code` is empty | `{"pdf_template_code": "PDF template code is required when PDF attachment is enabled."}` |

`read_only_fields`: `id`, `created_at`, `updated_at`

### `EmailTemplateTagSerializer`

No custom validation. `read_only_fields`: `id`

### `EmailLogSerializer`

All fields are read-only. Cannot be used for create/update.

### `EnquirySerializer`

`ModelSerializer` for the `Enquiry` model. `read_only_fields`: `id`, `created_at`

---

## 7. Filters

### `EmailMasterFilter` (in `filters.py`)

| Filter Field | Lookup | Notes |
|-------------|--------|-------|
| `event_name` | `icontains` | Partial match |
| `module_name` | `iexact` | Exact, case-insensitive |
| `is_active` | exact | Boolean |
| `to_send` | exact | Boolean |
| `to_type` | exact choice | Must be a valid `ToType` value |
| `created_after` | `gte` on `created_at` | ISO 8601 datetime |
| `created_before` | `lte` on `created_at` | ISO 8601 datetime |

### `EmailLogFilter` (in `filters.py`)

| Filter Field | Lookup |
|-------------|--------|
| `event_name` | `icontains` |
| `status` | exact choice (`pending`/`sent`/`failed`) |
| `to_email` | `icontains` |
| `created_after` | `gte` on `created_at` |
| `created_before` | `lte` on `created_at` |

---

## 8. Admin Panel

Access at: `http://127.0.0.1:8000/admin/`

### EmailMaster Admin

- **List display:** `event_name`, `module_name`, `is_active`, `to_send`, `to_type`, `is_cc`, `updated_at`
- **Inline edit:** `is_active`, `to_send` (toggle directly in list view)
- **Filters:** `is_active`, `to_send`, `module_name`, `to_type`
- **Search:** `event_name`, `module_name`, `subject_template`
- **Date hierarchy:** drill down by `created_at`
- **Fieldsets:** Event Binding / Recipient / Template / PDF Attachment (collapsible) / Timestamps (collapsible)

### EmailTemplateTag Admin

- **List display:** `tag_name`, `source_table`, `source_field`, `module_name`
- **Filters:** `module_name`
- **Search:** `tag_name`, `source_table`, `module_name`

### EmailLog Admin

- **List display:** `event_name`, `to_email`, `status`, `subject`, `created_at`
- **Filters:** `status`, `event_name`, `created_at`
- **Search:** `to_email`, `subject`, `event_name`
- **Read-only:** All fields (immutable audit log)
- **Add/Change disabled:** `has_add_permission=False`, `has_change_permission=False`

---

## 9. PDF Generation

### Built-in PDF Templates

| `pdf_template_code` | Class | Fields Used |
|--------------------|-------|-------------|
| `enquiry_pdf` | `EnquiryPDFRenderer` | `enquiry_number`, `customer_name`, `customer_email`, `customer_phone`, `company_name`, `created_date`, `status`, `description` |
| `quotation_pdf` | `QuotationPDFRenderer` | `quotation_number`, `quotation_date`, `customer_name`, `customer_email`, `items` (list), `grand_total` |
| `invoice_pdf` | `InvoicePDFRenderer` | `invoice_number`, `invoice_date`, `due_date`, `customer_name`, `customer_address`, `customer_email`, `items` (list), `subtotal`, `tax_amount`, `grand_total`, `payment_terms`, `bank_details` |

### `items` format (for quotation/invoice):
```python
items = [
    {"description": "Product A", "qty": 2, "unit_price": 500, "total": 1000},
    {"description": "Service B", "qty": 1, "unit_price": 2000, "total": 2000},
]
```

---

## 10. How the Engine Works — Flow Diagram

```
Any Django View / Signal / Task
         │
         ▼
trigger_event('enquiry_created', 'crm', enquiry_obj)
         │
         ▼
EmailMaster.objects.get(event_name, module_name, is_active=True, to_send=True)
         │
    ┌────┴────┐
    │ EXISTS? │
    └────┬────┘
   No ───┤ → Log INFO, return silently
         │
        Yes
         │
         ▼
build_context_from_instance(enquiry_obj)
→ {"name": "John", "email": "john@x.com", "message": "...", ...}
         │
         ▼
resolve_recipient(rule, instance, context)
→ "john@x.com"   (or empty → skip)
         │
         ▼
resolve_tags(subject_template, context)
→ "New Enquiry from John"
         │
         ▼
resolve_tags(body_template, context)
→ "<h1>New Enquiry</h1><p>Name: John</p>..."
         │
         ▼
   ┌─────┴──────┐
   │ Celery OK? │
   └─────┬──────┘
  Yes ───┤ → send_email_task.delay(...)
 No  ───→  send_email_sync(...)
         │
         ▼
EmailLog.create(status='pending')
→ EmailMessage.send()
→ EmailLog.update(status='sent' or 'failed')
```

---

## 11. How to Trigger a Notification from Any App

**Step 1:** Create an `EmailMaster` rule via Admin or API.

Example rule:
```json
{
    "event_name": "order_placed",
    "module_name": "sales",
    "is_active": true,
    "to_send": true,
    "to_type": "dynamic",
    "to_value": "customer.email",
    "subject_template": "Your Order #{{order_number}} is Confirmed",
    "body_template": "<p>Hi {{customer.name}},</p><p>Order {{order_number}} placed for {{grand_total}}.</p>"
}
```

**Step 2:** Call `trigger_event` from your view, signal, or task.

```python
# sales/views.py
from notify_engine.services.engine import trigger_event

class OrderCreateView(generics.CreateAPIView):
    def perform_create(self, serializer):
        order = serializer.save()
        trigger_event('order_placed', 'sales', order)
```

**Step 3:** The engine resolves `customer.email` by calling `getattr(getattr(order, 'customer'), 'email')`, replaces all `{{tag}}` placeholders, and sends the email.

---

## 12. Template Tag System

### Supported Tag Formats

| Template | Context Key Required |
|----------|---------------------|
| `{{name}}` | `context["name"]` |
| `{{customer_name}}` | `context["customer_name"]` |
| `{{customer.email}}` | `context["customer.email"]` |
| `{{order.total}}` | `context["order.total"]` |

### Auto-Built Context Keys

When you call `build_context_from_instance(order)` where `order` has a FK to `Customer`:

```python
{
    # Order's own fields
    "id": 42,
    "order_number": "ORD-2026-042",
    "grand_total": 3000,
    "created_at": datetime(2026, 4, 2),

    # FK traversal (one level deep)
    "customer": <Customer object>,     # The FK object itself
    "customer.id": 7,
    "customer.name": "John Doe",
    "customer.email": "john@example.com",
    "customer.phone": "+91-9876543210",
}
```

### Extra Context

Pass additional values that aren't on the model:

```python
trigger_event(
    'order_placed', 'sales', order,
    extra_context={
        'dashboard_url': 'https://app.example.com/orders/42',
        'support_email': 'support@example.com',
    }
)
```

Use in templates: `Click here: <a href="{{dashboard_url}}">View Order</a>`

---

## 13. Known Design Decisions

| Decision | Rationale |
|----------|-----------|
| `EmailTemplateTag` doesn't drive tag resolution at runtime | Performance — no extra DB query per email. Table is for team documentation only. |
| `trigger_event` silently skips if no rule found | Prevents crashes app-wide when rules aren't configured yet. |
| `EmailLog` is immutable via API | Logs are legal/audit records. Mutations would compromise their integrity. |
| Celery-optional design | Engine works in dev without Redis by falling back to synchronous send. |
| PDF context is the same context as the email | Ensures PDFs contain the same data as the email body — no duplication. |
| `unique_together` on `(event_name, module_name)` | Prevents ambiguous rule lookups. One rule per event per module. |
