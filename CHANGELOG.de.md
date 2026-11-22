[English](CHANGELOG.md) | **Deutsch**

# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [SemVer](https://semver.org/lang/de/).

## [Unveröffentlicht]
### Offen
- Gegen den echten bMS verifizieren: Verbindungstest, Endpoint-Abgleich, Job-Zuweisung und `/Start`.

### Geändert
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
