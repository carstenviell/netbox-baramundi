# NetBox baramundi

NetBox plugin integrating the **baramundi Management Suite** via the **bConnect REST API v2**.

- Settings page with *Test connection* (shows the name and version of the management server)
- Custom field `baramundi_endpoint_id` on devices and VMs, filled by an **endpoint sync**
  (daily and on demand): host name / display name, case-insensitive, short name vs. FQDN.
  Only empty fields are filled – existing values are never overwritten; ambiguous matches are only reported.
- *baramundi* panel on device/VM pages (endpoint, host name, OS, last seen; cached for 5 minutes)
- `netbox_baramundi.client.BConnect` for other plugins, e.g. the baramundi backend of
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (start patch jobs, job status, Windows update compliance)

Requires NetBox ≥ 4.7 and **baramundi bConnect API v2**.

## Installation

```bash
pip install netbox-baramundi
```

```python
PLUGINS = ["netbox_baramundi"]
PLUGINS_CONFIG = {
    "netbox_baramundi": {
        "endpoint_sync_interval_min": 1440,
        "panel_cache_seconds": 300,
    },
}
```

Run `manage.py migrate`, then open *Plugins → baramundi settings*:

| Setting | |
|---|---|
| Server URL | e.g. `https://bms.example.local` (without `/bconnect`) |
| User | bConnect user (HTTP basic auth); grant only the rights you need: read endpoints and job definitions, assign jobs, read job instances and update management |
| Password environment variable | Name of the variable that holds the password in the NetBox **and** worker containers (default `BARAMUNDI_PASSWORD`). The password is never stored in the database. |
| Verify TLS / CA bundle | Keep TLS verification on; point to your CA bundle for an internal CA |

## License

Apache-2.0. baramundi and bConnect are trademarks of their respective owner; this plugin is not affiliated with baramundi.
