[English](README.md) | **Deutsch**

# NetBox baramundi

[NetBox](https://github.com/netbox-community/netbox)-Plugin, das die **baramundi Management Suite** über die
**bConnect REST API v2** anbindet.

## Funktionen

- Einstellungsseite mit *Verbindung testen* (zeigt Name und Version des Management-Servers)
- Custom Field `baramundi_endpoint_id` an Geräten und VMs, befüllt durch einen **Endpoint-Abgleich**
  (täglich und auf Knopfdruck): Hostname / Anzeigename, ohne Groß-/Kleinschreibung, Kurzname gegen FQDN.
  Es werden nur leere Felder befüllt – vorhandene Werte werden nie überschrieben; mehrdeutige Treffer werden nur
  gemeldet, jede Zuordnung steht im Job-Log. Bei mehreren Domänen das Log prüfen: Ein Kurzname wird nur dann einem
  FQDN zugeordnet, wenn er eindeutig ist.
- Bereich *baramundi* auf Geräte-/VM-Seiten (Endpoint, Hostname, Betriebssystem, zuletzt gesehen; 5 Minuten gecacht)
- `netbox_baramundi.client.BConnect` für andere Plugins, z. B. das baramundi-Backend von
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (Patch-Jobs starten, Job-Status, Windows-Update-Compliance)

## Voraussetzungen

- NetBox **4.7** oder neuer
- **baramundi bConnect API v2**

## Installation

Das Plugin liegt nicht auf PyPI. Installiert wird aus dem GitHub-Release-Archiv – das funktioniert ohne `git`,
auch im netbox-docker-Image. `v0.1.3` ggf. durch das gewünschte [Release](https://github.com/carstenviell/netbox-baramundi/releases) ersetzen.

**NetBox aus dem Quellcode (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz

# bleibt bei NetBox-Upgrades erhalten (upgrade.sh installiert local_requirements.txt neu)
echo "https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz" | sudo tee -a /opt/netbox/local_requirements.txt
```

**netbox-docker:** in `plugin_requirements.txt`

```text
https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.1.3.tar.gz
```

und in `Dockerfile-Plugins` (aus dem `netbox`, `netbox-worker` und `netbox-housekeeping` per `docker-compose.override.yml` gebaut werden):

```dockerfile
FROM netboxcommunity/netbox:v4.7
COPY ./plugin_requirements.txt /opt/netbox/
RUN /usr/local/bin/uv pip install -r /opt/netbox/plugin_requirements.txt
```

Plugin aktivieren in der `configuration.py` (Docker: `configuration/plugins.py`):

```python
PLUGINS = [
    # ...
    'netbox_baramundi',
]
```

Migrationen anwenden und **beide** Dienste neu starten:

```bash
cd /opt/netbox/netbox
sudo /opt/netbox/venv/bin/python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

Docker: `docker compose build --no-cache && docker compose up -d` – die Migrationen laufen beim Start automatisch.

Optionale Einstellungen (das sind die Standardwerte):

```python
PLUGINS_CONFIG = {
    "netbox_baramundi": {
        "endpoint_sync_interval_min": 1440,
        "panel_cache_seconds": 300,
    },
}
```

Das Passwort des bConnect-Benutzers als Umgebungsvariable `BARAMUNDI_PASSWORD` (oder ein anderer Name mit Präfix
`BARAMUNDI_`) für **beide** Dienste bereitstellen, Web und Worker
(systemd: `systemctl edit netbox netbox-rq` → `Environment=BARAMUNDI_PASSWORD=...`; Docker: `env/netbox.env`).
Nach dem Neustart *Plugins → baramundi settings* öffnen (nur Superuser).

### Upgrade

Neues Release-Archiv installieren (auch in `local_requirements.txt` bzw. `plugin_requirements.txt`
anpassen), danach `migrate` und Neustart (Docker: neu bauen).

## Konfiguration

| Einstellung | |
|---|---|
| Server-URL | z. B. `https://bms.example.local` (ohne `/bconnect`; nur HTTPS) |
| Benutzer | bConnect-Benutzer (HTTP Basic Auth); nur die nötigen Rechte vergeben: Endpoints und Job-Definitionen lesen, Jobs zuweisen, Job-Instanzen und Update-Management lesen |
| Umgebungsvariable für das Passwort | Name der Variable, die das Passwort im NetBox- **und** Worker-Container enthält (muss mit `BARAMUNDI_` beginnen, Standard `BARAMUNDI_PASSWORD`). Das Passwort wird nie in der Datenbank gespeichert. |
| TLS prüfen / CA-Bundle | TLS-Prüfung eingeschaltet lassen; bei interner CA auf das CA-Bundle verweisen |

## Sprache

Die Oberfläche ist englisch, eine deutsche Übersetzung wird mitgeliefert. Angezeigt wird die Sprache, die der Benutzer
in NetBox gewählt hat (*Profil → Einstellungen → Sprache*); für Sprachen ohne Übersetzung erscheint Englisch.

## Lizenz

[Apache License 2.0](LICENSE). baramundi und bConnect sind Marken ihres jeweiligen Inhabers; dieses Plugin steht in
keiner Verbindung zu baramundi.
