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
- **Sync overview** for devices and for virtual machines (*Plugins → baramundi*): endpoint ID, status
  (assigned / not found / ambiguous with candidates / stale = endpoint no longer exists in baramundi / never checked),
  last check, filter by status, and *Sync selected with baramundi* for a selection or the whole filtered list.
  An endpoint ID that is already set on another object is never assigned a second time.
- **baramundi orphans**: endpoints whose ID is set on no device or VM (refreshed by every full endpoint sync or
  with *Refresh from baramundi*). Per endpoint:
  - *Assign* it to an existing device or VM (only if that object has no other endpoint ID; recorded in the changelog),
  - *Import* it as a new device (site, role, device type) or VM (site or cluster) – the name is prefilled with the
    display name, serial number (devices), operating system and baramundi comment are taken over,
  - *Ignore* it with an optional note.

  Several endpoints can be imported at once with common values (*Import selected*); endpoints that cannot be
  created (e.g. duplicate name) are skipped and listed.
- Permissions: the overviews need view permission on devices/VMs, *Sync selected* needs
  `netbox_baramundi.change_endpointlink`, the orphan list `view_unmatchedendpoint`, its actions
  `change_unmatchedendpoint` plus `change` (assign) or `add` (import) on devices/VMs.
- *baramundi* card on device/VM pages (endpoint ID) and a *baramundi* tab with live endpoint data (host name, OS, last seen; cached for 5 minutes). bConnect is only queried when the tab is opened.
- `netbox_baramundi.client.BConnect` for other plugins, e.g. the baramundi backend of
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (start patch jobs, job status, Windows update compliance)

## Requirements

- NetBox **4.7** or later
- **baramundi bConnect API v2**

## Installation

The plugin is not published on PyPI. Install it from the GitHub release archive – this works without `git`,
also in the netbox-docker image. Replace `v0.2.0` with the [release](https://github.com/carstenviell/netbox-baramundi/releases) you want.

**NetBox installed from source (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.2.0.tar.gz

# keep the plugin when NetBox is upgraded (upgrade.sh reinstalls local_requirements.txt)
echo "https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.2.0.tar.gz" | sudo tee -a /opt/netbox/local_requirements.txt
```

**netbox-docker:** add to `plugin_requirements.txt`

```text
https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.2.0.tar.gz
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

**systemd:** two ways, both for `netbox` **and** `netbox-rq`.

*Option A – directly with `systemctl edit`* (fine for passwords without special characters):

```bash
sudo systemctl edit netbox
sudo systemctl edit netbox-rq
```

In each editor, insert between the two comment lines at the top (`### Anything between here …` and
`### Lines below this comment …`), save and close:

```ini
[Service]
Environment="BARAMUNDI_PASSWORD=<password>"
```

> **Pitfall:** in `Environment=` a `%` is a systemd placeholder and must be written as `%%`. An invalid one
> (e.g. `%"`) makes systemd drop the whole line silently, so the plugin reports *Environment variable
> BARAMUNDI_PASSWORD is not set*. Section header must be exactly `[Service]`. Note: `systemctl show` displays
> the password to every user, so prefer option B on shared servers.

*Option B – environment file* (recommended: any special characters allowed, file readable by root only):

```bash
printf '%s\n' 'BARAMUNDI_PASSWORD=<password>' | sudo tee /etc/netbox-baramundi.env >/dev/null
sudo chmod 600 /etc/netbox-baramundi.env
for u in netbox netbox-rq; do
  sudo mkdir -p /etc/systemd/system/$u.service.d
  printf '[Service]\nEnvironmentFile=/etc/netbox-baramundi.env\n' | sudo tee /etc/systemd/system/$u.service.d/baramundi.conf >/dev/null
done
```

*Then (both options)* reload, restart and check:

```bash
sudo systemctl daemon-reload
sudo systemctl restart netbox netbox-rq
sudo cat /proc/$(systemctl show -p MainPID --value netbox)/environ | tr '\0' '\n' | grep -c BARAMUNDI_   # must print 1
```

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
