from netbox.plugins import PluginTemplateExtension

from .custom_fields import endpoint_id_for


class EndpointPanel(PluginTemplateExtension):
    """Compact card without a bConnect call; the live data lives in the "baramundi" tab (views.py)."""
    models = ['dcim.device', 'virtualization.virtualmachine']

    def left_page(self):
        return self.render('netbox_baramundi/endpoint_card.html',
                           extra_context={'endpoint_id': endpoint_id_for(self.context['object'])})


template_extensions = [EndpointPanel]
