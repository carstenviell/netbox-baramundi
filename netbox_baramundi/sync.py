"""Endpoint mapping: NetBox device/VM name <-> baramundi endpoint (hostName/displayName)."""
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from dcim.models import Device
from virtualization.models import VirtualMachine

from .custom_fields import CF_ENDPOINT, endpoint_id_for

MODELS = (Device, VirtualMachine)
ASSIGNED_STATES = ('matched', 'manual', 'imported')


def _names(value):
    value = (value or '').strip().lower()
    return {value, value.split('.')[0]} - {''}


def match_endpoints(names, endpoints):
    """
    names: {key: netbox name}; endpoints: [{'id', 'hostName', 'displayName'}].
    Exact (case-insensitive) name first, then short name vs. FQDN.
    Returns {key: ('matched', id) | ('ambiguous', [ids]) | ('missing', None)}.
    """
    full, short = defaultdict(set), defaultdict(set)
    for ep in endpoints:
        for field in ('hostName', 'displayName'):
            value = (ep.get(field) or '').strip().lower()
            if value:
                full[value].add(ep['id'])
                short[value.split('.')[0]].add(ep['id'])
    result = {}
    for key, name in names.items():
        name = (name or '').strip().lower()
        ids = full.get(name) or short.get(name.split('.')[0]) or set()
        if len(ids) == 1:
            result[key] = ('matched', next(iter(ids)))
        elif ids:
            result[key] = ('ambiguous', sorted(ids))
        else:
            result[key] = ('missing', None)
    return result


def assigned_q():
    """Objects whose endpoint-ID field holds a value."""
    key = f'custom_field_data__{CF_ENDPOINT}'
    return Q(**{f'{key}__isnull': False}) & ~Q(**{key: None}) & ~Q(**{key: ''})


def holder_of(endpoint_id, exclude=None):
    """The device/VM that already carries this endpoint ID, or None."""
    for model in MODELS:
        qs = model.objects.filter(**{f'custom_field_data__{CF_ENDPOINT}__iexact': endpoint_id})
        if exclude is not None and isinstance(exclude, model):
            qs = qs.exclude(pk=exclude.pk)
        if obj := qs.first():
            return obj
    return None


def set_link(obj, state, message=''):
    from .models import EndpointLink
    field = 'device' if isinstance(obj, Device) else 'virtual_machine'
    EndpointLink.objects.update_or_create(**{field: obj}, defaults={'state': state, 'message': message[:500]})


def sync_endpoint_ids(client, logger, objects=None):
    """Fill empty baramundi_endpoint_id fields. Existing values are never overwritten, only flagged
    as stale when the endpoint is gone. objects=None means all devices/VMs plus the orphan list."""
    endpoints = client.endpoints()
    known = {str(ep['id']).lower() for ep in endpoints}
    if objects is None:
        objects = [o for m in MODELS for o in m.objects.exclude(name__isnull=True).exclude(name='')
                   .select_related('baramundi_link')]
    counts = defaultdict(int)
    empty = []
    for obj in objects:
        endpoint_id = endpoint_id_for(obj)
        if not endpoint_id:
            empty.append(obj)
        elif endpoint_id.lower() not in known:
            counts['stale'] += 1
            set_link(obj, 'stale', _('Endpoint %(id)s no longer exists in baramundi.') % {'id': endpoint_id})
            logger.warning(f'{obj}: baramundi endpoint {endpoint_id} no longer exists')
        else:
            counts['assigned'] += 1
            link = getattr(obj, 'baramundi_link', None)
            if not link or link.state not in ASSIGNED_STATES:
                set_link(obj, 'manual')  # set outside the automatic sync

    # an endpoint already carried by an object is no candidate for another one
    taken = {str(v).lower() for m in MODELS
             for v in m.objects.filter(assigned_q()).values_list(f'custom_field_data__{CF_ENDPOINT}', flat=True)}
    free = [ep for ep in endpoints if str(ep['id']).lower() not in taken]
    for obj, (state, value) in match_endpoints({o: o.name for o in empty}, free).items():
        counts[state] += 1
        if state == 'matched':
            obj.custom_field_data[CF_ENDPOINT] = value
            obj.save()
            set_link(obj, 'matched')
            logger.info(f'{obj}: assigned baramundi endpoint {value}')  # audit trail of automatic assignments
        elif state == 'ambiguous':
            set_link(obj, 'ambiguous', _('Several endpoints match: %(ids)s') % {'ids': ', '.join(value)})
            logger.warning(f'{obj}: several baramundi endpoints match: {", ".join(value)}')
        else:
            set_link(obj, 'missing')
    logger.info(f"Endpoint sync: {counts['matched']} assigned, {counts['ambiguous']} ambiguous, "
                f"{counts['missing']} without baramundi endpoint, {counts['stale']} stale "
                f"(only empty fields were filled).")
    return counts, endpoints


