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

Das Plugin ist noch nicht auf PyPI oder GitHub veröffentlicht. Aus dem Repository ein Archiv bauen (enthält nur
versionierte Dateien) und auf den NetBox-Host kopieren:

```bash
git archive --format=tar.gz --prefix=netbox-baramundi-0.1.2/ -o dist/netbox-baramundi-0.1.2.tar.gz HEAD
```

**NetBox aus dem Quellcode (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install /pfad/zu/netbox-baramundi-0.1.2.tar.gz
```

**netbox-docker:** Archiv neben die `Dockerfile-Plugins` legen und ergänzen

```dockerfile
COPY ./netbox-baramundi-0.1.2.tar.gz /opt/
RUN /usr/local/bin/uv pip install /opt/netbox-baramundi-0.1.2.tar.gz
```

Aktivieren in der `configuration.py` (Docker: `configuration/plugins.py`):

```python
PLUGINS = ["netbox_baramundi"]
PLUGINS_CONFIG = {
    "netbox_baramundi": {                # optional – das sind die Standardwerte
        "endpoint_sync_interval_min": 1440,
        "panel_cache_seconds": 300,
    },
}
```

Das Passwort des bConnect-Benutzers als Umgebungsvariable `BARAMUNDI_PASSWORD` (oder ein anderer Name mit Präfix
`BARAMUNDI_`) für **beide** Dienste bereitstellen, Web und Worker
(systemd: `systemctl edit netbox netbox-rq` → `Environment=BARAMUNDI_PASSWORD=...`; Docker: `env/netbox.env`).

`manage.py migrate` ausführen, `netbox` **und** `netbox-rq` neu starten (der Worker führt den Endpoint-Abgleich aus),
dann *Plugins → baramundi settings* öffnen (nur Superuser).

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
