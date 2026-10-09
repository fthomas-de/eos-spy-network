# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-10-09.

## State

- Version: `0.0.1`, 2026-10-09 - the first release (see `CHANGELOG.md`):
  package skeleton, settings page, hostile list from aa-contacts.
- Uncommitted since 0.0.1: Corporation tiles and a page per Corporation
  with the mains that have markers (`markers.py`); the hostile list page is
  gone, `hostile_entities()` stays as the base of `hostile_index()`.
  Migration 0002 (`corp_changes_per_year`, permission text) applied to
  `aa_dev`. New messages are not in `tools/glossary.py` yet - that happens
  at `/commit`; the translation test now looks for "Mains with markers".
- What the app does today: a settings page to choose the Alliance, the
  standing threshold, the Corporation changes per year and the contact
  sources; the Corporations of the Alliance as tiles; per Corporation the
  mains with markers: hostile membership, frequent Corporation changes,
  friendly/watched hostile contacts, mails, ISK, contracts.
- Tests: 60 in the affected modules green; every new test checked against
  sabotaged code. The whole suite and the standalone run (`runtests.py`,
  now with `corptools` and `eve_sde` in `testauth`) not run yet.
- Translations: de, ru, zh_Hans, machine-generated, 37 messages in
  `tools/glossary.py`; not reviewed by the user yet.

| Page | Permission | What |
|---|---|---|
| Corporations | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found |
| Settings | `manage_settings` | Alliance, threshold, Corporation changes per year, contact sources with aa-contacts' token state |

## Open

- Not tried in the browser yet: the Corporations tiles and a Corporation
  page. On `aa_dev`, Ether Element shows E 'o with two watched hostiles at -5.
- Watching a hostile is a marker (README decision), but PvP pilots watch
  enemies routinely - ask the user whether watched hostiles with a negative
  standing should stay a marker.
- Markers switchable and weighted, a score; account page with evidence
  (`view_evidence`: mail headers and subjects, wallet entries, contracts);
  review per suspect: status (new, seen, harmless, watch, confirmed), note,
  history; a harmless one comes back only with new signals.
- More markers: clones/assets in staging systems, owner changes, audit gaps
  as data gap.
- The markers are computed on every page view, over the whole Alliance for
  the tiles. Fine for the dev data; measure on prod-sized wallet journals
  before release.
- Check the release against https://github.com/fthomas-de/aa-app-checklist.
- Staging systems for the clone/asset signal need a setting of their own.

## Decisions

- 2026-10-09: the start page is a tile per Corporation of the Alliance; a
  click opens the Corporation page listing only the mains with markers. The
  plain hostile list page is removed.
- 2026-10-09: first markers: hostile membership (now and history), frequent
  Corporation changes, contacts, mails, ISK, contracts.
- 2026-10-09: no ESI affiliation lookup. A counterpart is hostile only when
  it is a hostile contact itself or a member Auth knows (`EveCharacter`,
  `EveCorporationInfo`); corptools' `EveName` has no affiliation.

- Purpose: detect suspected spies (not run an own spy network, not an intel
  board).
- Hostile = contact of a ticked source (Alliance and/or its Corporations,
  ticked in a searchable table) with a standing below a configurable value,
  default below 0. One negative source is enough. The Alliance and its own
  Corporations never count.
- Contacts come from aa-contacts, which runs in the dev and the prod
  instance; no ESI call and no task of our own. The first version fetched
  them itself - dropped before any commit.
- Mails: headers and subject, never the body.
- Review with status, note and history.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migration 0001 applied to
  `aa_dev`, `collectstatic` run.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815), added 2026-10-09; first read 2026-10-09 by hand
  (159 Alliance, 54 Corporation contacts). No `celery beat` runs in the dev
  instance, so no periodic task fires on its own.
- The periodic task row `contacts` (id 7, every 15 minutes) is disabled; the
  `CELERYBEAT_SCHEDULE` entry in `local.py` (hourly) is the one to keep.

## Traps

- A Celery worker started before an app joined `INSTALLED_APPS` drops that
  app's tasks as "unregistered", and celery_once keeps their lock for an
  hour: restart every worker, and clear the `qo_` keys of dropped tasks.

- corptools' `CorporationContact` model is never filled by corptools - do
  not read it as if it were; aa-contacts has the contacts.
- aa-contacts keeps a contact that left ESI but has notes, with standing 0.
- DataTables takes rows of other pages and rows hidden by the search out of
  the page; checkboxes there would not be posted. The source table therefore
  has no pages, and `tables.js` clears the search before the form is sent.
- `user_passes_test` sends a user without permission to the login page with
  `?next=/eos_spy_network/...`; assert on the login URL, not on the app name.
- GitHub's Python `.gitignore` ignored `*.mo`; the line is gone, the compiled
  catalogues are committed. Check `git status` shows them after a
  translation run.
- Another installed app translates "Standing" and "Hostile" differently;
  both carry the `eos-spy-network` context. `tools/translate.py` names every
  new clash of that kind.
