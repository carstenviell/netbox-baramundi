from django.core.cache import cache

from netbox.plugins import PluginTemplateExtension, get_plugin_config

from .client import BConnect, BConnectError
from .custom_fields import endpoint_id_for


def cached_endpoint(endpoint_id):
    """Live endpoint data, cached briefly; errors are returned, never raised into the page."""
    key = f'netbox_baramundi:endpoint:{endpoint_id}'
    data = cache.get(key)
    if data is None:
        try:
            data = {'endpoint': BConnect.from_settings().endpoint(endpoint_id)}
        except BConnectError as exc:
            return {'error': str(exc)}
        cache.set(key, data, get_plugin_config('netbox_baramundi', 'panel_cache_seconds'))
    return data


class EndpointPanel(PluginTemplateExtension):
    models = ['dcim.device', 'virtualization.virtualmachine']

    def right_page(self):
        endpoint_id = endpoint_id_for(self.context['object'])
        data = cached_endpoint(endpoint_id) if endpoint_id else {}
        return self.render('netbox_baramundi/endpoint_panel.html',
                           extra_context={'endpoint_id': endpoint_id, **data})


template_extensions = [EndpointPanel]
