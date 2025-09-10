"""Common Settings"""
from typing import Any


def plugin_settings(settings: Any) -> None:
    """
    plugin settings
    """
    settings.PAYFORT_SETTINGS = getattr(
        settings,
        'PAYFORT_SETTINGS',
        {},
    )
