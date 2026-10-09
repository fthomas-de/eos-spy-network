# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-10-09.

## State

- Version: `0.0.2`, 2026-10-09 (see `CHANGELOG.md`): Corporation tiles and
  a page per Corporation with the mains that have markers (`markers.py`);
  the hostile list page is gone, `hostile_entities()` stays as the base of
  `hostile_index()`. Setting `corp_changes_per_year` (migration 0002).
- What the app does today: a settings page to choose the Alliance, the
  standing threshold, the Corporation changes per year and the contact
  sources; the Corporations of the Alliance as tiles; per Corporation the
  mains with markers: hostile membership (now and Corporation history),
  frequent Corporation changes, friendly/watched hostile contacts, mails,
  ISK, contracts - over the main and all its alts.
- Unreleased (committed, not pushed): Network tab (`network.py`): mains whose
  characters share an ISK partner outside the Alliance (>= 2 own characters,
  one payment each; donations, player trading, contract payments) or did
  player trading outside it, as a vis-network graph per main. Markers and
  connections are now computed by the task `update_snapshot` into the
  `Snapshot` row (migration 0003, `snapshot.py`, as in eos-auth-monitor);
  button *Recalculate*, footer with the calculation's cost. Corporations tab
  renamed Markers, with a switch hiding Corporations without markers. The
  footer's counts line carries the `eos-spy-network` context: eos-auth-monitor
  has the same msgid with another translation.
- Tests: 93 without translation tests plus 3 translation tests, all green
  in the dev instance; every new test checked against sabotaged code.
  `tests.base.SpyTestCase` patches `views.update_snapshot`, so no test
  queues a task into the dev worker.
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user yet.

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker; switch to hide clean ones |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found |
| Network | `view_suspects` + `view_evidence` | a tile per Corporation: mains with connections outside the Alliance |
| Network Corporation | `view_suspects` + `view_evidence` | per main a graph and a table of its connections |
| Settings | `manage_settings` | Alliance, threshold, Corporation changes per year, contact sources with aa-contacts' token state |

## Open

- Not tried in the browser yet (EVE SSO login): the tiles, the switch, the
  graph and the *Recalculate* button. Rendered server-side against `aa_dev`
  without errors: Ether Element shows E 'o with two watched hostiles at -5,
  and on Network E 'o and BigBlackout C both paying fenriscw1.
- Ask the user: does a shared payment partner need the main among the
  characters, or are two alts enough (implemented: any two)?
- Ask the user: watching a hostile is a marker (README decision), but PvP
  pilots watch enemies routinely - should a watched hostile with a negative
  standing stay a marker?
- Markers switchable and weighted, a score; account page with evidence
  (`view_evidence`: mail headers and subjects, wallet entries, contracts);
  review per suspect: status (new, seen, harmless, watch, confirmed), note,
  history; a harmless one comes back only with new signals.
- More markers: clones/assets in staging systems (needs a setting for the
  systems), owner changes, audit gaps as data gap.
- Measure the calculation on prod-sized wallet journals (footer shows it).
- The settings page help text still says "hostile list" ("Tick whose
  contacts make up the hostile list ...").
- Check the release against https://github.com/fthomas-de/aa-app-checklist.

## Decisions

- Purpose: detect suspected spies (not run an own spy network, not an intel
  board).
- Start page: a tile per Corporation of the Alliance; a click opens the
  Corporation page listing only the mains with markers. No plain hostile
  list page.
- Hostile = contact of a ticked source (Alliance and/or its Corporations,
  ticked in a searchable table) with a standing below a configurable value,
  default below 0. One negative source is enough. The Alliance and its own
  Corporations never count.
- No ESI call at all, not even an affiliation lookup: a counterpart is
  hostile only when it is a hostile contact itself or a member Auth knows
  (`EveCharacter`, `EveCorporationInfo`); corptools' `EveName` has no
  affiliation. Contacts come from aa-contacts; no task of our own.
- Mails: headers and subject, never the body.
- Review with status, note and history.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 and 0002
  applied to `aa_dev`, `collectstatic` run.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815); first read 2026-10-09 by hand (159 Alliance, 54
  Corporation contacts). No `celery beat` runs in the dev instance, so no
  periodic task fires on its own.
- The periodic task row `contacts` (id 7, every 15 minutes) is disabled; the
  `CELERYBEAT_SCHEDULE` entry in `local.py` (hourly) is the one to keep.
- The Celery worker started at 12:03 without aa-contacts was stopped; the
  one in the user's terminal remains.

## Traps

- A Celery worker started before an app joined `INSTALLED_APPS` drops that
  app's tasks as "unregistered", and celery_once keeps their lock for an
  hour: restart every worker, and clear the `qo_` keys of dropped tasks.
- Under the "EVE jargon" context Alliance Auth shows "Mains", "Characters"
  and "Corporations" as the singular in ru and zh_Hans; our plurals carry
  the `eos-spy-network` context. "View details" takes AA's German wording.
- Test IDs like 98000001 make tickers too long for MySQL; `tests.base.ticker`
  cuts them to five characters.
- A leftover `.git/CLAUDE_COMMIT_MSG` makes the Write tool refuse until the
  file is read - and `git commit -F` then takes the old message.
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
