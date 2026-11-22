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
        counts = sync_endpoint_ids(self.client_, logging.getLogger('test'))
        new.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(new.custom_field_data[CF_ENDPOINT], G1)
        self.assertEqual(manual.custom_field_data[CF_ENDPOINT], G3)  # never overwritten
        self.assertEqual(counts['matched'], 1)

    def test_views(self):
        from django.contrib.auth.models import Permission
        staff = User.objects.create(username='staff_b')
        staff.user_permissions.add(Permission.objects.get(codename='change_baramundisettings'))
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/plugins/baramundi/settings/').status_code, 403)  # superuser only
        self.client.force_login(User.objects.create(username='admin_b', is_superuser=True))
        self.assertEqual(self.client.get('/plugins/baramundi/settings/').status_code, 200)
