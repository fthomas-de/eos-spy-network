# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-10-09.

## State

- Version: `0.0.5`, 2026-10-09 (see `CHANGELOG.md`): network keeps only
  hostile partners (`network.hostile_only`, after `affiliate` in
  `snapshot.build`); the graph draws Corporation/Alliance only up to the
  reason (the Corporation stays between partner and a hostile Alliance),
  the rest in the partner's tooltip (`affiliation`); periods (first/last
  payment, ISO dates) per link in table and line tooltip; ISK and contract
  markers carry `rows` per own character and hostile (count, ISK, period,
  kinds, `partials/dealings.html`), Corporation changes the Corporations
  joined (`<abbr>` tooltip); graph layout: wider columns, repulsion run then
  frozen, height by the fullest column, payment count only in the tooltip.
- Before (0.0.4): counterparts followed to Corporation and Alliance
  (`affiliations.py`: Auth, corptools, then public ESI in the task); mains
  listed first, graph and table on click (`#main-<id>`); progress bar
  (`progress.py`, polled at `rebuild/progress/`).
- A snapshot of 0.0.4 or older has no periods and marker rows; `Report`
  reads it anyway, the next recalculation fills them.
- What the app does today: a settings page (Alliance, standing threshold,
  Corporation changes per year, contact sources); Markers: the Corporations
  as tiles, per Corporation the mains with markers (hostile membership now
  and in the history, frequent Corporation changes, friendly/watched hostile
  contacts, mails, ISK, contracts - over main and alts); Network: the ISK
  connections with hostile partners. Pages read only the stored snapshot.
- Tests: 126 without translation tests plus 3 translation tests, all green
  in the dev instance; every new test checked against sabotaged code.
  `tests.base.SpyTestCase` patches `views.update_snapshot` and the three
  ESI calls of `affiliations.py` (`self.esi_names`, `self.esi_affiliations`,
  `self.esi_corporation_alliance`; set `return_value` for an answer).
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user yet.

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker; switch to hide clean ones |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found |
| Network | `view_suspects` + `view_evidence` | a tile per Corporation: mains with connections to hostile partners |
| Network Corporation | `view_suspects` + `view_evidence` | the mains; on click a graph (partner, up to the reason) and a table of the connections with periods |
| Settings | `manage_settings` | Alliance, threshold, Corporation changes per year, contact sources with aa-contacts' token state |

## Open

- Not tried in the real app in the browser yet (EVE SSO login): tiles,
  switches, click-to-show graph, progress bar, the new dealings tables and
  the Corporation-change tooltips. The graph layout was checked only with a
  synthetic 14-partner graph served as a static page (labels no longer
  overlap; lines still cross labels in a dense graph). `aa_dev` has no
  hostile network partner and no ISK/contract marker, so the network pages
  there are empty since 0.0.5 (fenriscw1 is not hostile); rendered
  server-side without errors.
- Ask the user: should the payment count come back on the graph lines (moved
  to the tooltip for less overlap)?
- Ask the user (asked at the end of the session, no answer yet): does a
  shared payment partner need the main among the characters, or are two
  alts enough (implemented: any two)?
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
- Network hostile-only (2026-10-09): shared partner and player trading
  count only with a hostile partner (itself, its Corporation or Alliance).
- Network (2026-10-09): payments are donations, player trading and
  contract payments; one payment per character is enough, it is the overlap
  of two own characters that counts; player trading shows on its own. A
  counterpart Auth does not know counts as outside; NPCs never. The graph
  is vis-network from cdnjs. The pages need `view_evidence` as well.
- Recalculation: stored in the database by a Celery task (not a cache, not
  live), started by the button, by saving the settings, or by a
  `CELERYBEAT_SCHEDULE` entry the admin adds (README).
- ESI (changed 2026-10-09): the markers make no ESI call - a counterpart
  there is hostile only as a hostile contact itself or a member Auth knows.
  The network task looks up each counterpart's Corporation and Alliance:
  Auth and corptools first, ESI's public endpoints only for the rest
  (`affiliations.py`). corptools' `EveName` has the fields but leaves them
  empty (0 of 1393 in `aa_dev`). Contacts come from aa-contacts.
- Network graph (2026-10-09): the chain goes counterpart -> Corporation ->
  Alliance; the hostile one is the reason node, labelled with its standing.
  Own side green (main darker, alts lighter), hostiles red, others neutral;
  columns left to right. The Corporation page lists the mains, graph and
  table only after a click. The switch on the tiles hides Corporations
  without connections.
- Progress: the task writes its step into the cache (`progress.py`), the
  pages poll `rebuild/progress/` and reload when it is gone.
- Mails: headers and subject, never the body.
- Review with status, note and history.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 to 0003
  applied to `aa_dev`, `collectstatic` run. A snapshot was built once by
  hand (`snapshot.update()` in the shell); no `CELERYBEAT_SCHEDULE` entry
  for it in `local.py`.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815); first read 2026-10-09 by hand (159 Alliance, 54
  Corporation contacts). No `celery beat` runs in the dev instance, so no
  periodic task fires on its own.
- The periodic task row `contacts` (id 7, every 15 minutes) is disabled; the
  `CELERYBEAT_SCHEDULE` entry in `local.py` (hourly) is the one to keep.
- The Celery worker was restarted 2026-10-09 15:00 in a terminal tab of the
  Claude session (`celery -A myauth worker -l info -P solo`) and lists
  `eos_spy_network.tasks.update_snapshot`; it stops with that session. A
  snapshot of 0.0.4 was built by hand (`snapshot.update()`).

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
  new clash of that kind. Same for the footer's "... Corporations, ...
  accounts, ... characters" (eos-auth-monitor has that msgid).
- The dev server answers only on `127.0.0.1:8000`, not `localhost`
  (DisallowedHost), and needs EVE SSO: render pages for a check through
  `django.test.Client` with `force_login` in `manage.py shell`.
- `sri_static` of a new static file fails in tests with "Missing
  staticfiles manifest entry" until `collectstatic` ran.
- Every patch script of a session has to leave the repo: a `patch_*.py` in
  the repo root would land in `git status` and the next commit.
- An assertion on the URL `/eos_spy_network/rebuild/` also matches
  `rebuild/progress/`; assert on `action="..."` instead.
