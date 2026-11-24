from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from core.choices import JobStatusChoices
from core.models import Job
from dcim.models import Device
from extras.dashboard.utils import register_widget
from extras.dashboard.widgets import DashboardWidget
from virtualization.models import VirtualMachine

from .jobs import EndpointSyncJob
from .models import UnmatchedEndpoint
from .sync import assigned_q


@register_widget
class BaramundiStatusWidget(DashboardWidget):
    default_title = _('baramundi')
    description = _('Last endpoint sync, devices/VMs with endpoint ID and open baramundi orphans.')
    width = 4
    height = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = str(self.title)  # a lazy proxy breaks "Add widget" for all widgets (see cod-connector)

    def render(self, request):
        user = request.user
        rows = []
        for model, url in ((Device, 'plugins:netbox_baramundi:sync_devices'),
                           (VirtualMachine, 'plugins:netbox_baramundi:sync_vms')):
            qs = model.objects.restrict(user, 'view')
            total, assigned = qs.count(), qs.filter(assigned_q()).count()
            rows.append({'label': model._meta.verbose_name_plural, 'url': url, 'total': total, 'assigned': assigned,
                         'percent': round(100 * assigned / total) if total else 0})
        last_job = None
        if user.has_perm('core.view_job'):  # the system job is always also "scheduled" - show the last finished run
            last_job = (Job.objects.filter(name=EndpointSyncJob.Meta.name,
                                           status__in=JobStatusChoices.TERMINAL_STATE_CHOICES)
                        .order_by('-completed').first())
        orphans = None
        if user.has_perm('netbox_baramundi.view_unmatchedendpoint'):
            orphans = UnmatchedEndpoint.objects.restrict(user, 'view').filter(status='unresolved').count()
        return render_to_string('netbox_baramundi/dashboard_widget.html', {
            'rows': rows, 'last_job': last_job, 'can_view_jobs': user.has_perm('core.view_job'), 'orphans': orphans,
        })
