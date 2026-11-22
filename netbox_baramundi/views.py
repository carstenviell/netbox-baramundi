from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View

from dcim.models import Device
from netbox.plugins import get_plugin_config
from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from virtualization.models import VirtualMachine

from .client import BConnect, BConnectError
from .custom_fields import endpoint_id_for
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


def cached_endpoint(endpoint_id):
    """Live endpoint data, cached briefly; errors are returned, never raised into the page."""
    key = f'netbox_baramundi:endpoint:{endpoint_id}'
    data = cache.get(key)
    if data is None:
        try:  # short timeout: the tab must not hang when the bMS is unreachable
            data = {'endpoint': BConnect.from_settings(timeout=5).endpoint(endpoint_id)}
            cache.set(key, data, get_plugin_config('netbox_baramundi', 'panel_cache_seconds'))
        except BConnectError as exc:
            data = {'error': str(exc)}
            cache.set(key, data, 60)  # also cache errors briefly - no 5 s wait on every view
    return data


def _register_tab(model):
    """"baramundi" tab on device/VM pages; bConnect is only queried when the tab is opened."""
    @register_model_view(model, 'baramundi', path='baramundi')
    class EndpointTabView(generic.ObjectView):
        queryset = model.objects.all()
        template_name = 'netbox_baramundi/endpoint_tab.html'
        tab = ViewTab(label='baramundi', visible=lambda obj: bool(endpoint_id_for(obj)), weight=2600)

        def get_extra_context(self, request, instance):
            endpoint_id = endpoint_id_for(instance)
            return {'endpoint_id': endpoint_id, **(cached_endpoint(endpoint_id) if endpoint_id else {})}
    EndpointTabView.__name__ = EndpointTabView.__qualname__ = f'{model.__name__}BaramundiView'


for _model in (Device, VirtualMachine):
    _register_tab(_model)
