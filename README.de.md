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
- **Sync-Übersicht** für Geräte und für virtuelle Maschinen (*Plugins → baramundi*): Endpoint-ID, Status
  (zugeordnet / nicht gefunden / mehrdeutig mit Kandidaten / veraltet = Endpoint existiert in baramundi nicht mehr /
  nie geprüft), letzte Prüfung, Filter nach Status und *Auswahl mit baramundi abgleichen* für eine Auswahl oder die
  ganze gefilterte Liste. Eine Endpoint-ID, die schon an einem anderen Objekt steht, wird nie ein zweites Mal vergeben.
- **baramundi-Orphans**: Endpoints, deren ID an keinem Gerät und keiner VM steht (aktualisiert bei jedem vollständigen
  Endpoint-Abgleich oder per *Von baramundi aktualisieren*). Je Endpoint:
  - *Zuordnen* zu einem vorhandenen Gerät oder einer VM (nur wenn das Objekt keine andere Endpoint-ID hat; im
    Changelog sichtbar),
  - *Importieren* als neues Gerät (Standort, Rolle, Gerätetyp) oder als VM (Standort oder Cluster) – der Name ist mit
    dem Anzeigenamen vorbelegt, Seriennummer (Geräte), Betriebssystem und baramundi-Kommentar werden übernommen,
  - *Ignorieren* mit optionaler Notiz.

  Mehrere Endpoints lassen sich mit gemeinsamen Werten auf einmal importieren (*Auswahl importieren*); Endpoints, die
  sich nicht anlegen lassen (z. B. doppelter Name), werden übersprungen und aufgelistet.
- Berechtigungen: Die Übersichten brauchen Leserecht auf Geräte/VMs, *Auswahl abgleichen* braucht
  `netbox_baramundi.change_endpointlink`, die Orphan-Liste `view_unmatchedendpoint`, ihre Aktionen
  `change_unmatchedendpoint` und zusätzlich `change` (Zuordnen) bzw. `add` (Importieren) auf Geräte/VMs.
- **Dashboard-Widget** *baramundi*: letzter Endpoint-Abgleich (mit Status und Link auf den Job), Geräte und VMs mit
  Endpoint-ID (x von y, Fortschrittsbalken) und Anzahl offener baramundi-Orphans. Die Zahlen berücksichtigen die Rechte
  des Benutzers; kein bConnect-Aufruf. Bestehende Benutzer fügen es einmal über *Dashboard anpassen → Widget hinzufügen* hinzu.
- Karte *baramundi* auf Geräte-/VM-Seiten (Endpoint-ID) und Tab *baramundi* mit Live-Daten des Endpoints (Hostname, Betriebssystem, zuletzt gesehen; 5 Minuten gecacht). bConnect wird erst beim Öffnen des Tabs abgefragt.
- `netbox_baramundi.client.BConnect` für andere Plugins, z. B. das baramundi-Backend von
  [netbox-patch-management](https://github.com/carstenviell/netbox-patch-management)
  (Patch-Jobs starten, Job-Status, Windows-Update-Compliance)

## Voraussetzungen

- NetBox **4.7** oder neuer
- **baramundi bConnect API v2**

## Installation

Das Plugin liegt nicht auf PyPI. Installiert wird aus dem GitHub-Release-Archiv – das funktioniert ohne `git`,
auch im netbox-docker-Image. `v0.3.0` ggf. durch das gewünschte [Release](https://github.com/carstenviell/netbox-baramundi/releases) ersetzen.

**NetBox aus dem Quellcode (systemd):**

```bash
sudo /opt/netbox/venv/bin/pip install https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.3.0.tar.gz

# bleibt bei NetBox-Upgrades erhalten (upgrade.sh installiert local_requirements.txt neu)
echo "https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.3.0.tar.gz" | sudo tee -a /opt/netbox/local_requirements.txt
```

**netbox-docker:** in `plugin_requirements.txt`

```text
https://github.com/carstenviell/netbox-baramundi/archive/refs/tags/v0.3.0.tar.gz
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
`BARAMUNDI_`) für **beide** Dienste bereitstellen, Web und Worker (Docker: `env/netbox.env`).

**systemd:** zwei Wege, jeweils für `netbox` **und** `netbox-rq`.

*Variante A – direkt mit `systemctl edit`* (passt für Passwörter ohne Sonderzeichen):

```bash
sudo systemctl edit netbox
sudo systemctl edit netbox-rq
```

Im Editor jeweils zwischen die beiden Kommentarzeilen oben (`### Anything between here …` und
`### Lines below this comment …`) einfügen, speichern und schließen:

```ini
[Service]
Environment="BARAMUNDI_PASSWORD=<passwort>"
```

> **Stolperfalle:** In `Environment=` ist `%` ein systemd-Platzhalter und muss als `%%` geschrieben werden. Ein
> ungültiger (z. B. `%"`) lässt systemd die ganze Zeile stillschweigend verwerfen, das Plugin meldet dann
> *Umgebungsvariable BARAMUNDI_PASSWORD ist nicht gesetzt*. Die Abschnittsüberschrift muss genau `[Service]`
> lauten. Hinweis: `systemctl show` zeigt das Passwort jedem Benutzer an, auf geteilten Servern daher Variante B.

*Variante B – Umgebungsdatei* (empfohlen: beliebige Sonderzeichen, Datei nur für root lesbar):

```bash
printf '%s\n' 'BARAMUNDI_PASSWORD=<passwort>' | sudo tee /etc/netbox-baramundi.env >/dev/null
sudo chmod 600 /etc/netbox-baramundi.env
for u in netbox netbox-rq; do
  sudo mkdir -p /etc/systemd/system/$u.service.d
  printf '[Service]\nEnvironmentFile=/etc/netbox-baramundi.env\n' | sudo tee /etc/systemd/system/$u.service.d/baramundi.conf >/dev/null
done
```

*Danach (beide Varianten)* neu laden, neu starten und prüfen:

```bash
sudo systemctl daemon-reload
sudo systemctl restart netbox netbox-rq
sudo cat /proc/$(systemctl show -p MainPID --value netbox)/environ | tr '\0' '\n' | grep -c BARAMUNDI_   # muss 1 ausgeben
```

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
