import re

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from netbox.models import NetBoxModel
from utilities.querysets import RestrictedQuerySet


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


class EndpointLink(models.Model):
    """Result of the last endpoint sync for one device or VM. The assignment itself stays in the
    custom field baramundi_endpoint_id (public interface) - this only explains the state."""
    STATE_CHOICES = [
        ('matched', _('Matched by name')),
        ('manual', _('Assigned manually')),
        ('imported', _('Imported from baramundi')),
        ('missing', _('Not found')),
        ('ambiguous', _('Ambiguous')),
        ('stale', _('Endpoint no longer exists')),
    ]

    device = models.OneToOneField(to='dcim.Device', null=True, blank=True, on_delete=models.CASCADE,
                                  related_name='baramundi_link')
    virtual_machine = models.OneToOneField(to='virtualization.VirtualMachine', null=True, blank=True,
                                           on_delete=models.CASCADE, related_name='baramundi_link')
    state = models.CharField(verbose_name=_('state'), max_length=10, choices=STATE_CHOICES)
    message = models.CharField(verbose_name=_('message'), max_length=500, blank=True)
    last_checked = models.DateTimeField(verbose_name=_('last checked'), auto_now=True)

    objects = RestrictedQuerySet.as_manager()

    class Meta:
        verbose_name = _('baramundi endpoint link')
        verbose_name_plural = _('baramundi endpoint links')
        constraints = [models.CheckConstraint(
            condition=models.Q(device__isnull=False, virtual_machine__isnull=True)
            | models.Q(device__isnull=True, virtual_machine__isnull=False),
            name='netbox_baramundi_endpointlink_one_object')]

    def __str__(self):
        return f'{self.device or self.virtual_machine}: {self.state}'


class UnmatchedEndpoint(models.Model):
    """A baramundi endpoint whose ID is not set on any device or VM."""
    STATUS_CHOICES = [
        ('unresolved', _('Unresolved')),
        ('ignored', _('Ignored')),
        ('assigned', _('Assigned')),
        ('imported', _('Imported')),
    ]

    endpoint_id = models.CharField(verbose_name=_('endpoint ID'), max_length=36, unique=True)
    host_name = models.CharField(verbose_name=_('host name'), max_length=255, blank=True)
    display_name = models.CharField(verbose_name=_('display name'), max_length=255, blank=True)
    serial_number = models.CharField(verbose_name=_('serial number'), max_length=255, blank=True)
    operating_system = models.CharField(verbose_name=_('operating system'), max_length=255, blank=True)
    endpoint_type = models.CharField(verbose_name=_('endpoint type'), max_length=50, blank=True)
    comment = models.TextField(verbose_name=_('comment'), blank=True)
    status = models.CharField(verbose_name=_('status'), max_length=10, choices=STATUS_CHOICES, default='unresolved')
    assigned_device = models.ForeignKey(to='dcim.Device', null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name='+')
    assigned_vm = models.ForeignKey(to='virtualization.VirtualMachine', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    ignore_note = models.CharField(verbose_name=_('note'), max_length=255, blank=True)
    last_seen = models.DateTimeField(verbose_name=_('last seen'), auto_now=True)

    objects = RestrictedQuerySet.as_manager()

    class Meta:
        verbose_name = _('unmatched baramundi endpoint')
        verbose_name_plural = _('unmatched baramundi endpoints')
        ordering = ('display_name', 'host_name')

    def __str__(self):
        return self.display_name or self.host_name or self.endpoint_id

    @property
    def suggested_name(self):
        return self.display_name or (self.host_name or '').split('.')[0] or self.endpoint_id
