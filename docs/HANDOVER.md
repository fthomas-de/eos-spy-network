# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-11-06.

## State

- Version: `0.0.15`, 2026-11-06 (see `CHANGELOG.md`): blue kills
  reviewed per main and killmail (user): one row, one note, one tick;
  `snapshot.reviewed_kills` merges the rows of one killmail inside the
  main's marker, `views._kill_rows` groups by killmail and owner
  (`CharacterOwnership`), `views.kill_note` updates every `BlueKill` row of
  the killmail whose character belongs to the posted character's main (no
  migration). The tick is a checkbox column (`kill-note-button.html`
  renders the two cells *Cleared* and *Note*; `kills.js`: ticking without
  a note opens the popup with the tick set). Seen as rendered HTML for the
  seeded kills in `aa_dev` (Ether Element: 3 rows), not clicked in a
  browser.
- Before (0.0.14): note and *Cleared*
  tick per blue kill row (`BlueKill.note/cleared/reviewed_at/reviewed_by`,
  migration 0007, applied to `aa_dev`; endpoint `views.kill_note`,
  `kills/note/`, `view_suspects`; Cleared only with a note, popup
  `partials/kill-note-modal.html` + `kill-note-button.html`, `kills.js`:
  reloads on the Corporation page, updates the row in place in the
  settings tab). Applied at read time (`snapshot.kill_reviews` +
  `reviewed_kills`, in `views._report` and `api.character_markers`, which
  now takes a third query when the snapshot holds blue kills). New
  settings tab *Blue kills* (`views._kill_rows`, every `BlueKill` of the
  Alliance, no time frame, DataTables via `tables.js`).
- Before (0.0.13): new marker *Blue
  kills* (`markers.BLUE_KILLS`, last in `KINDS`, so also in `api.KINDS` -
  eos-auth-monitor shows it like the others; not tried there). A character
  among the attackers of a killmail whose victim is in the Alliance
  (*Awox*) or blue: the victim, its Corporation or Alliance among the
  **Alliance's own** aa-contacts contacts with standing >=
  `SpyConfiguration.blue_from` (default 5; `hostiles.blue_entities`,
  `contacts.contacts(at_least=...)`). Killmails from killtracker's
  `EveKillmail`/`EveKillmailAttacker` (`killmails.py`, optional behind
  `apps.is_installed("killtracker")`). Each calculation copies them into the
  own table `BlueKill` (`markers._copy_kills`, upsert: names follow
  killtracker, reason and standing frozen at the first copy), the marker
  reads `BlueKill` by Alliance, own characters and time frame - killtracker
  purges after 30 days by default. One marker, a row per own character and
  killmail (zKB link, victim, Corporation, Alliance, ship, reason), counted
  once per killmail per account; runs even without hostiles (step
  `kills`); not evidence. Notice on the marker pages when killtracker is
  missing or does not store (`views._killmails_missing`). Migration 0006
  (`blue_from` + `BlueKill`).
- Before (0.0.12): ISK marker rows with contract payments have a *View
  details* popup (`views.contracts`, `contract_details.details`, live from
  corptools, `contracts.js`); only the ISK rows, not yet the *Contracts
  with hostiles* rows (same view). (0.0.11) the contacts marker counts only
  a standing above 0. (0.0.10) every marker stores `character_ids`; `api.py`
  for eos-auth-monitor: `character_markers() -> dict[int, list[str]]`
  (KINDS order, `{}` without snapshot or for another Alliance, switched-off
  markers left out, two queries - three with blue kills since 0.0.14), `label`, `description`, `KINDS` -
  a stable contract, change it only together with eos-auth-monitor.
  (0.0.9) settings tabs and marker switches (`disabled_markers`, hide only);
  (0.0.8) corptools read by CharacterAudit ID, `test_network.TestQueries`
  pins the SQL; (0.0.6) time frame and ignored wallet types; (0.0.5)
  network only with hostile partners; (0.0.4) affiliations, progress bar.
- What the app does today: settings (Alliance, hostile threshold, blue
  threshold, Corporation changes per year, time frame, ignored wallet entry
  types; contact sources; marker switches; every stored blue kill with
  note and Cleared tick); Markers: the Corporations as
  tiles, per Corporation the mains with markers (hostile membership now and
  in the history, frequent Corporation changes, friendly hostile contacts,
  mails, ISK, contracts, blue kills - over main and alts); Network: the ISK
  connections with hostile partners. Pages read only the stored snapshot.
