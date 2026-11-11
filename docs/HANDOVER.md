# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-11-11.

## State

- Unreleased (2026-11-11): settings tab *Log* (`TAB_LOG`,
  `views._log_rows`), model `ReviewLog` (alliance, kind, `character_id`,
  key, cleared, note, `previous_cleared`, `previous_note`, `changed_at`,
  `changed_by`), written by `kill_note` and `finding_note` inside
  `transaction.atomic` with `select_for_update` on the review rows. For a
  blue kill `character_id` is the posted character, its main looked up at
  view time (`_victim_mains`); for a finding it is the main. Migration 0010
  seeds one entry per earlier review (blue kills deduplicated by alliance,
  killmail, `reviewed_at`, `reviewed_by`), applied to `aa_dev` (0 entries:
  none of its kills was ever reviewed). Tests `test_review_log.py` (8),
  checked against 8 faults, all caught. Glossary has the new texts; the
  catalogues follow at `/commit`. Not seen in a browser. The tab is
  rendered once with the page: a tick in another tab shows in the log only
  after a reload (said in the tab's help text).
- Prod question (user, 2026-11-11): 5 blue kills ticked, the settings tab
  *Blue kills* showed only one. The code groups only per main and killmail
  (what the user wants), so 5 different killmails give 5 rows. Suspects: a
  minimum kill value set after the last recalculation (the settings tab
  filters at once, the marker page only after a recalculation), the 5 ticks
  on one killmail, or the DataTables search. The user was given a shell
  line for prod to list the reviewed `BlueKill` rows; the answer is open.
- Version: `0.0.22`, 2026-11-10 (see `CHANGELOG.md`): the *Mains with
  markers* count is `text-info-emphasis` (plain `text-info` has about 2:1
  contrast on white; eos-auth-monitor does the same). The network legend
  uses Bootstrap classes (`partials/network-legend.html`, lighter shades
  `text-opacity-50`); the `eos-spy-network-legend-*` classes stay as the
  hook `network.js` reads the colours from. The graph is `border rounded`
  without a fixed height (`network.js` sets it). `network.css` holds only
  `legend-hostile_alliance` (`#8b1a1a`); the progress bar's `min-width`
  moved into `progress.css`, loaded by `base.html` next to `progress.js`
  (before, only the network Corporation page loaded it). Tests: marker
  colour test sharpened,
  `test_views.TestNetworkPages.test_should_colour_the_legend_with_bootstrap_classes`
  new, a `progress.css` assertion in `test_progress.TestPages`; all red
  against the old state. Graph seen in a browser, light and dark, as a
  static page with the real legend, `network.css`, `network.js`,
  Bootstrap 5.3.3 and vis-network 10.1.2 (`aa_dev` has no network
  partner): all ten colours arrive, vis draws the `rgba(...)` of
  `text-opacity-50`. Not seen: the count in the running app (no marker in
  `aa_dev`), the progress bar (needs a running recalculation).
- Before (0.0.21): spy markers in Bootstrap info (cyan) instead of red,
  as in eos-auth-monitor: `text-bg-info` badges in `corporations.html` and
  `corporation.html`, `border-info` on a tile with markers.
- Before (0.0.20): *Value* columns in
  million ISK (`markers.million`, `floatformat:"1g"` + " M", "–" when
  unknown) for the blue kills (marker row key `million`,
  `views._kill_rows` sets `row.million`; the settings tab sorts by the raw
  ISK in `data-order`, `stringformat:'f'` keeps it unlocalized) and the
  *Contracts with hostiles* rows (`Dealings` sums price + reward, the row
  key `million` exists for ISK rows too but only contracts show it). The
  marker pages need a recalculation, an older snapshot shows "–". Msgid
  "Value" (de Wert, ru Стоимость, zh 价值; no AA clash). Tests: one each in
  `test_kills.TestKillsPage`, `test_kill_reviews.TestSettingsTab`,
  `test_markers.TestContracts`; checked against 7 faults, all caught. Not
  seen in a browser.
- Before (0.0.19), three things:
  - Minimum blue kill value: `SpyConfiguration.min_kill_value` (million
    ISK, default 0 = off, Alliance tab) and `BlueKill.value` (float, from
    killtracker's `EveKillmail.total_value`; migration 0009, applied to
    `aa_dev`). `killmails.Kill.value`; `markers._copy_kills` writes it and
    the upsert refreshes it (`RESOLVED_NAMES` now holds `value`), so older
    copies get it while killtracker still holds the killmail.
    `markers.worth_counting(queryset, config)` filters in `_check_kills`
    (marker, API - after a recalculation, which saving the settings
    starts) and `views._kill_rows` (settings tab, at once). A kill without
    a value counts. Tests `test_kills.TestMinimumValue` (6), one in
    `test_kill_reviews.TestSettingsTab`.
  - New settings tab *Friendly to hostiles* (`TAB_CONTACTS = "contacts"`,
    `views._contact_rows`): every contacts row of the stored snapshot,
    cleared ones too, with main, characters, contact, Corporation,
    Alliance, standing, tick, note, "Last changed by"; reviews read from
    `FindingReview` of the configured Alliance. `views._snapshot(config)`
    is the shared "snapshot of this Alliance or None" (also used by
    `_report`). Tests `test_finding_reviews.TestSettingsTab` (4).
  - Clearing without a note for admins: `views._posted_note` refuses an
    empty note only without `manage_settings` (endpoints still need
    `view_suspects`). The settings page includes the popup with
    `admin=True` -> `data-eos-spy-network-kill-admin`; `kills.js` then
    stores the row tick at once and lets Save go without a note. The
    Corporation page keeps the note in its popup - for admins only a UI
    rule, the server would take it. Tests in `TestKillNote` and
    `TestFindingNote`.
  None of it seen in a browser (`aa_dev` has neither a contacts marker nor
  real blue kills with a value).
- Before (0.0.18): *Blue kills* got EveWho icons (own characters, victim,
  its Corporation and Alliance) in the marker and the settings tab, plus an
  audit icon (`corptools:reactmain`) to the **main** of a victim with an
  account in Auth (`views._victim_mains`, read at every view). The victim's
  icons on the marker page need a recalculation. Not seen in a browser.
- Before (0.0.17): *Friendly to
  hostiles* shows the contact's Corporation and Alliance (two columns, red
  with standing when hostile) and a small EveWho icon after the contact
  (`/character|corporation|alliance/<id>`, none for a Faction or an
  unknown category) and after each own character. The contact rows go
  through the same affiliation step as ISK/contracts
  (`snapshot._affiliate_rows(..., "contact_id")`, so public ESI in the
  task for what Auth and corptools do not know); `Marker.affiliated` now
  covers contacts; `reviewed_contacts` adds `named_characters` (ID, name)
  at read time because the template cannot zip. New partials
  `affiliation-cells.html` (shared with `dealings.html`) and
  `evewho-link.html`. Columns and the contact's link need a
  recalculation; the own characters' links show at once. Tests
  `test_finding_reviews.py` (21). Not seen in a browser (`aa_dev` has no
  contacts marker).
  Decided (user, 2026-11-07): Corporation **and** Alliance as columns; the
  link is an icon after the name, the name stays text; a Corporation or
  Alliance contact links to its own EveWho page.
