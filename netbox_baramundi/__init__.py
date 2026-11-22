from django.db.models.signals import post_migrate
from netbox.plugins import PluginConfig


class BaramundiConfig(PluginConfig):
    name = 'netbox_baramundi'
    verbose_name = 'baramundi'
    description = 'baramundi Management Suite integration via bConnect API v2 (endpoint mapping, endpoint panel).'
    version = '0.1.1'
    author = 'Carsten Viell'
    base_url = 'baramundi'
    min_version = '4.7.0'
    default_settings = {
        'endpoint_sync_interval_min': 1440,
        'panel_cache_seconds': 300,
    }

    def ready(self):
        super().ready()
        from . import jobs  # noqa: F401  (registers the system job)
        from .custom_fields import ensure_custom_fields
        post_migrate.connect(ensure_custom_fields, sender=self)


config = BaramundiConfig
