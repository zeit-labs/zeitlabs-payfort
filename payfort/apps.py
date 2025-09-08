"""
payfort Django application initialization.
"""

from django.apps import AppConfig


class PayfortConfig(AppConfig):
    """
    Configuration for the payfort Django application.
    """

    name = 'payfort'

    plugin_app = {
        'settings_config': {
            'lms.djangoapp': {
                'production': {
                    'relative_path': 'settings.common_production',
                }
            }
        },
        'url_config': {
            'lms.djangoapp': {
                'namespace': 'payfort',
                'regex': '^payfort/',
                'relative_path': 'urls',
            },
        },
    }
