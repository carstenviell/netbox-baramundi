"""
Minimal client for the baramundi bConnect REST API v2.

URLs: <server>/bconnect/<area>/v2.0/<resource>, HTTP basic auth, paged lists
(Page starting at 0, PageSize, response {data, hasNextPage}).
Write calls are never retried (a retry could assign a job twice).
"""
import os

import requests
from django.utils.translation import gettext as _

API_VERSION = 'v2.0'
PAGE_SIZE = 500
MAX_PAGES = 1000

# Job instance states -> generic outcome used by other plugins.
JOB_STATE_OUTCOME = {
    'FinishedSuccessfully': 'succeeded',
    'FinishedWithError': 'failed',
    'RequirementsNotMet': 'failed',
    'SkippedDueToIncompatibility': 'failed',
    'Cancelled': 'cancelled',
}


def job_outcome(state):
    """'succeeded' | 'failed' | 'cancelled' | 'running' (everything else is still in progress)."""
    return JOB_STATE_OUTCOME.get(state or '', 'running')


class BConnectError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class BConnect:
    def __init__(self, url, username, password, verify=True, timeout=30):
        self.base = url.rstrip('/')
        self.auth = (username, password)
        self.verify = verify
        self.timeout = timeout

    @classmethod
    def from_settings(cls):
        from .models import BaramundiSettings
        s = BaramundiSettings.load()
        if not s.url or not s.username:
            raise BConnectError(_('baramundi connection is not configured.'))
        password = os.environ.get(s.password_env or '')
        if not password:
            raise BConnectError(_('Environment variable %(name)s is not set.') % {'name': s.password_env})
        return cls(s.url, s.username, password, verify=s.ca_bundle or s.verify_tls, timeout=s.timeout)

    # -- transport -----------------------------------------------------------
    def request(self, method, area, resource, params=None, json=None):
        url = f'{self.base}/bconnect/{area}/{API_VERSION}/{resource.lstrip("/")}'
        attempts = 2 if method == 'GET' else 1
        for attempt in range(attempts):
            try:
                resp = requests.request(method, url, params=params, json=json, auth=self.auth,
                                        verify=self.verify, timeout=self.timeout,
                                        headers={'Accept': 'application/json'})
                break
            except requests.RequestException as exc:
                if attempt == attempts - 1:
                    raise BConnectError(str(exc))
        if resp.status_code >= 400:
            raise BConnectError(self._problem(resp), status=resp.status_code)
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            raise BConnectError(_('Response is not JSON (HTTP %(code)s)') % {'code': resp.status_code})

    @staticmethod
    def _problem(resp):
        try:
            p = resp.json()
            text = ' – '.join(str(x) for x in (p.get('title'), p.get('detail')) if x)
        except ValueError:
            text = resp.text[:200]
        return f'HTTP {resp.status_code}: {text}'.strip()

    def pages(self, area, resource, **params):
        for page in range(MAX_PAGES):
            data = self.request('GET', area, resource, params={**params, 'Page': page, 'PageSize': PAGE_SIZE}) or {}
            yield from data.get('data') or []
            if not data.get('hasNextPage'):
                return
        raise BConnectError(_('Too many pages from %(res)s') % {'res': resource})

    # -- API -----------------------------------------------------------------
    def management_server(self):
        return self.request('GET', 'servermanagement', 'ManagementServer') or {}

    def endpoints(self, host_name=None):
        params = {'HostName': host_name} if host_name else {}
        return list(self.pages('endpoints', 'Endpoints', **params))

    def endpoint(self, endpoint_id):
        return self.request('GET', 'endpoints', f'Endpoints/{endpoint_id}') or {}

    def job_definitions(self):
        return list(self.pages('jobs', 'JobDefinitions'))

    def create_job_instance(self, endpoint_id, job_definition_id):
        """Assign the job definition to the endpoint. Returns the job instance."""
        return self.request('POST', 'jobs', 'JobInstances', json={
            'jobDefinitionId': job_definition_id, 'endpointId': endpoint_id, 'startIfAlreadyAssigned': False,
        }) or {}

    def start_job_instance(self, instance_id):
        return self.request('POST', 'jobs', f'JobInstances/{instance_id}/Start')

    def job_instance(self, instance_id):
        return self.request('GET', 'jobs', f'JobInstances/{instance_id}') or {}

    def windows_update_states(self):
        return list(self.pages('updatemanagement', 'WindowsEndpoints'))
