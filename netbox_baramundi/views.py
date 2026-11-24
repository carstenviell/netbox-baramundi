from django.contrib import messages
from django.core.cache import cache
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views import View

from dcim.models import Device
from netbox.plugins import get_plugin_config
from netbox.views import generic
from utilities.views import ViewTab, register_model_view
from virtualization.models import VirtualMachine

from .client import BConnect, BConnectError
from .custom_fields import endpoint_id_for
from .filtersets import DeviceEndpointFilterSet, OrphanFilterSet, VMEndpointFilterSet
from .forms import (BaramundiSettingsForm, DeviceEndpointFilterForm, ImportDefaultsForm, OrphanAssignForm,
                    OrphanImportForm, VMEndpointFilterForm)
from .jobs import EndpointSyncJob
from .models import BaramundiSettings, UnmatchedEndpoint
from .object_actions import BulkEndpointSync, BulkImportSelected
from .sync import assign_endpoint, import_endpoint
from .tables import DeviceEndpointTable, OrphanTable, VMEndpointTable

PERM = 'netbox_baramundi.change_baramundisettings'
LINK_PERM = 'netbox_baramundi.change_endpointlink'
ORPHAN_PERM = 'netbox_baramundi.change_unmatchedendpoint'


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


# -- sync overview ------------------------------------------------------------------
class DeviceSyncOverviewView(generic.ObjectListView):
    queryset = Device.objects.select_related('baramundi_link', 'site', 'role', 'device_type__manufacturer')
    table = DeviceEndpointTable
    filterset = DeviceEndpointFilterSet
    filterset_form = DeviceEndpointFilterForm
    actions = (BulkEndpointSync,)


class VMSyncOverviewView(generic.ObjectListView):
    queryset = VirtualMachine.objects.select_related('baramundi_link', 'site', 'cluster', 'role')
    table = VMEndpointTable
    filterset = VMEndpointFilterSet
    filterset_form = VMEndpointFilterForm
    actions = (BulkEndpointSync,)


def _return_url(request, default):
    url = request.POST.get('return_url') or request.GET.get('return_url')
    if url and url_has_allowed_host_and_scheme(url, allowed_hosts={request.get_host()}):
        return url
    return reverse(default)


class BulkEndpointSyncView(PermissionRequiredMixin, View):
    """Sync only the selected (or all filtered) devices/VMs; the orphan list is refreshed by the full run."""
    permission_required = LINK_PERM

    def post(self, request, kind):
        model, filterset = (Device, DeviceEndpointFilterSet) if kind == 'devices' else (VirtualMachine, VMEndpointFilterSet)
        queryset = model.objects.restrict(request.user, 'view')
        if request.POST.get('_all'):
            ids = list(filterset(request.GET, queryset=queryset).qs.values_list('pk', flat=True))
        else:
            ids = list(queryset.filter(pk__in=request.POST.getlist('pk')).values_list('pk', flat=True))
        EndpointSyncJob.enqueue(user=request.user, **{'device_ids' if kind == 'devices' else 'vm_ids': ids})
        messages.success(request, _('Endpoint sync for %(count)d object(s) enqueued.') % {'count': len(ids)})
        return redirect(_return_url(request, f'plugins:netbox_baramundi:sync_{kind}'))


# -- orphans -----------------------------------------------------------------------
class OrphanListView(generic.ObjectListView):
    # no add/import/export/edit/delete views exist - per-row actions are plain links (tables.OrphanTable)
    queryset = UnmatchedEndpoint.objects.all()
    table = OrphanTable
    filterset = OrphanFilterSet
    actions = (BulkImportSelected,)
    template_name = 'netbox_baramundi/orphan_list.html'

    def get(self, request, *args, **kwargs):
        if 'status' not in request.GET:  # default view: open items only
            request.GET = request.GET.copy()
            request.GET['status'] = 'unresolved'
        return super().get(request, *args, **kwargs)


class OrphanMixin(PermissionRequiredMixin):
    permission_required = ORPHAN_PERM

    def orphan(self, request, pk):
        return get_object_or_404(UnmatchedEndpoint.objects.restrict(request.user, 'change'), pk=pk)


