# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-11-13 (0.0.26).

## State

- Version: `0.0.26`, 2026-11-13 (see `CHANGELOG.md`):
  - Note buttons: `SpyConfiguration.note_presets` (free text, default
    `default_note_presets()` -> "bomb", "sb ratting"; migration 0012), tab
    *Alliance*, Tom Select with `create` (`searchable.js` reads
    `data-eos-spy-network-create`). The form makes the stored plus the
    posted texts the choices and `clean_note_presets` normalises them like
    a note (whitespace, max `KILL_NOTE_LENGTH`, no duplicates/empties).
    Not part of `snapshot._inputs()` (changes no calculation). The popup
    (`kill-note-modal.html`) gets a button per text; `kills.js` hides them
    for a contacts finding; a click sets text + Cleared and saves.
  - Clearing a day: `reviewed_kills` adds `day_open` to each row,
    `kills.html` heads each date (`ifchanged`) with a row (count badge,
    tick, pen) through `kill-note-button.html` (`day`, `main_id`,
    `locked` once nothing is open). `views.kill_day_note`
    (`kills/day/`, `main_id` + `date`) takes only the open rows of that
    main and date from `_report` (404 otherwise), skips a group cleared
    meanwhile under `select_for_update`, writes a `ReviewLog` per
    killmail. Corporation page only; the settings tab stays flat.
  16 new tests, one adjusted (7 ticks instead of 4 with the day rows); 14
  failed against the old code (the default test passed because the model
  was not stashed, the "no buttons" test is a negative one). Settings page
  rendered in `aa_dev` (200, both buttons); nothing clicked in a browser.
- Before (0.0.25): *Ignored ships* (migration 0011), choices from
  killtracker's private `_require_victim_ship_types_query` plus the stored
  names, filtered in `markers.worth_counting` like the minimum value.
- Before (0.0.24): the eight fixes of the audit of 2026-11-11. The report
  is `docs/AUDIT.md` - **untracked on purpose** (user), keep it out of
  commits; it holds per finding the trace, the fix and the test, plus
  "Checked and fine" (no need to audit those areas again).
- Before (0.0.23): settings tab *Log*, model `ReviewLog` written by
  `kill_note` and `finding_note` inside `transaction.atomic` with
  `select_for_update`; migration 0010 seeded the earlier reviews (0 in
  `aa_dev`). The tab is rendered once with the page: a tick in another tab
  shows in the log only after a reload.
- Prod question (user, 2026-11-11): 5 blue kills ticked, the settings tab
  *Blue kills* showed only one. The code groups only per main and killmail
  (what the user wants), so 5 different killmails give 5 rows. Suspects: a
  minimum kill value set after the last recalculation (the settings tab
  filters at once, the marker page only after a recalculation), the 5 ticks
  on one killmail, or the DataTables search. The user was given a shell
  line for prod to list the reviewed `BlueKill` rows; the answer is open -
  next step once it comes. The *Log* tab on prod shows the seeded state of
  those reviews.
- Earlier versions (0.0.4 - 0.0.22): see `CHANGELOG.md`. Still relevant
  from them: `api.py` (0.0.10) is a stable contract with eos-auth-monitor -
  `character_markers() -> dict[int, list[str]]`, `label`, `description`,
  `KINDS`; change it only together with eos-auth-monitor. Colours
  (0.0.21/0.0.22): spy markers Bootstrap info, `text-info-emphasis` for
  text, legend from Bootstrap classes, only the hostile Alliance keeps
  `#8b1a1a` in `network.css`.
- What the app does today: settings (Alliance, hostile threshold, blue
  threshold, minimum kill value, ignored ships, note buttons, Corporation changes per year, time frame,
  ignored wallet entry types; contact sources; marker switches; every
  stored blue kill and every friendly hostile contact with note and Cleared
  tick, an admin clears without a note); Markers: the Corporations as
  tiles, per Corporation the mains with markers (hostile membership now and
  in the history, frequent Corporation changes, friendly hostile contacts,
  mails, ISK, contracts, blue kills - over main and alts); Network: the ISK
  connections with hostile partners. Pages read only the stored snapshot.
