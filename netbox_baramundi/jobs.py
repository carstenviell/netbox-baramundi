from dcim.models import Device
from netbox.jobs import JobRunner, system_job
from netbox.plugins import get_plugin_config
from virtualization.models import VirtualMachine

from .client import BConnect, BConnectError
from .sync import refresh_orphans, sync_endpoint_ids


@system_job(interval=get_plugin_config('netbox_baramundi', 'endpoint_sync_interval_min'))
class EndpointSyncJob(JobRunner):
    """Without ids: all devices/VMs plus the orphan list. With ids: only the selection (sync overview)."""
    class Meta:
        name = 'baramundi endpoint sync'

    def run(self, *args, device_ids=None, vm_ids=None, **kwargs):
        try:
            client = BConnect.from_settings()
        except BConnectError as exc:
            self.logger.info(f'Skipped: {exc}')  # not configured is not an error
            return
        selection = None
        if device_ids is not None or vm_ids is not None:
            selection = [*Device.objects.filter(pk__in=device_ids or []).select_related('baramundi_link'),
                         *VirtualMachine.objects.filter(pk__in=vm_ids or []).select_related('baramundi_link')]
        _counts, endpoints = sync_endpoint_ids(client, self.logger, selection)
        if selection is None:
            orphans = refresh_orphans(endpoints)
            self.logger.info(f"Orphans: {orphans['unresolved']} unresolved, {orphans['assigned']} newly assigned, "
                             f"{orphans['deleted']} removed (no longer in baramundi).")
