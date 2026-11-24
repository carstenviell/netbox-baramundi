**English** | [Deutsch](README.de.md)

# NetBox baramundi

[NetBox](https://github.com/netbox-community/netbox) plugin integrating the **baramundi Management Suite** via the **bConnect REST API v2**.

## Features

- Settings page with *Test connection* (shows the name and version of the management server)
- Custom field `baramundi_endpoint_id` on devices and VMs, filled by an **endpoint sync**
  (daily and on demand): host name / display name, case-insensitive, short name vs. FQDN.
  Only empty fields are filled – existing values are never overwritten; ambiguous matches are only reported,
  every assignment is written to the job log. With several domains, check the log: a short name is matched to
  an FQDN only if it is unique.
- *baramundi* card on device/VM pages (endpoint ID) and a *baramundi* tab with live endpoint data (host name, OS, last seen; cached for 5 minutes). bConnect is only queried when the tab is opened.
- `netbox_baramundi.client.BConnect` for other plugins, e.g. the baramundi backend of
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (start patch jobs, job status, Windows update compliance)

## Requirements

- NetBox **4.7** or later
- **baramundi bConnect API v2**

## Installation

The plugin is not published on PyPI. Install it from the GitHub release archive – this works without `git`,
also in the netbox-docker image. Replace `v0.1.3` with the [release](https://github.com/carstenviell/netbox-baramundi/releases) you want.

**NetBox installed from source (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz

# keep the plugin when NetBox is upgraded (upgrade.sh reinstalls local_requirements.txt)
echo "https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz" | sudo tee -a /opt/netbox/local_requirements.txt
```

**netbox-docker:** add to `plugin_requirements.txt`

```text
https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz
```

and to `Dockerfile-Plugins` (build `netbox`, `netbox-worker` and `netbox-housekeeping` from it via `docker-compose.override.yml`):

```dockerfile
FROM netboxcommunity/netbox:v4.7
COPY ./plugin_requirements.txt /opt/netbox/
RUN /usr/local/bin/uv pip install -r /opt/netbox/plugin_requirements.txt
```

Enable the plugin in `configuration.py` (Docker: `configuration/plugins.py`):

```python
PLUGINS = [
    # ...
    'netbox_baramundi',
]
```

Apply the migrations and restart **both** services:

```bash
cd /opt/netbox/netbox
sudo /opt/netbox/venv/bin/python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

Docker: `docker compose build --no-cache && docker compose up -d` – migrations run automatically at start.

Optional settings (these are the defaults):

```python
PLUGINS_CONFIG = {
    "netbox_baramundi": {
        "endpoint_sync_interval_min": 1440,
        "panel_cache_seconds": 300,
    },
}
```

Provide the password of the bConnect user as environment variable `BARAMUNDI_PASSWORD` (or another name
starting with `BARAMUNDI_`) for **both** the web service and the worker (Docker: `env/netbox.env`).

**systemd:** use an environment file. It keeps the password out of the unit (`systemctl show` is readable
by every user), and systemd does not expand `%` placeholders inside it:

```bash
printf '%s\n' 'BARAMUNDI_PASSWORD=<password>' > /etc/netbox-baramundi.env
chmod 600 /etc/netbox-baramundi.env
for u in netbox netbox-rq; do
  mkdir -p /etc/systemd/system/$u.service.d
  printf '[Service]\nEnvironmentFile=/etc/netbox-baramundi.env\n' > /etc/systemd/system/$u.service.d/baramundi.conf
done
systemctl daemon-reload && systemctl restart netbox netbox-rq
tr '\0' '\n' < /proc/$(systemctl show -p MainPID --value netbox)/environ | grep -c BARAMUNDI_   # must print 1
```

> **Pitfall:** do **not** set the password via `Environment=` in the unit or in `systemctl edit`. There `%` is a
> systemd placeholder, and an invalid one (e.g. `%"`) makes systemd drop the whole line silently, so the
> plugin reports *Environment variable BARAMUNDI_PASSWORD is not set*. The line must be in the `[Service]`
> section, and `systemctl daemon-reload` is required after every change.

After the restart open *Plugins → baramundi settings* (superusers only).

### Upgrade

Install the new release archive (also update `local_requirements.txt` / `plugin_requirements.txt`),
then `migrate` and restart (Docker: rebuild).

## Configuration

| Setting | |
|---|---|
| Server URL | e.g. `https://bms.example.local` (without `/bconnect`; HTTPS only) |
| User | bConnect user (HTTP basic auth); grant only the rights you need: read endpoints and job definitions, assign jobs, read job instances and update management |
| Password environment variable | Name of the variable that holds the password in the NetBox **and** worker containers (must start with `BARAMUNDI_`, default `BARAMUNDI_PASSWORD`). The password is never stored in the database. |
| Verify TLS / CA bundle | Keep TLS verification on; point to your CA bundle for an internal CA |

## Language

The user interface is English and ships with a German translation. It follows the language the user selected in
NetBox (*Profile → Preferences → Language*); languages without a translation fall back to English.

## License

[Apache License 2.0](LICENSE). baramundi and bConnect are trademarks of their respective owner; this plugin is not affiliated with baramundi.