- Tests: 333 without translation tests plus 3 translation tests, all green
  in the dev instance at 0.0.26 (fresh test database); every new test
  checked against the unfixed code. `tests.base.SpyTestCase` patches
  `views.update_snapshot` and the three ESI calls of `affiliations.py`.
  `testauth` has `eveuniverse` and `killtracker` installed for the tests.
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user (0.0.13 added the blue kill texts, 0.0.14 the
  note texts, 0.0.19 the minimum value and contacts tab texts, 0.0.25
  "Ignored ships" and its help text, 0.0.26 the note buttons and day texts; Awox and
  Blue stay English; "Cleared" carries the `eos-spy-network` context -
  another app translates it differently in ru).

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker; switch to hide clean ones |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found; blue kills as a table with zKB links, note and Cleared tick, grouped by date with a row to clear the day's open kills |
| Network | `view_suspects` + `view_evidence` | a tile per Corporation: mains with connections to hostile partners |
| Network Corporation | `view_suspects` + `view_evidence` | the mains; on click a graph (partner, up to the reason) and a table of the connections with periods |
| Settings | `manage_settings` (+ `view_suspects` for the tabs Blue kills, Friendly to hostiles, Log) | tabs: Alliance (hostile and blue threshold, minimum kill value, ignored ships, note buttons, Corporation changes per year, time frame, ignored wallet types), Contact sources with aa-contacts' token state, Markers (switch per marker), Blue kills (all stored at or above the minimum value), Friendly to hostiles (all of the snapshot); in those two note and tick editable with `view_suspects`, clearing without a note; Log (every save of both) |

## Open

- 0.0.26 on prod: run migration 0012 (adds "bomb" and "sb ratting").
  Not clicked in a browser yet: a note button (saves and reloads), the
  day row's tick and pen, adding a free text in the *Note buttons* field
  (Enter creates it). `aa_dev` has no blue kill in its snapshot, so the
  day rows were only seen in tests.
- 0.0.25 on prod: run migration 0011. The ship list needs eveuniverse's
  ship types loaded (killtracker's own setup loads them); with few loaded,
  only the stored blue kill ships are offered. Click the multi-select
  once in a browser. After a killtracker update, check that
  `_require_victim_ship_types_query` still exists (else the list shrinks
  to the stored names, without an error).
- 0.0.24 on prod: an admin with `manage_settings` but without
  `view_suspects` loses the three review tabs - give them `view_suspects`
  if they are meant to review. After the next calculation the *Hostile
  membership* count drops by one for alts in a hostile Corporation with a
  corptools history. Not clicked in a browser: the hidden tabs, the
  *Own account* badge, the popup's 404 for a pair not on the page.
- The `disabled` branch in `partials/kill-note-button.html` is now
  unreachable (both pages that include it need `view_suspects`); left in,
  it costs nothing.
- Menu badge: the count costs a snapshot read and up to three small
  queries on every Auth page for `view_suspects` users; not measured on
  prod. A cache would be the fix if it shows.
- eos-auth-monitor: check that a character whose blue kills are all
  cleared, or whose blue kills were all inside its own account, loses its
  problem there (only tested on this side, `test_api`).
- Note and *Cleared* per finding, marker by marker (user, 2026-11-06):
  *Friendly to hostiles* is done (0.0.16, columns and EveWho links
  0.0.17). `aa_dev` has no contacts marker, so neither was seen in a
  browser; a contact hostile only through its Corporation still reads
  "Name (Corp)" next to the new Corporation column (left as is); seeding a corptools
  `CharacterContact` needs the user's yes.
  Decided (user): a review belongs to the **main** + finding, so a later
  alt with the same finding is cleared too; a different finding (other
  standing, new payment/mail/join) is **always a separate row** (option
  (a), not reopening) - for the dated markers the calculation has to split
  the rows at the review time. Next markers: Membership, Corporation
  changes, Mails/ISK/Contracts (mails need rows; with `view_evidence`).
- Not clicked in the browser yet: the 0.0.19 admin tick in both settings
  tabs (row tick without popup, Save without note), the contacts tab, the
  minimum value field, the 0.0.20 *Value* columns (`aa_dev` has no
  contracts marker; its 4 seeded `BlueKill` rows have no value, so they
  show "–"). `kills.js` has no JS tests; the server side is tested.
- Blue kills not clicked in the browser yet (checkbox, popup, settings
  tab, the 0.0.18 EveWho and audit icons; the `aa_dev` snapshot has no
  victim IDs until a recalculation). `aa_dev` holds 4 `BlueKill` rows with fake killmail IDs
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
  the settings tab; clearing needs a note (user; admins in the settings
  tabs excepted since 0.0.19); a cleared kill no longer counts (pages and API) but
  stays greyed in the table; at once, no recalculation. Changed
  (user, 2026-11-06): one row, note and tick per main and killmail, the
  main's characters together; two mains on one killmail, a row each. The settings tab
  lists every kill of the Alliance regardless of the time frame, client-side
  DataTables.
- Admin clearing (user, 2026-11-09): every reviewable finding gets a
  settings tab where a user with `manage_settings` **and** `view_suspects`
  clears with the tick alone; the Corporation page (the normal view) keeps
  the note. A marker that gets reviews later gets its own settings tab.
- Minimum kill value (user, 2026-11-09): million ISK, default 0 (off);
  below it hidden everywhere (marker, API, settings tab), not left
  uncopied; a kill without a known value counts.
- Ignored ships (user, 2026-11-13): the victim's ship, hidden like the
  minimum value; choices are what killtracker offers as a victim's ship
  (not only real ships, not only those already killed); default empty.
- Note buttons (user, 2026-11-13): a click enters the text, ticks Cleared
  and saves; blue kills only (not the friendly hostile contacts); free
  text in tab *Alliance*, default "bomb" and "sb ratting".
- Clearing a day (user, 2026-11-13): Corporation page only, a head row per
  date in the main's kill table; it touches only the open kills of that
  day, a cleared one keeps its note.
- Value columns (user, 2026-11-09): kill value and contract value in
  million ISK, in both blue kill tables (marker and settings tab); the
  contract value is price + reward, the collateral stays out (a deposit);
  the ISK marker's own column stays in full ISK.
- Colours (user, 2026-11-10): spy markers in Bootstrap info (cyan) in this
  app and in eos-auth-monitor - first purple, dropped the same day because
  purple text is hard to read in AA's dark theme and a standard colour needs
  no CSS. Red only for problems and hostiles (group cells, dealings,
  network partners and graph stay red), yellow for warnings, green for
  clean. Cyan is shared with *Player trading* on the network pages
  (accepted). The menu badge is Alliance Auth's own (`text-bg-primary`,
  blue) and stays. Coloured text in info is `text-info-emphasis`, not
  `text-info` (contrast, 0.0.22). Legend colours are Bootstrap classes;
  only the hostile Alliance keeps its own `#8b1a1a`, because
  `text-danger-emphasis` turns lighter in the dark theme (user,
  2026-11-10).