- Tests: 237 without translation tests plus 3 translation tests, all green
  in the dev instance (0.0.15 added 6 in `test_kill_reviews.py`,
  `TestPerMainAndKillmail`); every new test
  checked against sabotaged code. `tests.base.SpyTestCase` patches
  `views.update_snapshot` and the three ESI calls of `affiliations.py`.
  `testauth` has `eveuniverse` and `killtracker` installed for the tests.
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user (0.0.13 added the blue kill texts, 0.0.14 the
  note texts; Awox and Blue stay English; "Cleared" carries the
  `eos-spy-network` context - another app translates it differently in ru).

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker; switch to hide clean ones |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found; blue kills as a table with zKB links, note and Cleared tick |
| Network | `view_suspects` + `view_evidence` | a tile per Corporation: mains with connections to hostile partners |
| Network Corporation | `view_suspects` + `view_evidence` | the mains; on click a graph (partner, up to the reason) and a table of the connections with periods |
| Settings | `manage_settings` | tabs: Alliance (hostile and blue threshold, Corporation changes per year, time frame, ignored wallet types), Contact sources with aa-contacts' token state, Markers (switch per marker), Blue kills (all stored, note editable with `view_suspects`) |

## Open

- eos-auth-monitor: check that a character whose blue kills are all
  cleared loses its problem there (only tested on this side, `test_api`).
- Note and *Cleared* per finding, marker by marker (user, 2026-11-06).
  Built (unreleased, under `[Unreleased]`): *Friendly to hostiles* - model
  `FindingReview` (alliance, kind, **main_id**, key; migration 0008,
  applied to `aa_dev`), endpoint `views.finding_note` (`findings/note/`,
  `REVIEWED_KINDS`), applied at read time by `snapshot.finding_reviews` +
  `reviewed_contacts` (pages and `api.py`); key `<contact ID>:<standing>`;
  popup and `kills.js` shared with the blue kills (a button with
  `data-...-kill-key` posts to the finding URL). Tests:
  `test_finding_reviews.py` (18, checked against sabotage). Snapshot in
  `aa_dev` rebuilt 2026-11-06 with this code, but `aa_dev` has no contacts
  marker: not seen in a browser; seeding a corptools `CharacterContact`
  needs the user's yes.
  Decided (user): a review belongs to the **main** + finding, so a later
  alt with the same finding is cleared too; a different finding (other
  standing, new payment/mail/join) is **always a separate row** (option
  (a), not reopening) - for the dated markers the calculation has to split
  the rows at the review time. Next markers: Membership, Corporation
  changes, Mails/ISK/Contracts (mails need rows; with `view_evidence`).
  Translations of the new texts ("Contact", the modal's "cleared finding"
  sentence) come at `/commit`.
- Blue kills not clicked in the browser yet (checkbox, popup, settings
  tab). `aa_dev` holds 4 `BlueKill` rows with fake killmail IDs
  99000000101-103 (Ether Element, test seed of unknown origin, not in
  killtracker; a recalculation keeps them, `BlueKill` is never pruned);
  killtracker itself stores 0 there - its periodic task needs `celery
  beat`, which does not run in dev. Prod: check that it stores, and that
  the snapshot task runs well within the purge (README: every 4 hours).
- Not decided, left as built: a `BlueKill` copy is never deleted (few
  rows; the time frame hides old ones); after a change of the Alliance the
  old Alliance's copies stay unused.
- The contract popup was not seen in a browser: `aa_dev` holds no ISK
  marker, so only the tests rendered it. Seeding a `contract_price` journal
  entry plus a `Contract` in aa_dev needs the user's yes (foreign tables).

- Not tried in the real app in the browser yet (EVE SSO login): the
  settings tabs (column widths of the source table in its initially
  hidden tab), the marker switches, tiles,
  switches, click-to-show graph, progress bar, the dealings tables with
  their Corporation/Alliance columns, the multi-select of ignored wallet
  types and the Corporation-change tooltips. `aa_dev` has no ISK or
  contract marker, so the new columns were only seen in tests.
- The translations (0.0.6: time frame, ignored wallet entry types; 0.0.7:
  the contacts marker description) are machine-made like the rest; not
  reviewed by the user. The graph layout was checked only with a
  synthetic 14-partner graph served as a static page, before the payment
  counts came back on the lines (the user accepts the overlap).
- The stored snapshot in `aa_dev` was rebuilt 2026-11-04 with the
  0.0.10 code (1.44 s): no main has a marker any
  more (the 0.0.7 contacts change dropped the old ones), so
  `api.character_markers()` gives `{}` there; the character IDs were only
  seen in tests.
- `aa_dev` has no hostile network partner and no ISK/contract marker, so the network pages
  there are empty since 0.0.5 (fenriscw1 is not hostile); rendered
  server-side without errors.
- Markers weighted, a score; account page with evidence
  (`view_evidence`: mail headers and subjects, wallet entries, contracts).
- More markers: clones/assets in staging systems (needs a setting for the
  systems), owner changes, audit gaps as data gap.
- Measure the calculation on prod-sized wallet journals (footer shows it).
  `aa_dev` holds 6 journal entries, 0 mails, 1 contract: its EXPLAIN plans
  say nothing about prod. Left as is after the 0.0.8 review: the network
  still reads every payment in the time frame, inside the Alliance too
  (dropped in Python - hard to express in SQL); mails and contracts have no
  date index in corptools, so the time frame filters rows after the
  character index; the hostile ID lists go into SQL as long `IN` lists
  (fine for MySQL).
