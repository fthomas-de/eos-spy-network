# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.0.2] - 2026-10-09

### Added

- Corporations page: a tile per Corporation of the Alliance with its mains,
  how many have markers and per marker how many; a page per Corporation
  with every main that has a marker and what was found
- Markers per account, over the main and all its alts, from corptools:
  hostile membership now or in the Corporation history, frequent
  Corporation changes, friendly or watched hostile contacts, mails, ISK and
  contracts with hostiles. The counterparts of mails, ISK and contracts are
  evidence and need `view_evidence`
- A hostile Corporation or Alliance makes its members hostile as far as
  Auth knows them; no ESI call, corptools stores no affiliation
- Setting for the number of Corporation changes per year that sets a marker
  (migration 0002)

### Changed

- The Corporations page replaces the hostile list as the start page: a plain
  list of negative contacts told nobody which member to look at. The
  hostiles are now only the base of the markers
- `view_suspects` reads "Can view the suspects per Corporation"

## [0.0.1] - 2026-10-09

### Added

- Package skeleton after eos-auth-monitor: hatchling, permissions
  `view_suspects`, `view_evidence` and `manage_settings`, a django-solo
  configuration, standalone test project `testauth`, `tools/translate.py`
  and `tools/glossary.py`
- Settings page: the Alliance, the standing below which a contact is
  hostile, and a searchable table of the Alliance and its Corporations to
  tick as contact sources, with aa-contacts' token, the time of its contacts
  and the counts per source
- Hostile list: every contact of a ticked source below the threshold, read
  from aa-contacts (optional, no ESI call of our own), merged across
  sources, without the Alliance itself and its Corporations
