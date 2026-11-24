**English** | [Deutsch](CHANGELOG.de.md)

# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [SemVer](https://semver.org/).

## [Unreleased]
### Open
- Verify against a real bMS: connection test, endpoint sync, job assignment and `/Start`.

## [0.1.4] – 2026-11-24
### Changed
- README: systemd setup of the password via `EnvironmentFile=` instead of `Environment=`, with a warning about `%` placeholders (an invalid one makes systemd drop the line silently).
- Device/VM pages: the panel below the rack elevations is replaced by a compact card in the left column and a *baramundi* tab (shown only with an endpoint ID). The device page no longer calls bConnect; the live query runs only when the tab is opened.

## [0.1.3] – 2026-11-22
### Changed
- Published on GitHub; installation from the GitHub release archive (`…/archive/refs/tags/v0.1.3.tar.gz`) instead of a local folder or package.
- Documentation in two languages: `README.md`/`README.de.md`, `CHANGELOG.md`/`CHANGELOG.de.md`.

## [0.1.2] – 2026-11-22
### Fixed
- Installation guide: installation from the local folder (not on PyPI/GitHub) for source installation and netbox-docker, password variable for web **and** worker, worker restart.
- The compiled German translation (`django.mo`) is shipped (without `gettext` on the target system the UI stayed English).

## [0.1.1] – 2026-11-22
### Security
Result of the security audit of 2026-11-22 (report kept locally, not in the repository):
- Server URL only `https://` (basic auth never in plain text), the password variable must start with `BARAMUNDI_` – before, the settings page could have sent any process secret to any host. Checked when saving and when connecting.
- The endpoint ID is validated as GUID before every use (the field regex only applies in forms; a value set via API could change the request path).
- Settings and connection test for superusers only.
- Panel: timeout max. 5 s, errors cached for 60 s (pages do not hang when the bMS is unreachable).
- The endpoint sync logs every automatic assignment in the job log.

## [0.1.0] – 2026-11-22
### Added
- Settings page for the bConnect connection (API v2, HTTP basic auth; password only via environment variable) with "Test connection" (name/version of the management server).
- Client `BConnect` (paging, error details, no retry for write calls): management server, endpoints, job definitions, create/start/read job instances, Windows update state.
- Custom field `baramundi_endpoint_id` on devices/VMs, endpoint sync (daily and via button), fills only empty fields, reports ambiguities.
- Panel "baramundi" on device/VM pages (live, cached).
- German translation.
