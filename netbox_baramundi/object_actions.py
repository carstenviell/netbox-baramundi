from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.object_actions import ObjectAction


class BulkEndpointSync(ObjectAction):
    """Sync overview: endpoint sync for the selected devices/VMs. multi=True also turns on the row checkboxes."""
    name = 'bulk_endpoint_sync'
    label = _('Sync selected with baramundi')
    multi = True
    permissions_required = {'view'}  # the view itself requires change_endpointlink
    template_name = 'netbox_baramundi/buttons/bulk_apply.html'

    @classmethod
    def get_url(cls, obj):
        kind = 'devices' if obj._meta.model_name == 'device' else 'vms'
        return reverse('plugins:netbox_baramundi:bulk_sync', kwargs={'kind': kind})

    @classmethod
    def get_context(cls, context, obj):
        return {'icon': 'mdi-sync'}


class BulkImportSelected(ObjectAction):
    name = 'bulk_import_endpoints'
    label = _('Import selected')
    multi = True
    permissions_required = {'change'}
    template_name = 'netbox_baramundi/buttons/bulk_apply.html'

    @classmethod
    def get_url(cls, obj):
        return reverse('plugins:netbox_baramundi:orphan_bulk_import')

    @classmethod
    def get_context(cls, context, obj):
        return {'icon': 'mdi-database-import'}