class RefreshOrphansView(OrphanMixin, View):
    def post(self, request):
        job = EndpointSyncJob.enqueue(user=request.user)
        messages.success(request, _('Endpoint sync enqueued; the list is refreshed when it has finished.'))
        return redirect(job.get_absolute_url())


class AssignOrphanView(OrphanMixin, View):
    template_name = 'netbox_baramundi/orphan_assign.html'

    def get(self, request, pk):
        return render(request, self.template_name,
                      {'orphan': self.orphan(request, pk), 'form': OrphanAssignForm(user=request.user)})

    def post(self, request, pk):
        orphan = self.orphan(request, pk)
        form = OrphanAssignForm(request.POST, user=request.user)
        if form.is_valid():
            target = form.cleaned_data['target']
            try:
                assign_endpoint(target, orphan.endpoint_id)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                orphan.status = 'assigned'
                orphan.assigned_device = target if isinstance(target, Device) else None
                orphan.assigned_vm = target if isinstance(target, VirtualMachine) else None
                orphan.save(update_fields=['status', 'assigned_device', 'assigned_vm'])
                messages.success(request, _('Endpoint assigned to %(obj)s.') % {'obj': target})
                return redirect('plugins:netbox_baramundi:orphan_list')
        return render(request, self.template_name, {'orphan': orphan, 'form': form})


class ImportOrphanView(OrphanMixin, View):
    template_name = 'netbox_baramundi/orphan_import.html'

    def get(self, request, pk):
        orphan = self.orphan(request, pk)
        form = OrphanImportForm(initial={'name': orphan.suggested_name, 'status': 'active'})
        return render(request, self.template_name, {'orphan': orphan, 'form': form})

    def post(self, request, pk):
        orphan = self.orphan(request, pk)
        form = OrphanImportForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            try:
                obj = import_endpoint(orphan, data['kind'], data, request.user, name=data['name'])
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, _('%(obj)s created from baramundi.') % {'obj': obj})
                return redirect(obj.get_absolute_url())
        return render(request, self.template_name, {'orphan': orphan, 'form': form})


class BulkImportOrphansView(OrphanMixin, View):
    """Step 1 (from the list): show the defaults form for the selection. Step 2 (_import): create the objects;
    one transaction per endpoint, failures are skipped and reported."""
    template_name = 'netbox_baramundi/orphan_bulk_import.html'

    def post(self, request):
        orphans = UnmatchedEndpoint.objects.restrict(request.user, 'change').filter(
            pk__in=request.POST.getlist('pk'), status__in=('unresolved', 'ignored'))
        if '_import' not in request.POST:
            form = ImportDefaultsForm(initial={'status': 'active'})
        else:
            form = ImportDefaultsForm(request.POST)
            if form.is_valid():
                data, created, failed = form.cleaned_data, 0, []
                for orphan in orphans:
                    try:
                        import_endpoint(orphan, data['kind'], data, request.user)
                        created += 1
                    except ValidationError as exc:
                        failed.append(f'{orphan}: {" ".join(exc.messages)}')
                if created:
                    messages.success(request, _('%(count)d object(s) created from baramundi.') % {'count': created})
                for line in failed:
                    messages.error(request, line)
                return redirect('plugins:netbox_baramundi:orphan_list')
        return render(request, self.template_name, {'orphans': orphans, 'form': form})


class IgnoreOrphanView(OrphanMixin, View):
    template_name = 'netbox_baramundi/orphan_ignore.html'

    def get(self, request, pk):
        return render(request, self.template_name, {'orphan': self.orphan(request, pk)})

    def post(self, request, pk):
        orphan = self.orphan(request, pk)
        orphan.status = 'ignored'
        orphan.ignore_note = request.POST.get('ignore_note', '')[:255]
        orphan.save(update_fields=['status', 'ignore_note'])
        messages.success(request, _('Endpoint marked as ignored.'))
        return redirect('plugins:netbox_baramundi:orphan_list')


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
