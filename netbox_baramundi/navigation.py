from django.utils.translation import gettext_lazy as _

from netbox.plugins.navigation import PluginMenuItem

menu_items = (
    PluginMenuItem(link='plugins:netbox_baramundi:settings', link_text=_('baramundi settings'),
                   permissions=['netbox_baramundi.change_baramundisettings']),
)
