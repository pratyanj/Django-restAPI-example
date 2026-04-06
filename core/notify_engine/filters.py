"""
notify_engine/filters.py

DjangoFilterBackend filter classes for the notification engine API.
"""

import django_filters

from .models import EmailLog, EmailMaster


class EmailMasterFilter(django_filters.FilterSet):
    """Filters for EmailMaster list endpoint."""

    event_name = django_filters.CharFilter(lookup_expr="icontains")
    module_name = django_filters.CharFilter(lookup_expr="iexact")
    is_active = django_filters.BooleanFilter()
    to_send = django_filters.BooleanFilter()
    to_type = django_filters.ChoiceFilter(choices=EmailMaster.ToType.choices)
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = EmailMaster
        fields = [
            "event_name",
            "module_name",
            "is_active",
            "to_send",
            "to_type",
            "created_after",
            "created_before",
        ]


class EmailLogFilter(django_filters.FilterSet):
    """Filters for EmailLog list endpoint."""

    event_name = django_filters.CharFilter(lookup_expr="icontains")
    status = django_filters.ChoiceFilter(choices=EmailLog.Status.choices)
    to_email = django_filters.CharFilter(lookup_expr="icontains")
    created_after = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.DateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = EmailLog
        fields = [
            "event_name",
            "status",
            "to_email",
            "created_after",
            "created_before",
        ]
