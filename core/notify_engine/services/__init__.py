"""
notify_engine/services/__init__.py

Public API for the notification engine services layer.
"""

from .engine import trigger_event  # noqa: F401

__all__ = ["trigger_event"]
