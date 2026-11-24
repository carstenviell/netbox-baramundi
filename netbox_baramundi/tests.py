import json
import logging
import threading
from base64 import b64encode
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from django.test import TestCase

from dcim.models import Device, DeviceRole, DeviceType, Manufacturer, Site
from users.models import User

from .client import BConnect, BConnectError, job_outcome
from .custom_fields import CF_ENDPOINT, ensure_custom_fields
from .sync import match_endpoints, sync_endpoint_ids

G1, G2, G3 = ('11111111-1111-1111-1111-111111111111', '22222222-2222-2222-2222-222222222222',
              '33333333-3333-3333-3333-333333333333')
ENDPOINTS = [  # self-made minimal records
    {'id': G1, 'hostName': 'srv01.example.local', 'displayName': 'SRV01'},
    {'id': G2, 'hostName': 'app.example.local', 'displayName': 'app'},
    {'id': G3, 'hostName': 'app.other.local', 'displayName': 'app-other'},
]


def grant(user, model, actions, constraints=None):
    """NetBox evaluates permissions via ObjectPermission only (Django user_permissions are ignored)."""
    from django.contrib.contenttypes.models import ContentType
    from users.models import ObjectPermission
    perm = ObjectPermission.objects.create(name=f'test {model.__name__} {actions}', actions=actions,
                                           constraints=constraints)
    perm.object_types.add(ContentType.objects.get_for_model(model))
    perm.users.add(user)


class MatchTests(TestCase):
    def test_match(self):
        r = match_endpoints({'a': 'SRV01', 'b': 'srv01.example.local', 'c': 'app', 'd': 'nothere',
                             'e': 'app.example.local'}, ENDPOINTS)
        self.assertEqual(r['a'], ('matched', G1))          # case-insensitive, short name vs FQDN
        self.assertEqual(r['b'], ('matched', G1))          # FQDN
        self.assertEqual(r['c'], ('matched', G2))          # exact displayName wins over short-name ambiguity
        self.assertEqual(r['d'], ('missing', None))
        self.assertEqual(r['e'], ('matched', G2))
        self.assertEqual(match_endpoints({'x': 'app.third.local'}, ENDPOINTS)['x'][0], 'ambiguous')

    def test_endpoint_id_validated(self):
        from types import SimpleNamespace
        from .custom_fields import endpoint_id_for
        self.assertEqual(endpoint_id_for(SimpleNamespace(custom_field_data={CF_ENDPOINT: G1})), G1)
        for bad in ('../../jobs/v2.0/JobInstances', G1 + '/x', '', None):
            self.assertIsNone(endpoint_id_for(SimpleNamespace(custom_field_data={CF_ENDPOINT: bad})))

    def test_settings_validators(self):
        from django.core.exceptions import ValidationError
        from .models import BaramundiSettings
        for field, value in (('url', 'http://bms.example.test'), ('password_env', 'SECRET_KEY'),
                             ('password_env', 'BARAMUNDI_x;y')):
            s = BaramundiSettings(url='https://bms.example.test', username='u', password_env='BARAMUNDI_PASSWORD')
            setattr(s, field, value)
            with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                s.full_clean()

    def test_outcome(self):
        self.assertEqual([job_outcome(s) for s in ('FinishedSuccessfully', 'FinishedWithError', 'Cancelled',
                                                   'Running', None)],
                         ['succeeded', 'failed', 'cancelled', 'running', 'running'])