- `aa_dev`: the configured Alliance holds 30 Corporations `T000`-`T029`
  without mains, apparently leftover seed data of another app; untouched,
  ask the user before removing anything.
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
- Shared partner (user, 2026-10-09): any two own characters, two alts
  without the main are enough; the graph always draws the main with them.
  The payment count stands on the lines again (user: overlap does not
  matter).
- Contacts (user, 2026-11-04): only a standing above 0 counts, watched or
  not; the 2026-10-09 rule (watched at 0 or above counts) is gone, a
  neutral contact is no friendship.
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
- Time frame (2026-10-09): "last N days" in the settings, not fixed dates;
  it limits mails, ISK, contracts, network payments and the Corporation
  history, because standings change and the hostile list is today's.
- Ignored wallet types (2026-10-09): one list for the ISK marker and the
  network; default `market_transaction` (the user's example).
- Corporation/Alliance of ISK and contract counterparts (2026-10-09): from
  the same lookup as the network (Auth, corptools, then public ESI in the
  task); whether a counterpart is hostile is still decided without ESI.
- Marker switches (user, 2026-11-04): a switched-off marker is hidden,
  not skipped - it takes effect at once and back on without a
  recalculation; the tab is called *Markers*; the settings stay one page
  with one form in tabs.
- Characters per marker (user, 2026-11-04): eos-spy-network stores the
  characters, eos-auth-monitor shows them (display only, no problem
  counts) through `api.py`, which leaves switched-off markers out like
  the pages; its own tests live in `tests/test_api.py`.
- Blue kills (user, 2026-11-06): one marker for awox and blue; every own
  attacker counts, not only the final blow; blue = the configured
  Alliance's own contacts only (not the ticked Corporation sources), from a
  standing of 5 by default, adjustable; killmails from killtracker's
  storage, copied into `BlueKill` so a kill survives killtracker's purge.
- Blue kill review (user, 2026-11-06): the `BlueKill` row is the snapshot
  of the time found - reason and standing stay when the victim is no longer
  blue. Note and *Cleared* per row (character + killmail), not per
  killmail; editable with `view_suspects` on the Corporation page and in
  the settings tab; clearing needs a note (user); a cleared kill no longer counts (pages and API) but
  stays greyed in the table; at once, no recalculation. Changed
  (user, 2026-11-06): one row, note and tick per main and killmail, the
  main's characters together; two mains on one killmail, a row each. The settings tab
  lists every kill of the Alliance regardless of the time frame, client-side
  DataTables.
- Mails: headers and subject, never the body.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 to 0007
  applied to `aa_dev`, `collectstatic` run. The snapshot was rebuilt by
  hand with 0.0.10, not since the 0.0.11 contacts change (`snapshot.update()` in the shell; time frame 365,
  ignored `market_transaction`); no `CELERYBEAT_SCHEDULE` entry for it in
  `local.py`.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815); first read 2026-10-09 by hand (159 Alliance, 54
  Corporation contacts). No `celery beat` runs in the dev instance, so no
  periodic task fires on its own.
- The periodic task row `contacts` (id 7, every 15 minutes) is disabled; the
  `CELERYBEAT_SCHEDULE` entry in `local.py` (hourly) is the one to keep.
- The Celery worker last started 2026-10-09 17:55 with the 0.0.6 code in a
  background shell of an earlier Claude session (`celery -A myauth worker
  -l info -P solo`); it stops with that session and does not know the
  code since 0.0.7 - check `pgrep -af celery` and start it again before
  testing the button. `collectstatic` ran with the 0.0.7 `network.js`.

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
- `bulk_create(update_conflicts=True)`: MySQL refuses `unique_fields`,
  sqlite requires them - `markers._copy_kills` asks
  `connection.features.supports_update_conflicts_with_target`.
- After regenerating an unreleased migration, the kept test database still
  has the old one: run `aa-test ... --fresh` once.
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
- `django.test.Client()` in `manage.py shell` gets 400 (host `testserver`)
  and a superuser without a main is redirected: use
  `Client(HTTP_HOST="127.0.0.1:8000")` and a user with
  `profile.main_character`.
- `wsl.exe ... bash -lc '... | grep ...'` from the PowerShell tool breaks
  the pipes; run such lines through the Bash tool.
- Restoring a file with `shutil.copy2` from a backup on `/mnt/c` carries
  the Windows mode along (100644 -> 100755, shows in `git diff
  --summary`); `chmod 644` afterwards, or write the text back instead.
- Inheriting a test class to borrow a helper runs all its tests twice;
  assign the helper instead (`add_entry = TestWallet.add_entry`).
- Another app's suite running at the same time (eos-auth-monitor) shares
  `test_aa_dev` and breaks the run with "table already exists": set
  `EOS_TEST_DB=test_spy_net` for your own test database. `aa-test` ends
  with "xport: command not found" noise (its lines 52-53); results are fine.
