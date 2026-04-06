"""
notify_engine/services/recipient.py

Resolves TO and CC email addresses for an email rule.

Supports:
    - 'static'   → Use the literal value from the rule (e.g. "admin@co.com").
    - 'dynamic'  → Traverse a dotted attribute path on the model instance.
    - 'customer' → Same as dynamic (resolve from instance).
    - 'user'     → Same as dynamic (resolve from instance).
"""

import logging
from functools import reduce
from typing import Any, Optional

logger = logging.getLogger(__name__)


def resolve_recipient(rule: Any, instance: Any, context: dict) -> str:
    """
    Resolve the primary TO email address based on the rule's to_type.

    Returns an email address string, or empty string if resolution fails.
    """
    if rule.to_type == "static":
        return rule.to_value

    if rule.to_type in ("customer", "user", "dynamic"):
        email = _dotted_get(instance, rule.to_value)
        if not email:
            logger.warning(
                "Could not resolve TO email via path '%s' on %r",
                rule.to_value,
                instance,
            )
            return ""
        return str(email)

    logger.warning("Unknown to_type '%s' on rule %s", rule.to_type, rule)
    return ""


def resolve_cc(rule: Any, instance: Any, context: dict) -> str:
    """
    Resolve CC email address(es) based on the rule's cc_type.

    Returns a comma-separated string of CC addresses.
    """
    if rule.cc_type == "static":
        return rule.cc_value

    if rule.cc_type == "dynamic":
        email = _dotted_get(instance, rule.cc_value)
        if not email:
            logger.warning(
                "Could not resolve CC email via path '%s' on %r",
                rule.cc_value,
                instance,
            )
            return ""
        return str(email)

    return ""


def _dotted_get(obj: Any, path: str) -> Optional[Any]:
    """
    Traverse a dotted attribute path on an object.

    Example: _dotted_get(enquiry, 'customer.email')
             → getattr(getattr(enquiry, 'customer'), 'email')
    """
    if not path:
        return None

    try:
        return reduce(getattr, path.split("."), obj)
    except AttributeError:
        logger.debug("Attribute path '%s' not found on %r", path, obj)
        return None