- Review log (user, 2026-11-11): every save of a note or tick is kept,
  shown in an own settings tab (not a popup per row); the reviews made
  before the log are seeded once with their last state. Blue kills stay
  grouped per main and killmail in both tables, nothing more (user).
- Audit (user, 2026-11-12): `manage_settings` alone does not see the
  findings - the three review tabs need `view_suspects` too. A reviewer
  may clear findings of their own account; the log marks it, no refusal.
  The contract popup is bound to the pairs the ISK marker shows, not to
  every character of the Alliance. A save during a running calculation
  makes that run repeat itself once, rather than a message to the admin.
- Menu badge (user, 2026-11-07): counts the mains with open markers (not
  markers or findings), only for `view_suspects`.
- Own kills (user, 2026-11-07): a blue kill whose victim belongs to the
  attacker's account is never stored; old copies are hidden, not deleted.
- Mails: headers and subject, never the body.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 to 0012
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
  testing the button. `collectstatic` ran with the 0.0.26 static files (`kills.js`, `searchable.js`). `aa_dev` is at 0012 (0.0.26).

## Traps

- Checking new tests against the unfixed code in one go: `git stash push
  -- <the changed code files>` (tests left in place), run the modules,
  `git stash pop`. Name the paths, or the tests go into the stash too.

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
- A missing key renders as an empty string in a template, not `None`: a
  test for "no link without an ID" asserts on `.../character/"`, not
  `.../character/None"`.
- Inheriting a test class to borrow a helper runs all its tests twice;
  assign the helper instead (`add_entry = TestWallet.add_entry`).
- Another app's suite running at the same time (eos-auth-monitor) shares
  `test_aa_dev` and breaks the run with "table already exists": set
  `EOS_TEST_DB=test_spy_net` for your own test database. `aa-test` ends
  with "xport: command not found" noise (its lines 52-53); results are fine.
- A new required `SpyConfiguration` form field breaks the settings POSTs in
  `test_views.TestSettingsPage` (200 instead of 302): add the field to each
  posted dict there.
- A heredoc inside `wsl.exe ... bash -lc '...'` breaks on the first
  apostrophe in the text: write files with the Write/Edit tools instead.
- To see the graph without SSO and without network data: a static page with
  the legend partial, `network.css`, `network.js` and a json_script graph.
  The Claude browser pane opens a `file://` page only as a snapshot without
  scripts; serve the folder over HTTP (`python3 -m http.server`) instead.
  `?dark` plus `data-bs-theme="dark"` on `<html>` before the scripts gives
  the dark theme - `network.js` reads the colours once at load.
