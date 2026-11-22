from django.contrib import messages
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View

from .client import BConnect, BConnectError
from .forms import BaramundiSettingsForm
from .jobs import EndpointSyncJob
from .models import BaramundiSettings

PERM = 'netbox_baramundi.change_baramundisettings'


class SuperuserMixin(PermissionRequiredMixin):
    """Settings decide where the service-account password is sent - superusers only."""
    permission_required = PERM

    def has_permission(self):
        return self.request.user.is_superuser and super().has_permission()


class SettingsView(SuperuserMixin, View):
    template_name = 'netbox_baramundi/settings.html'

    def get(self, request):
        return render(request, self.template_name, {'form': BaramundiSettingsForm(instance=BaramundiSettings.load())})

    def post(self, request):
        settings = BaramundiSettings.load()
        settings.snapshot()
        form = BaramundiSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, _('Settings saved.'))
            return redirect('plugins:netbox_baramundi:settings')
        return render(request, self.template_name, {'form': form})


class TestConnectionView(SuperuserMixin, View):

    def post(self, request):
        try:
            server = BConnect.from_settings().management_server()
        except BConnectError as exc:
            messages.error(request, _('Connection failed: %(err)s') % {'err': exc})
        else:
            messages.success(request, _('Connected to %(name)s, version %(version)s.') % {
                'name': server.get('name', '?'), 'version': server.get('version', '?')})
        return redirect('plugins:netbox_baramundi:settings')


class EndpointSyncView(PermissionRequiredMixin, View):
    permission_required = PERM

    def post(self, request):
        job = EndpointSyncJob.enqueue(user=request.user)
        messages.success(request, _('Endpoint sync enqueued.'))
        return redirect(job.get_absolute_url())