def refresh_orphans(endpoints):
    """Upsert endpoints without a NetBox object into UnmatchedEndpoint. 'ignored' rows keep their status;
    rows whose ID got assigned meanwhile become 'assigned'; vanished 'unresolved' rows are deleted."""
    from .models import UnmatchedEndpoint
    taken = {str(v).lower() for m in MODELS
             for v in m.objects.filter(assigned_q()).values_list(f'custom_field_data__{CF_ENDPOINT}', flat=True)}
    seen = set()
    for ep in endpoints:
        endpoint_id = str(ep.get('id') or '')
        seen.add(endpoint_id.lower())
        if not endpoint_id or endpoint_id.lower() in taken:
            continue
        data = {
            'host_name': (ep.get('hostName') or '')[:255],
            'display_name': (ep.get('displayName') or '')[:255],
            'serial_number': (ep.get('serialNumber') or '')[:255],
            'operating_system': (ep.get('operatingSystem') or '')[:255],
            'endpoint_type': str(ep.get('type') or '')[:50],
            'comment': ep.get('comment') or '',
        }
        row, created = UnmatchedEndpoint.objects.get_or_create(endpoint_id=endpoint_id, defaults=data)
        if not created:
            for field, value in (data.items() if row.status == 'unresolved' else ()):
                setattr(row, field, value)
            row.save()  # refreshes last_seen
    counts = {'assigned': 0, 'deleted': 0}
    for row in UnmatchedEndpoint.objects.filter(status__in=('unresolved', 'ignored')):
        if row.endpoint_id.lower() in taken:
            row.status = 'assigned'
            row.save(update_fields=['status'])
            counts['assigned'] += 1
        elif row.status == 'unresolved' and row.endpoint_id.lower() not in seen:
            row.delete()
            counts['deleted'] += 1
    counts['unresolved'] = UnmatchedEndpoint.objects.filter(status='unresolved').count()
    return counts


def assign_endpoint(obj, endpoint_id, state='manual'):
    """Set the endpoint ID on obj (changelogged via snapshot). Never overwrites another ID."""
    current = endpoint_id_for(obj)
    if current and current.lower() != endpoint_id.lower():
        raise ValidationError(_('%(obj)s already has endpoint ID %(id)s. Clear it first.') % {'obj': obj, 'id': current})
    if holder := holder_of(endpoint_id, exclude=obj):
        raise ValidationError(_('Endpoint ID %(id)s is already set on %(obj)s.') % {'id': endpoint_id, 'obj': holder})
    obj.snapshot()
    obj.custom_field_data[CF_ENDPOINT] = endpoint_id
    obj.full_clean()
    obj.save()
    set_link(obj, state)


def import_endpoint(orphan, kind, values, user, name=None):
    """Create a device (kind='device') or VM from an UnmatchedEndpoint. values: site, role, device_type,
    cluster, status. Raises ValidationError (nothing is saved) on invalid data or missing permission."""
    if holder := holder_of(orphan.endpoint_id):
        raise ValidationError(_('Endpoint ID %(id)s is already set on %(obj)s.') % {'id': orphan.endpoint_id, 'obj': holder})
    comments = '\n\n'.join(x for x in (
        orphan.operating_system and _('Operating system (baramundi): %(os)s') % {'os': orphan.operating_system},
        orphan.comment) if x)
    common = {'name': name or orphan.suggested_name, 'site': values.get('site'), 'role': values.get('role'),
              'status': values.get('status') or 'active', 'comments': comments,
              'custom_field_data': {CF_ENDPOINT: orphan.endpoint_id}}
    if kind == 'device':
        model = Device
        obj = Device(**common, device_type=values.get('device_type'), serial=orphan.serial_number[:50])
    else:
        model = VirtualMachine
        obj = VirtualMachine(**common, cluster=values.get('cluster'))
    with transaction.atomic():
        obj.full_clean()
        obj.save()
        if not model.objects.restrict(user, 'add').filter(pk=obj.pk).exists():  # honours permission constraints
            raise PermissionDeniedError(_('You are not allowed to create this object.'))
        set_link(obj, 'imported')
        orphan.status = 'imported'
        orphan.assigned_device = obj if kind == 'device' else None
        orphan.assigned_vm = obj if kind != 'device' else None
        orphan.save(update_fields=['status', 'assigned_device', 'assigned_vm'])
    return obj


class PermissionDeniedError(ValidationError):
    """Raised inside the transaction so the object is rolled back."""
