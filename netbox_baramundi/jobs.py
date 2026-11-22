from netbox.jobs import JobRunner, system_job
from netbox.plugins import get_plugin_config

from .client import BConnect, BConnectError
from .sync import sync_endpoint_ids


@system_job(interval=get_plugin_config('netbox_baramundi', 'endpoint_sync_interval_min'))
class EndpointSyncJob(JobRunner):
    class Meta:
        name = 'baramundi endpoint sync'

    def run(self, *args, **kwargs):
        try:
            client = BConnect.from_settings()
        except BConnectError as exc:
            self.logger.info(f'Skipped: {exc}')  # not configured is not an error
            return
        sync_endpoint_ids(client, self.logger)
