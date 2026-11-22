from django import forms

from .models import BaramundiSettings


class BaramundiSettingsForm(forms.ModelForm):
    class Meta:
        model = BaramundiSettings
        fields = ('url', 'username', 'password_env', 'verify_tls', 'ca_bundle', 'timeout')
