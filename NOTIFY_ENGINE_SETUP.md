# Dynamic Email Notification System - Setup Guide

## What Was Fixed:

1. ✅ Created missing `serializers.py` with EnquirySerializer
2. ✅ Fixed import path in `queue.py` (models import)
3. ✅ Implemented `pdf_generator.py` for PDF attachments
4. ✅ Registered all models in `admin.py`
5. ✅ Added Celery configuration
6. ✅ Added email SMTP settings
7. ✅ Created Celery app initialization
8. ✅ Created sample Enquiry model
9. ✅ Fixed views.py imports
10. ✅ Added URL routing for notify_engine
11. ✅ Integrated drf-yasg for Swagger API documentation

## Installation Steps:

### 1. Install Required Packages:
```bash
pip install celery redis django-celery-results weasyprint drf-yasg
```

### 2. Install Redis (for Celery broker):
- Windows: Download from https://github.com/microsoftarchive/redis/releases
- Or use: `choco install redis-64`

### 3. Configure Email Settings:
Edit `core/settings.py` and update:
```python
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'  # Use Gmail App Password
DEFAULT_FROM_EMAIL = 'your-email@gmail.com'
```

### 4. Run Migrations:
```bash
python manage.py makemigrations notify_engine
python manage.py migrate
```

### 5. Create Superuser:
```bash
python manage.py createsuperuser
```

### 6. Start Redis Server:
```bash
redis-server
```

### 7. Start Celery Worker (in new terminal):
```bash
celery -A core worker -l info --pool=solo
```

### 8. Start Django Server:
```bash
python manage.py runserver
```

## API Documentation:

Once the server is running, access Swagger UI at:
- **Swagger UI**: http://localhost:8000/swagger/
- **ReDoc**: http://localhost:8000/redoc/
- **JSON Schema**: http://localhost:8000/swagger.json

## Available Endpoints:

### Enquiry API:
- **POST** `/api/notify/enquiry/` - Create new enquiry and trigger email

### Admin Panel:
- **Admin**: http://localhost:8000/admin/

## How to Use:

### 1. Configure Email Rules in Admin:
- Go to: http://localhost:8000/admin/
- Navigate to: Email Masters
- Create a new rule:
  - Event Name: `enquiry_created`
  - Module Name: `crm`
  - To Type: `dynamic`
  - To Value: `email` (field name from Enquiry model)
  - Subject Template: `New Enquiry from {{name}}`
  - Body Template: `<h1>Hello {{name}}</h1><p>Message: {{message}}</p>`

### 2. Test via Swagger:
1. Go to http://localhost:8000/swagger/
2. Find the `/api/notify/enquiry/` endpoint
3. Click "Try it out"
4. Enter sample data:
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "1234567890",
  "message": "I need more information about your services"
}
```
5. Click "Execute"
6. Check Celery worker logs for email processing
7. Check EmailLog in admin for status

### 3. Test via cURL:
```bash
curl -X POST http://localhost:8000/api/notify/enquiry/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "1234567890",
    "message": "Test enquiry"
  }'
```

### 4. Trigger Email from Code:
```python
from notify_engine.services.engine import trigger_event

# After creating an enquiry
trigger_event('enquiry_created', 'crm', enquiry_instance)
```

### 5. Template Tags:
Use `{{field_name}}` in subject/body templates. Available tags are auto-extracted from the model instance.

## System Architecture:

```
User Action → trigger_event() → EmailMaster Rule → 
Resolve Recipients → Resolve Tags → Queue Email (Celery) → 
Send Email + Log → EmailLog
```

## Testing:

1. Create an EmailMaster rule via admin
2. POST to `/api/notify/enquiry/` via Swagger
3. Check Celery worker logs
4. Check EmailLog in admin for status

## Notes:

- For production, use proper email service (SendGrid, AWS SES)
- For PDF generation, create templates in `templates/pdf_templates/`
- Celery tasks are async - emails won't block your API
- All emails are logged in EmailLog model
- Swagger UI provides interactive API testing
- Use ReDoc for cleaner API documentation view
