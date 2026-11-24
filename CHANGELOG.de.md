[English](CHANGELOG.md) | **Deutsch**

# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [SemVer](https://semver.org/lang/de/).

## [Unveröffentlicht]
### Offen
- Gegen den echten bMS verifizieren: Job-Zuweisung und `/Start` (Verbindungstest, Endpoint-Abgleich, Sync-Übersicht und Orphans am 2026-11-24 bestätigt).

## [0.3.0] – 2026-11-24
### Neu
- Dashboard-Widget *baramundi*: letzter Endpoint-Abgleich (Status, Link auf den Job), Geräte und VMs mit Endpoint-ID (x von y) und offene baramundi-Orphans. Die Zahlen berücksichtigen die Rechte; kein bConnect-Aufruf.

## [0.2.0] – 2026-11-24
### Neu
- Sync-Übersicht für Geräte und für virtuelle Maschinen: Endpoint-ID, Status mit Grund (per Name zugeordnet, manuell zugeordnet, importiert, nicht gefunden, mehrdeutig mit Kandidaten-IDs, veraltet), letzte Prüfung, Statusfilter und *Auswahl mit baramundi abgleichen*.
- baramundi-Orphans: Endpoints ohne NetBox-Objekt, mit *Zuordnen* (vorhandenes Gerät/VM), *Importieren* (neues Gerät oder neue VM inkl. Seriennummer, Betriebssystem, Kommentar), Massenimport mit gemeinsamen Werten und *Ignorieren*.
- Neue Berechtigungen `change_endpointlink` und `view`/`change_unmatchedendpoint` (Migration `0003`).

### Geändert
- Der Endpoint-Abgleich vergibt keine Endpoint-ID mehr, die schon an einem anderen Objekt steht, und markiert Objekte, deren Endpoint in baramundi nicht mehr existiert, als *veraltet* (das Feld selbst bleibt unverändert).

## [0.1.5] – 2026-11-24
### Geändert
- README: Passwort unter systemd mit beiden Wegen beschrieben – direkt per `systemctl edit` (`Environment=`, `%` als `%%`) und per Umgebungsdatei –, danach ein gemeinsamer Schritt zum Neuladen und Prüfen.

## [0.1.4] – 2026-11-24
### Geändert
- README: Passwort unter systemd per `EnvironmentFile=` statt `Environment=` einrichten, mit Hinweis auf `%`-Platzhalter (ein ungültiger lässt systemd die Zeile stillschweigend verwerfen).
- Geräte-/VM-Seiten: Statt des Bereichs unter der Rack-Ansicht gibt es eine kompakte Karte in der linken Spalte und einen Tab *baramundi* (nur mit Endpoint-ID). Die Detailseite fragt bConnect nicht mehr ab, das geschieht erst beim Öffnen des Tabs.

## [0.1.3] – 2026-11-22
### Geändert
- Auf GitHub veröffentlicht; Installation aus dem GitHub-Release-Archiv (`…/archive/refs/tags/v0.1.3.tar.gz`) statt aus lokalem Ordner bzw. Paket.
- Dokumentation zweisprachig: `README.md`/`README.de.md`, `CHANGELOG.md`/`CHANGELOG.de.md`.

## [0.1.2] – 2026-11-22
### Behoben
- Installationsanleitung: Installation aus dem lokalen Ordner (nicht auf PyPI/GitHub) für Source-Installation und netbox-docker, Passwort-Variable für Web **und** Worker, Neustart des Workers.
- Kompilierte deutsche Übersetzung (`django.mo`) wird mitgeliefert (ohne `gettext` auf dem Zielsystem blieb die Oberfläche englisch).

## [0.1.1] – 2026-11-22
### Sicherheit
Ergebnis des Security-Audits vom 2026-11-22 (Bericht lokal, nicht im Repo):
- Server-URL nur noch `https://` (Basic Auth nie im Klartext), Passwort-Variable muss mit `BARAMUNDI_` beginnen – vorher hätte die Einstellungsseite beliebige Prozess-Secrets an einen beliebigen Host senden können. Prüfung beim Speichern und beim Verbindungsaufbau.
- Endpoint-ID wird vor jeder Verwendung als GUID geprüft (Feld-Regex wirkt nur in Formularen; ein per API gesetzter Wert konnte den Request-Pfad verändern).
- Einstellungen und Verbindungstest nur für Superuser.
- Panel: Timeout max. 5 s, Fehler 60 s gecacht (Seiten hängen nicht, wenn der bMS nicht erreichbar ist).
- Endpoint-Abgleich protokolliert jede automatische Zuordnung im Job-Log.

## [0.1.0] – 2026-11-22
### Neu
- Einstellungsseite für die bConnect-Verbindung (API v2, HTTP Basic Auth; Passwort nur über Umgebungsvariable) mit „Verbindung testen“ (Name/Version des Management-Servers).
- Client `BConnect` (Paging, Fehlerdetails, kein Retry bei schreibenden Aufrufen): Management-Server, Endpoints, Job-Definitionen, Job-Instanzen anlegen/starten/lesen, Windows-Update-Stand.
- Custom Field `baramundi_endpoint_id` an Devices/VMs, Endpoint-Abgleich (täglich und per Button), füllt nur leere Felder, meldet Mehrdeutigkeiten.
- Panel „baramundi“ auf Device-/VM-Seiten (live, gecacht).
- Deutsche Übersetzung.
