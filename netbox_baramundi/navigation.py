from django.utils.translation import gettext_lazy as _

from netbox.plugins.navigation import PluginMenuItem

menu_items = (
    PluginMenuItem(link='plugins:netbox_baramundi:sync_devices', link_text=_('Sync overview: devices'),
                   permissions=['dcim.view_device']),
    PluginMenuItem(link='plugins:netbox_baramundi:sync_vms', link_text=_('Sync overview: virtual machines'),
                   permissions=['virtualization.view_virtualmachine']),
    PluginMenuItem(link='plugins:netbox_baramundi:orphan_list', link_text=_('baramundi orphans'),
                   permissions=['netbox_baramundi.view_unmatchedendpoint']),
    PluginMenuItem(link='plugins:netbox_baramundi:settings', link_text=_('baramundi settings'),
                   permissions=['netbox_baramundi.change_baramundisettings']),
)
