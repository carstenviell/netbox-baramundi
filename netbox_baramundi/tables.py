import django_tables2 as tables
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from dcim.tables import DeviceTable
from netbox.tables import NetBoxTable, columns
from virtualization.tables import VirtualMachineTable

from .custom_fields import endpoint_id_for
from .models import UnmatchedEndpoint

BADGE = '<span class="badge text-bg-{}" title="{}">{}</span>'


class EndpointColumnsMixin(tables.Table):
    baramundi_endpoint = tables.Column(empty_values=(), orderable=False, verbose_name=_('baramundi endpoint ID'))
    baramundi_status = tables.Column(empty_values=(), orderable=False, verbose_name=_('baramundi status'))
    baramundi_checked = tables.DateTimeColumn(accessor='baramundi_link__last_checked',
                                              verbose_name=_('baramundi last checked'))

    def render_baramundi_endpoint(self, record):
        return endpoint_id_for(record) or '—'

    def render_baramundi_status(self, record):
        link = getattr(record, 'baramundi_link', None)
        if link and link.state == 'stale':
            return format_html(BADGE, 'warning', link.message, _('Stale'))
        if endpoint_id_for(record):
            return format_html(BADGE, 'success', link.get_state_display() if link else '', _('Assigned'))
        if not link:
            return format_html(BADGE, 'secondary', '', _('Never checked'))
        color = 'danger' if link.state == 'ambiguous' else 'secondary'
        return format_html(BADGE, color, link.message, link.get_state_display())


EXTRA = ('baramundi_endpoint', 'baramundi_status', 'baramundi_checked')


class DeviceEndpointTable(EndpointColumnsMixin, DeviceTable):
    class Meta(DeviceTable.Meta):
        fields = DeviceTable.Meta.fields + EXTRA
        default_columns = ('name', 'status', 'site', 'role', 'device_type') + EXTRA


class VMEndpointTable(EndpointColumnsMixin, VirtualMachineTable):
    class Meta(VirtualMachineTable.Meta):
        fields = VirtualMachineTable.Meta.fields + EXTRA
        default_columns = ('name', 'status', 'site', 'cluster', 'role') + EXTRA


class OrphanTable(NetBoxTable):
    # no registered edit/delete views - an empty tuple skips the URL reversal ActionsColumn attempts
    actions = columns.ActionsColumn(actions=())
    display_name = tables.Column(verbose_name=_('display name'))
    status = columns.ChoiceFieldColumn()
    row_actions = tables.TemplateColumn(template_name='netbox_baramundi/inc/orphan_row_actions.html',
                                        orderable=False, verbose_name='')

    class Meta(NetBoxTable.Meta):
        model = UnmatchedEndpoint
        fields = ('pk', 'display_name', 'host_name', 'endpoint_id', 'endpoint_type', 'operating_system',
                  'serial_number', 'status', 'ignore_note', 'last_seen', 'row_actions')
        default_columns = ('display_name', 'host_name', 'endpoint_type', 'operating_system', 'serial_number',
                           'status', 'last_seen', 'row_actions')
