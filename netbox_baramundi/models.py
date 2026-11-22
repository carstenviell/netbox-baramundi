import re

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel


ENV_PREFIX = 'BARAMUNDI_'


def https_only(value):
    """Basic auth credentials must never travel unencrypted."""
    if value and not value.lower().startswith('https://'):
        raise ValidationError(_('Only https:// URLs are allowed.'))


def env_name(value):
    """Only BARAMUNDI_* variables: otherwise the password field could point to any process secret
    (SECRET_KEY, DB password) and send it to the configured server."""
    if not re.fullmatch(rf'{ENV_PREFIX}[A-Z0-9_]+', value or ''):
        raise ValidationError(_('The variable name must start with %(p)s (A-Z, 0-9, _).') % {'p': ENV_PREFIX})


class BaramundiSettings(NetBoxModel):
    """Singleton (pk=1). The password is never stored - only the name of the environment variable."""
    url = models.URLField(verbose_name=_('server URL'), blank=True, validators=[https_only],
                          help_text=_('e.g. https://bms.example.local (without /bconnect)'))
    username = models.CharField(verbose_name=_('user'), max_length=150, blank=True)
    password_env = models.CharField(verbose_name=_('password environment variable'), max_length=100,
                                    default='BARAMUNDI_PASSWORD', validators=[env_name],
                                    help_text=_('Must start with BARAMUNDI_'))
    verify_tls = models.BooleanField(verbose_name=_('verify TLS'), default=True)
    ca_bundle = models.CharField(verbose_name=_('CA bundle path'), max_length=300, blank=True)
    timeout = models.PositiveIntegerField(verbose_name=_('timeout (s)'), default=30)

    class Meta:
        verbose_name = _('baramundi settings')
        verbose_name_plural = _('baramundi settings')

    def __str__(self):
        return str(_('baramundi settings'))

    def get_absolute_url(self):
        return reverse('plugins:netbox_baramundi:settings')

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]
