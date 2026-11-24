from django import forms
from django.utils.translation import gettext_lazy as _

from dcim.choices import DeviceStatusChoices
from dcim.forms import DeviceFilterForm
from dcim.models import Device, DeviceRole, DeviceType, Site
from utilities.forms.fields import DynamicModelChoiceField
from utilities.forms.rendering import FieldSet
from virtualization.forms import VirtualMachineFilterForm
from virtualization.models import Cluster, VirtualMachine

from .filtersets import STATUS_CHOICES
from .models import BaramundiSettings

KIND_CHOICES = (('device', _('Device')), ('vm', _('Virtual machine')))


class BaramundiSettingsForm(forms.ModelForm):
    class Meta:
        model = BaramundiSettings
        fields = ('url', 'username', 'password_env', 'verify_tls', 'ca_bundle', 'timeout')


# -- sync overview filters ----------------------------------------------------
_status_field = forms.ChoiceField(label=_('baramundi status'), required=False,
                                  choices=(('', '---------'),) + STATUS_CHOICES)


class DeviceEndpointFilterForm(DeviceFilterForm):
    baramundi_status = _status_field
    fieldsets = (FieldSet('baramundi_status', name='baramundi'),) + DeviceFilterForm.fieldsets


class VMEndpointFilterForm(VirtualMachineFilterForm):
    baramundi_status = _status_field
    fieldsets = (FieldSet('baramundi_status', name='baramundi'),) + VirtualMachineFilterForm.fieldsets


# -- orphans -------------------------------------------------------------------
class OrphanAssignForm(forms.Form):
    kind = forms.ChoiceField(label=_('Object type'), choices=KIND_CHOICES)
    device = DynamicModelChoiceField(label=_('Device'), queryset=Device.objects.all(), required=False, selector=True)
    virtual_machine = DynamicModelChoiceField(label=_('Virtual machine'), queryset=VirtualMachine.objects.all(),
                                              required=False, selector=True)

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # only objects the user may change (permission constraints included)
        self.fields['device'].queryset = Device.objects.restrict(user, 'change')
        self.fields['virtual_machine'].queryset = VirtualMachine.objects.restrict(user, 'change')

    def clean(self):
        data = super().clean()
        field = 'device' if data.get('kind') == 'device' else 'virtual_machine'
        if not data.get(field):
            self.add_error(field, _('This field is required.'))
        data['target'] = data.get(field)
        return data


class ImportDefaultsForm(forms.Form):
    """Values the endpoint cannot provide. Used for the single and the bulk import."""
    kind = forms.ChoiceField(label=_('Create as'), choices=KIND_CHOICES)
    site = DynamicModelChoiceField(label=_('Site'), queryset=Site.objects.all(), required=False)
    role = DynamicModelChoiceField(label=_('Role'), queryset=DeviceRole.objects.all(), required=False)
    device_type = DynamicModelChoiceField(label=_('Device type'), queryset=DeviceType.objects.all(), required=False,
                                          help_text=_('Devices only'))
    cluster = DynamicModelChoiceField(label=_('Cluster'), queryset=Cluster.objects.all(), required=False,
                                      help_text=_('Virtual machines only (site or cluster required)'))
    status = forms.ChoiceField(label=_('Status'), choices=DeviceStatusChoices, initial='active')

    def clean(self):
        data = super().clean()
        if data.get('kind') == 'device':
            for field in ('site', 'role', 'device_type'):
                if not data.get(field):
                    self.add_error(field, _('Required for devices.'))
        elif not data.get('site') and not data.get('cluster'):
            self.add_error('cluster', _('A virtual machine needs a site or a cluster.'))
        return data


class OrphanImportForm(ImportDefaultsForm):
    name = forms.CharField(label=_('Name'), max_length=64)
    field_order = ('name', 'kind')
