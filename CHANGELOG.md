# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/), Versionen nach [SemVer](https://semver.org/lang/de/).

## [Unveröffentlicht]
### Offen
- Gegen den echten bMS verifizieren: Verbindungstest, Endpoint-Abgleich, Job-Zuweisung und `/Start`.
- Security-Audit (`SECURITY-ANALYSE-<Datum>.md`).

## [0.1.0] – 2026-11-22
### Neu
- Einstellungsseite für die bConnect-Verbindung (API v2, HTTP Basic Auth; Passwort nur über Umgebungsvariable) mit „Verbindung testen“ (Name/Version des Management-Servers).
- Client `BConnect` (Paging, Fehlerdetails, kein Retry bei schreibenden Aufrufen): Management-Server, Endpoints, Job-Definitionen, Job-Instanzen anlegen/starten/lesen, Windows-Update-Stand.
- Custom Field `baramundi_endpoint_id` an Devices/VMs, Endpoint-Abgleich (täglich und per Button), füllt nur leere Felder, meldet Mehrdeutigkeiten.
- Panel „baramundi“ auf Device-/VM-Seiten (live, gecacht).
- Deutsche Übersetzung.
