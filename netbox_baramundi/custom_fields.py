from django.conf import settings
from django.utils import translation
from django.utils.translation import gettext_lazy as _

CF_ENDPOINT = 'baramundi_endpoint_id'
TARGET_MODELS = ('dcim.device', 'virtualization.virtualmachine')


def ensure_custom_fields(sender=None, **kwargs):
    """Create the endpoint-ID field if missing; never modify or delete an existing one."""
    from django.apps import apps
    from core.models import ObjectType
    from extras.models import CustomField

    with translation.override(settings.LANGUAGE_CODE):
        label, description = str(_('baramundi endpoint ID')), str(_('Set by the endpoint sync; can be corrected manually'))
    cf, _created = CustomField.objects.get_or_create(name=CF_ENDPOINT, defaults={
        'type': 'text', 'label': label, 'description': description, 'group_name': 'baramundi', 'weight': 200,
        'validation_regex': r'^[0-9a-fA-F-]{36}$',
    })
    cf.object_types.add(*[ObjectType.objects.get_for_model(apps.get_model(m)) for m in TARGET_MODELS])


def endpoint_id_for(obj):
    return (obj.custom_field_data.get(CF_ENDPOINT) or '').strip() or None
