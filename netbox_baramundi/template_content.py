from django.core.cache import cache

from netbox.plugins import PluginTemplateExtension, get_plugin_config

from .client import BConnect, BConnectError
from .custom_fields import endpoint_id_for


def cached_endpoint(endpoint_id):
    """Live endpoint data, cached briefly; errors are returned, never raised into the page."""
    key = f'netbox_baramundi:endpoint:{endpoint_id}'
    data = cache.get(key)
    if data is None:
        try:  # short timeout: the device page must not hang when the bMS is unreachable
            data = {'endpoint': BConnect.from_settings(timeout=5).endpoint(endpoint_id)}
            cache.set(key, data, get_plugin_config('netbox_baramundi', 'panel_cache_seconds'))
        except BConnectError as exc:
            data = {'error': str(exc)}
            cache.set(key, data, 60)  # also cache errors briefly - no 5 s wait on every page view
    return data


class EndpointPanel(PluginTemplateExtension):
    models = ['dcim.device', 'virtualization.virtualmachine']

    def right_page(self):
        endpoint_id = endpoint_id_for(self.context['object'])
        data = cached_endpoint(endpoint_id) if endpoint_id else {}
        return self.render('netbox_baramundi/endpoint_panel.html',
                           extra_context={'endpoint_id': endpoint_id, **data})


template_extensions = [EndpointPanel]