class _Handler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, *args):
        pass

    def _send(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        url = urlparse(self.path)
        q = parse_qs(url.query)
        type(self).requests.append(('GET', url.path, q, self.headers.get('Authorization')))
        if url.path == '/bconnect/endpoints/v2.0/Endpoints':
            page = int(q['Page'][0])
            self._send(200, {'data': ENDPOINTS[page * 2:page * 2 + 2], 'hasNextPage': page == 0})
        elif url.path == '/bconnect/servermanagement/v2.0/ManagementServer':
            self._send(200, {'name': 'mock', 'version': '1.0'})
        else:
            self._send(404, {'title': 'Not Found', 'detail': url.path})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        type(self).requests.append(('POST', self.path, body, None))
        self._send(201, {'id': 'inst-1', 'state': 'Assigned'})


class ClientTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.server = HTTPServer(('127.0.0.1', 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.client_ = BConnect(f'http://127.0.0.1:{cls.server.server_port}', 'svc', 'pw', timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        super().tearDownClass()

    def test_paging_auth_and_errors(self):
        _Handler.requests = []
        self.assertEqual([e['id'] for e in self.client_.endpoints()], [G1, G2, G3])  # two pages
        self.assertEqual(_Handler.requests[0][3], 'Basic ' + b64encode(b'svc:pw').decode())
        self.assertEqual(self.client_.management_server()['version'], '1.0')
        with self.assertRaises(BConnectError) as ctx:
            self.client_.job_instance('nope')
        self.assertEqual(ctx.exception.status, 404)

    def test_create_job_instance_body(self):
        _Handler.requests = []
        self.assertEqual(self.client_.create_job_instance(G1, 'job-1')['id'], 'inst-1')
        method, path, body, _auth = _Handler.requests[-1]
        self.assertEqual((method, path), ('POST', '/bconnect/jobs/v2.0/JobInstances'))
        self.assertEqual(body, {'jobDefinitionId': 'job-1', 'endpointId': G1, 'startIfAlreadyAssigned': False})

    def test_sync_fills_only_empty_fields(self):
        ensure_custom_fields()
        site = Site.objects.create(name='S', slug='s')
        dt = DeviceType.objects.create(manufacturer=Manufacturer.objects.create(name='M', slug='m'), model='T', slug='t')
        role = DeviceRole.objects.create(name='R', slug='r')
        new = Device.objects.create(name='srv01', site=site, device_type=dt, role=role)
        manual = Device.objects.create(name='app', site=site, device_type=dt, role=role,
                                       custom_field_data={CF_ENDPOINT: G3})
        counts, _endpoints = sync_endpoint_ids(self.client_, logging.getLogger('test'))
        new.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(new.custom_field_data[CF_ENDPOINT], G1)
        self.assertEqual(manual.custom_field_data[CF_ENDPOINT], G3)  # never overwritten
        self.assertEqual(counts['matched'], 1)

    def test_views(self):
        from .models import BaramundiSettings
        staff = User.objects.create(username='staff_b')
        grant(staff, BaramundiSettings, ['view', 'change'])
        self.assertTrue(staff.has_perm('netbox_baramundi.change_baramundisettings'))  # has the permission ...
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/plugins/baramundi/settings/').status_code, 403)  # superuser only
        self.client.force_login(User.objects.create(username='admin_b', is_superuser=True))
        self.assertEqual(self.client.get('/plugins/baramundi/settings/').status_code, 200)


    def test_endpoint_tab(self):
        ensure_custom_fields()
        site = Site.objects.create(name='S2', slug='s2')
        dt = DeviceType.objects.create(manufacturer=Manufacturer.objects.create(name='M2', slug='m2'), model='T2', slug='t2')
        role = DeviceRole.objects.create(name='R2', slug='r2')
        with_id = Device.objects.create(name='with-id', site=site, device_type=dt, role=role,
                                        custom_field_data={CF_ENDPOINT: G1})
        without = Device.objects.create(name='without-id', site=site, device_type=dt, role=role)
        self.client.force_login(User.objects.create(username='admin_t', is_superuser=True))
        tab = f'{with_id.get_absolute_url()}baramundi/'
        self.assertContains(self.client.get(with_id.get_absolute_url()), f'href="{tab}"')
        self.assertNotContains(self.client.get(without.get_absolute_url()), 'baramundi/"')
        self.assertContains(self.client.get(tab), 'alert-warning')  # not configured: shown, never raised

class FakeClient:
    def __init__(self, endpoints):
        self._endpoints = endpoints

    def endpoints(self):
        return self._endpoints


def _objects(prefix):
    from virtualization.models import Cluster, ClusterType
    site = Site.objects.create(name=prefix, slug=prefix)
    dt = DeviceType.objects.create(manufacturer=Manufacturer.objects.create(name=prefix, slug=prefix),
                                   model=prefix, slug=prefix)
    role = DeviceRole.objects.create(name=prefix, slug=prefix)
    cluster = Cluster.objects.create(name=prefix, type=ClusterType.objects.create(name=prefix, slug=prefix))
    return site, dt, role, cluster


class OverviewAndOrphanTests(TestCase):
    """Sync states, orphan list, manual assignment and import (no bMS needed: FakeClient)."""
    LOG = logging.getLogger('test')

    def setUp(self):
        ensure_custom_fields()
        self.site, self.dt, self.role, self.cluster = _objects('ov')

    def dev(self, name, endpoint_id=None):
        return Device.objects.create(name=name, site=self.site, device_type=self.dt, role=self.role,
                                     custom_field_data={CF_ENDPOINT: endpoint_id} if endpoint_id else {})

    def test_states_and_orphans(self):
        from .models import EndpointLink, UnmatchedEndpoint
        from .sync import refresh_orphans
        gone = '44444444-4444-4444-4444-444444444444'
        matched, missing, stale = self.dev('srv01'), self.dev('nothere'), self.dev('old', gone)
        ambiguous = self.dev('app.third.local')
        counts, endpoints = sync_endpoint_ids(FakeClient(ENDPOINTS), self.LOG)
        state = {o.name: EndpointLink.objects.get(device=o).state for o in (matched, missing, stale, ambiguous)}
        self.assertEqual(state, {'srv01': 'matched', 'nothere': 'missing', 'old': 'stale', 'app.third.local': 'ambiguous'})
        stale.refresh_from_db()
        self.assertEqual(stale.custom_field_data[CF_ENDPOINT], gone)  # stale is flagged, never cleared
        self.assertIn(G2, EndpointLink.objects.get(device=ambiguous).message)

        UnmatchedEndpoint.objects.create(endpoint_id='55555555-5555-5555-5555-555555555555')  # vanished
        refresh_orphans(endpoints)
        self.assertEqual(set(UnmatchedEndpoint.objects.values_list('endpoint_id', flat=True)), {G2, G3})
        UnmatchedEndpoint.objects.filter(endpoint_id=G3).update(status='ignored')
        missing.custom_field_data[CF_ENDPOINT] = G2  # assigned elsewhere meanwhile
        missing.save()
        refresh_orphans(endpoints)
        self.assertEqual(dict(UnmatchedEndpoint.objects.values_list('endpoint_id', 'status')),
                         {G2: 'assigned', G3: 'ignored'})

    def test_selection_and_taken_ids(self):
        from .models import EndpointLink
        holder = self.dev('other', G1)
        first, second = self.dev('srv01'), self.dev('SRV01.example.local')
        sync_endpoint_ids(FakeClient(ENDPOINTS), self.LOG, objects=[second])
        self.assertFalse(EndpointLink.objects.filter(device=first).exists())  # not selected
        second.refresh_from_db()
        self.assertNotIn(CF_ENDPOINT, second.custom_field_data)  # G1 is already taken by holder
        self.assertEqual(EndpointLink.objects.get(device=second).state, 'missing')
        self.assertEqual(holder.custom_field_data[CF_ENDPOINT], G1)

    def test_assign_endpoint(self):
        from django.core.exceptions import ValidationError
        from .sync import assign_endpoint
        target, other = self.dev('target'), self.dev('busy', G2)
        assign_endpoint(target, G1)
        target.refresh_from_db()
        self.assertEqual(target.custom_field_data[CF_ENDPOINT], G1)
        with self.assertRaises(ValidationError):
            assign_endpoint(other, G3)  # already has another ID
        with self.assertRaises(ValidationError):
            assign_endpoint(self.dev('free'), G1)  # ID held by target

    def test_import_and_permissions(self):
        from virtualization.models import VirtualMachine
        from .models import UnmatchedEndpoint
        orphan = UnmatchedEndpoint.objects.create(endpoint_id=G3, display_name='app-other', host_name='app.other.local',
                                                  serial_number='SN1', operating_system='Windows 11', comment='desk 4')
        user = User.objects.create(username='importer')
        self.client.force_login(user)
        url = f'/plugins/baramundi/orphans/{orphan.pk}/import/'
        post = {'name': 'app-other', 'kind': 'device', 'site': self.site.pk, 'role': self.role.pk,
                'device_type': self.dt.pk, 'status': 'active'}
        self.assertEqual(self.client.post(url, post).status_code, 403)  # no orphan permission
        grant(user, UnmatchedEndpoint, ['view', 'change'])
        self.client.post(url, post)
        self.assertFalse(Device.objects.filter(name='app-other').exists())  # no add_device
        grant(user, Device, ['view', 'add'])
        self.assertEqual(self.client.post(url, post).status_code, 302)
        device = Device.objects.get(name='app-other')
        self.assertEqual((device.serial, device.custom_field_data[CF_ENDPOINT]), ('SN1', G3))
        self.assertIn('Windows 11', device.comments)
        self.assertIn('desk 4', device.comments)
        orphan.refresh_from_db()
        self.assertEqual((orphan.status, orphan.assigned_device), ('imported', device))

        # bulk: one VM is created, one fails on the duplicate name and is reported
        grant(user, VirtualMachine, ['view', 'add'])
        a = UnmatchedEndpoint.objects.create(endpoint_id=G1, display_name='vm-new')
        b = UnmatchedEndpoint.objects.create(endpoint_id=G2, display_name='vm-new')
        resp = self.client.post('/plugins/baramundi/orphans/bulk-import/',
                                {'pk': [a.pk, b.pk], '_import': '1', 'kind': 'vm', 'cluster': self.cluster.pk,
                                 'status': 'active'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(VirtualMachine.objects.filter(name='vm-new').count(), 1)
        self.assertEqual(sorted(UnmatchedEndpoint.objects.filter(pk__in=[a.pk, b.pk])
                                .values_list('status', flat=True)), ['imported', 'unresolved'])

    def test_pages_render(self):
        from .models import UnmatchedEndpoint
        from virtualization.models import VirtualMachine
        orphan = UnmatchedEndpoint.objects.create(endpoint_id=G1, display_name='x')
        self.dev('srv01')
        VirtualMachine.objects.create(name='vm1', cluster=self.cluster)
        self.client.force_login(User.objects.create(username='admin_o', is_superuser=True))
        for url in ('sync/devices/', 'sync/vms/', 'sync/devices/?baramundi_status=never_checked', 'orphans/',
                    'orphans/?status=', f'orphans/{orphan.pk}/assign/', f'orphans/{orphan.pk}/import/',
                    f'orphans/{orphan.pk}/ignore/'):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(f'/plugins/baramundi/{url}').status_code, 200)
        resp = self.client.post('/plugins/baramundi/orphans/bulk-import/', {'pk': [orphan.pk]})
        self.assertContains(resp, 'name="_import"')
        resp = self.client.post(f'/plugins/baramundi/orphans/{orphan.pk}/ignore/', {'ignore_note': 'lab'})
        orphan.refresh_from_db()
        self.assertEqual((orphan.status, orphan.ignore_note), ('ignored', 'lab'))


class DashboardTests(TestCase):
    def test_widget(self):
        from django.test import RequestFactory
        from uuid import uuid4
        from django.utils import timezone
        from core.models import Job
        from virtualization.models import VirtualMachine
        from .dashboard import BaramundiStatusWidget
        from .jobs import EndpointSyncJob
        from .models import UnmatchedEndpoint
        ensure_custom_fields()
        site, dt, role, cluster = _objects('db')
        Device.objects.create(name='d1', site=site, device_type=dt, role=role, custom_field_data={CF_ENDPOINT: G1})
        Device.objects.create(name='d2', site=site, device_type=dt, role=role)
        VirtualMachine.objects.create(name='v1', cluster=cluster)
        UnmatchedEndpoint.objects.create(endpoint_id=G2, display_name='open-one')
        UnmatchedEndpoint.objects.create(endpoint_id=G3, display_name='ignored-one', status='ignored')
        Job.objects.create(name=EndpointSyncJob.Meta.name, status='completed', completed=timezone.now(), job_id=uuid4())

        request = RequestFactory().get('/')
        request.user = User.objects.create(username='admin_d', is_superuser=True)
        html = BaramundiStatusWidget().render(request)
        self.assertIn('1 of 2 with endpoint ID', html)
        self.assertIn('0 of 1 with endpoint ID', html)
        self.assertIn('badge text-bg-warning">1<', html)  # ignored orphans are not counted
        self.assertIn('/core/jobs/', html)

        request.user = User.objects.create(username='nobody_d')
        html = BaramundiStatusWidget().render(request)
        self.assertIn('0 of 0 with endpoint ID', html)
        self.assertNotIn('orphans/', html)
        self.assertNotIn('/core/jobs/', html)


class TranslationTests(TestCase):
    def test_compiled_catalog_is_current(self):
        """django.mo is shipped (target systems usually lack gettext) - it must contain every translated msgid."""
        import gettext
        import os
        import re
        base = os.path.join(os.path.dirname(__file__), 'locale', 'de', 'LC_MESSAGES')
        po = open(os.path.join(base, 'django.po'), encoding='utf-8').read()
        with open(os.path.join(base, 'django.mo'), 'rb') as f:
            catalog = gettext.GNUTranslations(f)._catalog
        missing = [m for m in re.findall(r'^msgid "(.+)"\nmsgstr "(?!")', po, re.M)
                   if m.replace('\\"', '"') not in catalog]
        self.assertEqual(missing, [], 'django.mo is outdated - run makemessages/msgfmt (see CLAUDE.md)')
        self.assertEqual(re.findall(r'^#, .*fuzzy.*\n(?:#\|.*\n)*msgid "(.*)"', po, re.M), [], 'fuzzy (guessed) translations - fix them')
