"""
notify_engine/services/tag_resolver.py

Resolves {{tag}} placeholders in email subject/body templates.

Supports:
    - Simple tags:  {{name}}, {{email}}
    - Dotted tags:  {{customer.email}}, {{order.total}}
    - Underscore:   {{customer_name}}

The build_context_from_instance() function auto-generates a flat context
dict from any Django model instance, traversing FK relations one level deep.
"""

import re
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Matches {{tag_name}} and {{dotted.path}} — supports word chars and dots
_TAG_PATTERN = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")


def resolve_tags(template: str, context: dict[str, Any]) -> str:
    """
    Replace all {{tag}} placeholders in `template` with values from `context`.

    Unresolved tags are left as-is (e.g. {{unknown_tag}} stays in output)
    so they can be spotted during debugging.
    """

    def _replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        value = context.get(key)

        if value is None:
            logger.debug("Unresolved template tag: {{%s}}", key)
            return match.group(0)  # Leave the tag intact

        return str(value)

    return _TAG_PATTERN.sub(_replacer, template)


def build_context_from_instance(
    instance: Any,
    extra: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Auto-build a flat context dict from a Django model instance.

    Iterates over all concrete fields on the instance and adds them
    to the context. Foreign-key related objects are traversed one level
    deep, prefixed with the relation name (e.g. ``customer.email``).

    Args:
        instance: A Django model instance.
        extra:    Additional key-value pairs merged into the context
                  (these take precedence over auto-generated values).

    Returns:
        Flat dict suitable for passing to resolve_tags().
    """
    context: dict[str, Any] = {}

    if instance is None:
        logger.warning("build_context_from_instance called with None instance.")
        if extra:
            context.update(extra)
        return context

    for field in instance._meta.get_fields():
        # Skip reverse relations (ManyToOneRel, ManyToManyRel, etc.)
        if not hasattr(field, "attname") and not hasattr(field, "name"):
            continue

        field_name = getattr(field, "name", None)
        if field_name is None:
            continue

        try:
            value = getattr(instance, field_name, None)

            # Skip callables (managers, methods)
            if callable(value) and not isinstance(value, str):
                continue

            if value is not None:
                context[field_name] = value

                # Traverse FK one level deep
                if hasattr(field, "related_model") and field.related_model is not None:
                    related_obj = value
                    for related_field in related_obj._meta.get_fields():
                        related_field_name = getattr(related_field, "name", None)
                        if related_field_name is None:
                            continue
                        try:
                            related_value = getattr(related_obj, related_field_name, None)
                            if related_value is not None and not callable(related_value):
                                dotted_key = f"{field_name}.{related_field_name}"
                                context[dotted_key] = related_value
                        except Exception:
                            pass

        except Exception:
            logger.debug("Could not read field '%s' from %r", field_name, instance)

    if extra:
        context.update(extra)

    return context