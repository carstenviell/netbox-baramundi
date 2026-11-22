from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel


class BaramundiSettings(NetBoxModel):
    """Singleton (pk=1). The password is never stored - only the name of the environment variable."""
    url = models.URLField(verbose_name=_('server URL'), blank=True,
                          help_text=_('e.g. https://bms.example.local (without /bconnect)'))
    username = models.CharField(verbose_name=_('user'), max_length=150, blank=True)
    password_env = models.CharField(verbose_name=_('password environment variable'), max_length=100,
                                    default='BARAMUNDI_PASSWORD')
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
