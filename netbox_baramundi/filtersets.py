import django_filters
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from dcim.filtersets import DeviceFilterSet
from virtualization.filtersets import VirtualMachineFilterSet

from .models import UnmatchedEndpoint
from .sync import assigned_q

STATUS_CHOICES = (
    ('assigned', _('Assigned')),
    ('stale', _('Stale')),
    ('ambiguous', _('Ambiguous')),
    ('missing', _('Not found')),
    ('never_checked', _('Never checked')),
)


def filter_baramundi_status(queryset, name, value):
    if value == 'assigned':
        return queryset.filter(assigned_q()).exclude(baramundi_link__state='stale')
    if value == 'stale':
        return queryset.filter(baramundi_link__state='stale')
    unassigned = queryset.exclude(assigned_q())
    if value == 'never_checked':
        return unassigned.filter(baramundi_link__isnull=True)
    return unassigned.filter(baramundi_link__state=value)


class DeviceEndpointFilterSet(DeviceFilterSet):
    baramundi_status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, label=_('baramundi status'),
                                                   method=filter_baramundi_status)


class VMEndpointFilterSet(VirtualMachineFilterSet):
    baramundi_status = django_filters.ChoiceFilter(choices=STATUS_CHOICES, label=_('baramundi status'),
                                                   method=filter_baramundi_status)


class OrphanFilterSet(django_filters.FilterSet):
    q = django_filters.CharFilter(method='search', label=_('Search'))
    status = django_filters.ChoiceFilter(choices=UnmatchedEndpoint.STATUS_CHOICES)

    class Meta:
        model = UnmatchedEndpoint
        fields = ('status',)

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(Q(display_name__icontains=value) | Q(host_name__icontains=value)
                               | Q(endpoint_id__icontains=value) | Q(serial_number__icontains=value))
