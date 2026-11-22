"""Endpoint mapping: NetBox device/VM name <-> baramundi endpoint (hostName/displayName)."""
from collections import defaultdict

from dcim.models import Device
from virtualization.models import VirtualMachine

from .custom_fields import CF_ENDPOINT, endpoint_id_for

MODELS = (Device, VirtualMachine)


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


def sync_endpoint_ids(client, logger):
    """Fill empty baramundi_endpoint_id fields. Existing values are never overwritten."""
    objs = [o for m in MODELS for o in m.objects.exclude(name__isnull=True).exclude(name='')
            if not endpoint_id_for(o)]
    result = match_endpoints({o: o.name for o in objs}, client.endpoints())
    counts = defaultdict(int)
    for obj, (state, value) in result.items():
        counts[state] += 1
        if state == 'matched':
            obj.custom_field_data[CF_ENDPOINT] = value
            obj.save()
            logger.info(f'{obj}: assigned baramundi endpoint {value}')  # audit trail of automatic assignments
        elif state == 'ambiguous':
            logger.warning(f'{obj}: several baramundi endpoints match: {", ".join(value)}')
    logger.info(f"Endpoint sync: {counts['matched']} assigned, {counts['ambiguous']} ambiguous, "
                f"{counts['missing']} without baramundi endpoint (only empty fields were considered).")
    return counts