- Before (0.0.16), three things:
  - *Friendly to hostiles* reviewed like the blue kills: note and tick per
    main, contact and standing. Model `FindingReview` (alliance, kind,
    **main_id**, key; migration 0008, applied to `aa_dev`), endpoint
    `views.finding_note` (`findings/note/`, `REVIEWED_KINDS`), applied at
    read time by `snapshot.finding_reviews` + `reviewed_contacts` (pages
    and `api.py`); key `<contact ID>:<standing>`; popup and `kills.js`
    shared with the blue kills (a button with `data-...-kill-key` posts to
    the finding URL).
  - Menu badge: mains with open markers (`views.open_mains`, reuses
    `_report`, so switched-off markers and cleared findings do not count);
    `auth_hooks` sets `count` on every render - one hook object serves all
    users - and `None` without `view_suspects`. Tests `test_menu.py`.
  - Blue kills inside one account (attacker and victim owned by the same
    user, `markers.own_kill`) are not copied into `BlueKill` and are
    filtered at read time in `_check_kills` and `views._kill_rows`; old
    rows stay in the table.
  None of the three seen in a browser.
- Before (0.0.15): blue kills
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
  threshold, minimum kill value, Corporation changes per year, time frame,
  ignored wallet entry types; contact sources; marker switches; every
  stored blue kill and every friendly hostile contact with note and Cleared
  tick, an admin clears without a note); Markers: the Corporations as
  tiles, per Corporation the mains with markers (hostile membership now and
  in the history, frequent Corporation changes, friendly hostile contacts,
  mails, ISK, contracts, blue kills - over main and alts); Network: the ISK
  connections with hostile partners. Pages read only the stored snapshot.
- Tests: 290 without translation tests plus 3 translation tests, all green
  in the dev instance (0.0.22 added 1 for the legend); every new test
  checked against sabotaged code (0.0.22: against the old templates and
  CSS, all caught). `tests.base.SpyTestCase` patches
  `views.update_snapshot` and the three ESI calls of `affiliations.py`.
  `testauth` has `eveuniverse` and `killtracker` installed for the tests.
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user (0.0.13 added the blue kill texts, 0.0.14 the
  note texts, 0.0.19 the minimum value and contacts tab texts; Awox and
  Blue stay English; "Cleared" carries the `eos-spy-network` context -
  another app translates it differently in ru).

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, count per marker; switch to hide clean ones |
| Corporation | `view_suspects` (+ `view_evidence` for the counterparts of mails/ISK/contracts) | mains with markers and what was found; blue kills as a table with zKB links, note and Cleared tick |
| Network | `view_suspects` + `view_evidence` | a tile per Corporation: mains with connections to hostile partners |
| Network Corporation | `view_suspects` + `view_evidence` | the mains; on click a graph (partner, up to the reason) and a table of the connections with periods |
| Settings | `manage_settings` | tabs: Alliance (hostile and blue threshold, minimum kill value, Corporation changes per year, time frame, ignored wallet types), Contact sources with aa-contacts' token state, Markers (switch per marker), Blue kills (all stored at or above the minimum value), Friendly to hostiles (all of the snapshot); in those two note and tick editable with `view_suspects`, clearing without a note; Log (every save of both) |

## Open

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
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 to 0009
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
  testing the button. `collectstatic` ran with the 0.0.22 static files.

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
