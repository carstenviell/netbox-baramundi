# NetBox baramundi

NetBox plugin integrating the **baramundi Management Suite** via the **bConnect REST API v2**.

- Settings page with *Test connection* (shows the name and version of the management server)
- Custom field `baramundi_endpoint_id` on devices and VMs, filled by an **endpoint sync**
  (daily and on demand): host name / display name, case-insensitive, short name vs. FQDN.
  Only empty fields are filled – existing values are never overwritten; ambiguous matches are only reported,
  every assignment is written to the job log. With several domains, check the log: a short name is matched to
  an FQDN only if it is unique.
- *baramundi* panel on device/VM pages (endpoint, host name, OS, last seen; cached for 5 minutes)
- `netbox_baramundi.client.BConnect` for other plugins, e.g. the baramundi backend of
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (start patch jobs, job status, Windows update compliance)

Requires NetBox ≥ 4.7 and **baramundi bConnect API v2**.

## Installation

The plugin is not published on PyPI or GitHub yet. Build an archive from the repository (contains only
versioned files) and copy it to the NetBox host:

```bash
git archive --format=tar.gz --prefix=netbox-baramundi-0.1.2/ -o dist/netbox-baramundi-0.1.2.tar.gz HEAD
```

**NetBox installed from source (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install /path/to/netbox-baramundi-0.1.2.tar.gz
```

**netbox-docker:** put the archive next to your `Dockerfile-Plugins` and add

```dockerfile
COPY ./netbox-baramundi-0.1.2.tar.gz /opt/
RUN /usr/local/bin/uv pip install /opt/netbox-baramundi-0.1.2.tar.gz
```

Enable it in `configuration.py` (Docker: `configuration/plugins.py`):

```python
PLUGINS = ["netbox_baramundi"]
PLUGINS_CONFIG = {
    "netbox_baramundi": {                # optional - these are the defaults
        "endpoint_sync_interval_min": 1440,
        "panel_cache_seconds": 300,
    },
}
```

Provide the password of the bConnect user as environment variable `BARAMUNDI_PASSWORD` (or another name
starting with `BARAMUNDI_`) for **both** the web service and the worker
(systemd: `systemctl edit netbox netbox-rq` → `Environment=BARAMUNDI_PASSWORD=...`; Docker: `env/netbox.env`).

Run `manage.py migrate`, restart `netbox` **and** `netbox-rq` (the worker runs the endpoint sync), then open *Plugins → baramundi settings* (superusers only):

| Setting | |
|---|---|
| Server URL | e.g. `https://bms.example.local` (without `/bconnect`; HTTPS only) |
| User | bConnect user (HTTP basic auth); grant only the rights you need: read endpoints and job definitions, assign jobs, read job instances and update management |
| Password environment variable | Name of the variable that holds the password in the NetBox **and** worker containers (must start with `BARAMUNDI_`, default `BARAMUNDI_PASSWORD`). The password is never stored in the database. |
| Verify TLS / CA bundle | Keep TLS verification on; point to your CA bundle for an internal CA |

## License

Apache-2.0. baramundi and bConnect are trademarks of their respective owner; this plugin is not affiliated with baramundi.
