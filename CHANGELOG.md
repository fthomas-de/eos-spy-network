# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.0.26] - 2026-11-13

### Added

- Note popup of a blue kill: a button per text of the new setting *Note
  buttons* (tab *Alliance*, free text, default "bomb" and "sb ratting").
  A click enters the text, ticks *Cleared* and saves, so the everyday
  reasons no longer have to be typed kill by kill. Offered on the
  Corporation page and in the settings tab *Blue kills*, not for the
  friendly hostile contacts, whose reasons are different. Texts are
  normalised like a note and no longer than one. Migration 0012.
- Corporation page: the blue kills of a main are grouped by date, each
  date headed by a row with its number of open kills, a tick and a note.
  It clears every open kill of the main on that day at once (new endpoint
  `kills/day/`), e.g. a whole evening of bombing. Kills already cleared
  keep their note; each killmail gets its own *Log* entry as with a single
  tick. A day with nothing open shows its tick locked.

## [0.0.25] - 2026-11-13

### Added

- Settings tab *Alliance*: *Ignored ships*, a searchable multi-select of the
  victim's ships whose blue kills do not count. The minimum value alone
  could not leave out a cheap ship by type, nor a ship whose kill has no
  known value. The choices are the types killtracker itself offers as a
  victim's ship (its tracker filter), the ships of the stored blue kills
  and whatever is ignored already; default none. Like the minimum value it
  hides the kills (marker, API, settings tab *Blue kills*) and deletes
  none, so taking a ship off the list brings its kills back. Migration
  0011.

## [0.0.24] - 2026-11-13

Fixes from the audit of 2026-11-11 (`docs/AUDIT.md`, SPY-01 to SPY-08).

### Added

- The settings tab *Log* marks a save a reviewer made on their own account
  with an *Own account* badge. Anyone with `view_suspects` may clear a
  finding of their own characters, and the log named them, but a reader had
  to compare *Changed by* with *Main* row by row to notice. The save stays
  allowed (user, 2026-11-12). Whose account it is is read when the tab is
  shown, from the ownership of today.

### Changed

- The settings tabs *Blue kills*, *Friendly to hostiles* and *Log* need
  `view_suspects` as well. With `manage_settings` alone they showed every
  blue kill, every friendly hostile contact, the notes and the log per
  main - who is suspected, to a permission meant for the Alliance, the
  sources and the thresholds. They are now neither rendered nor read
  without `view_suspects` (user, 2026-11-12).
- The menu entry and the start page no longer open with `view_evidence`
  alone. No page opens with it without `view_suspects`: the entry led to
  the Markers page and from there to the login page.

### Fixed

- The contract popup only answers for a pair the ISK marker shows with a
  contract payment. `contracts/<character>/<counterpart>/` took any two
  IDs and returned the contracts of any character corptools audits, in the
  Alliance or not, with any counterpart, hostile or not. It now reads the
  stored result first and answers 404 for anything the page does not offer.
- `findings/note/` only stores a review for a finding the stored result
  holds. It took any main and any key, so a reviewer could clear a contact
  before it was found - it then never showed as open - and fill the log
  with entries nobody could open; a negative main ID ended in a database
  error. Anything else is now a 404 before a row is written.
- Settings saved while a calculation runs are applied. The save queues a
  run, but `QueueOnce` drops it while one is going, and that one had read
  the settings at its start: the result was made with the old values and
  stamped as new, while the page said it was being recalculated.
  `snapshot.update` now compares the settings and the contact sources
  before and after the calculation and repeats it once when they differ.
- A current hostile membership counts once. Auth's Corporation of today and
  the open-ended record of corptools' Corporation history are the same
  membership, but each added to the count: "Hostile membership (2)" for one
  alt in one hostile Corporation, 1 without corptools. The history now
  skips the record the current membership has marked; an earlier, ended
  membership in the same Corporation still counts.
- *Recalculate* with a `next` that is no path (`next=x`) no longer ends in
  a server error. Django's `redirect()` looks a word without a slash up as
  a URL name and raises on an unknown one; only a value starting with `/`
  is taken now, anything else goes to the start page.

## [0.0.23] - 2026-11-11

### Added

- Settings tab *Log*: every save of a note or a *Cleared* tick of a blue
  kill or a friendly hostile contact, the latest first, with who and when,
  the main, the finding (victim with zKB link, or the contact), the tick
  before and after and the note before and after. Until now each save
  overwrote the last one, so nobody could tell who had cleared a finding
  before or what the note had said. New model `ReviewLog`, written by
  `kill_note` and `finding_note` in the same transaction as the review.
  A blue kill's entry keeps the character it was saved for; its main is
  looked up when the tab is shown, like the victims' mains. Migration 0010
  copies each review made before the log in as one entry with its last
  state (a main's characters of one killmail as one entry); it reads and
  writes only this app's tables.

## [0.0.22] - 2026-11-10

### Changed

- The *Mains with markers* count on a tile with markers is
  `text-info-emphasis` instead of `text-info`, as in eos-auth-monitor:
  plain info cyan has a contrast of about 2:1 on white and was hard to read
  in the light theme.
- The network graph's legend takes its colours from Bootstrap classes
  (`text-success`, `text-warning`, `text-secondary`, `text-danger`,
  `text-info`, the lighter ones with `text-opacity-50`) instead of rules of
  its own in `network.css`, and the graph's frame is `border rounded`; the
  fixed height of 520 px is gone, `network.js` sets the height itself
  before it draws. The `eos-spy-network-legend-*` classes stay, `network.js`
  reads the colours from them. `network.css` keeps only the deep red of a
  hostile Alliance, which Bootstrap has no class for (`text-danger-emphasis`
  turns lighter in the dark theme). The lighter colours are now 50 %
  instead of 55-60 %, the steps Bootstrap offers.

### Fixed

- The recalculation's progress bar keeps its minimum width on every page.
  The rule lived in `network.css`, which only the network Corporation page
  loads, so on the Markers, Corporation and Network pages the empty bar
  could shrink. It now has its own `progress.css`, loaded by `base.html`
  next to `progress.js`.

## [0.0.21] - 2026-11-10

### Changed

- Spy markers are Bootstrap's *info* colour (cyan) instead of red: the
  marker badges on the Markers and Corporation pages, and on a tile with
  markers its border and the *Mains with markers* count. Red also meant
  hostile contacts, Corporations and Alliances, so a marker and a hostile
  looked the same; eos-auth-monitor draws its markers in the same colour.
  Hostiles stay red, tiles without markers stay green. A standard colour
  rather than purple: purple text is hard to read in Alliance Auth's dark
  theme, and Bootstrap has no purple utilities.

## [0.0.20] - 2026-11-09

### Added

- *Blue kills* (marker and settings tab): a *Value* column with the
  killmail's value in million ISK, the unit of the minimum kill value, so a
  reviewer sees at a glance whether a kill matters; "–" when zKillboard sent
  no value. The marker page shows it after the next recalculation.
- *Contracts with hostiles*: a *Value* column in million ISK per own
  character and hostile, the sum of price and reward of its contracts. The
  row only said how often and when, not how much changed hands; the
  collateral is left out, it is a deposit that comes back. Shows after the
  next recalculation.

## [0.0.19] - 2026-11-09

### Added

- Settings, *Alliance*: a minimum value for blue kills in million ISK, as
  killtracker's own trackers take it (default 0: every kill). A capsule or
  a shuttle shot by a blue made a marker as loud as a lost battleship. A
  kill below it counts neither for the marker and eos-auth-monitor nor in
  the settings tab; one zKillboard sent no value for still counts. The
  value comes from killtracker and is refreshed on every copy, so kills
  copied before get theirs at the next recalculation as long as killtracker
  still holds them (migration 0009).
- Settings tab *Friendly to hostiles*: every friendly hostile contact of
  the last calculation, the cleared ones too, with main, characters,
  Corporation, Alliance, standing, tick and note - so an admin can work
  through the findings without opening each Corporation.

### Changed

- In the settings tabs *Blue kills* and *Friendly to hostiles* a user with
  `manage_settings` (and `view_suspects`, which the tick needs) clears a
  row with the tick alone, without a note (user's decision). On the
  Corporation page clearing still asks for a note, also of an admin; the
  server takes a cleared finding without a note from `manage_settings`
  users only.

## [0.0.18] - 2026-11-07

### Added

- *Blue kills* (marker and settings tab): EveWho icons after each own
  character and after the victim, its Corporation and its Alliance, as in
  *Friendly to hostiles*; checking a victim no longer means searching by
  name. A victim with an account in Auth also gets an audit icon to its
  main's corptools audit, looked up at every view, so an alt that changed
  hands needs no recalculation. A victim without an account, a structure
  without a victim character or an empty Alliance gets no icon.
- Needs one recalculation for the victim's icons on the marker page (the
  stored rows had no victim IDs); the own characters' icons and the
  settings tab show at once.

## [0.0.17] - 2026-11-07

### Added

- *Friendly to hostiles*: the contact's Corporation and Alliance as two
  columns, red with the standing when hostile themselves. Before, a
  character contact showed only its name, and the hostility usually sits
  on its Corporation or Alliance. They come from the same lookup as the
  ISK and contract counterparts (Auth, corptools, then public ESI in the
  task); the two cells are now one partial for both tables.
- *Friendly to hostiles*: a small EveWho icon after the contact (its
  character, Corporation or Alliance page; none for a Faction) and after
  each own character, so checking one no longer means searching by name.
- Needs one recalculation for the columns and the contact's link; the own
  characters' links show at once.

## [0.0.16] - 2026-11-07

### Added

- *Friendly to hostiles*: note and tick *Cleared* per main, contact and
  standing on the Corporation page, as for the blue kills. Before, a
  contact checked and found harmless kept marking the main with no way to
  say so. The marker now shows a table, one row per contact and standing
  with the main's characters together; a cleared row stays greyed and no
  longer counts, on the pages and in `api.character_markers()`, at once.
  The review belongs to the main (user's rule): an alt that shows the same
  contact at the same standing later is cleared with it; another standing
  is a new, open finding. Stored in the new model `FindingReview`
  (migration 0008, endpoint `findings/note/`), kept apart from the
  snapshot so a recalculation does not lose it; the other markers can
  join it later. Needs one recalculation: an older snapshot has no
  contact rows and shows the plain list until then.
- Menu badge: the *Spy Network* menu item shows how many mains have open
  markers, for users with `view_suspects`. Before, a new finding showed
  only to someone who opened the app. The count is the one the
  Corporation pages list: switched-off markers and cleared findings do
  not count. Read from the stored snapshot on every page.

### Fixed

- Blue kills: a kill between two characters of one account (attacker and
  victim belong to the same main) no longer counts as awox. It marked a
  player who shot one of their own characters. Such a kill is no longer
  copied into `BlueKill`; copies made before stay in the database but are
  left out of the marker and `api.character_markers()` from the next
  recalculation on, and out of the settings tab at once.

## [0.0.15] - 2026-11-06

### Changed

- Blue kills: one row, one note and one tick *Cleared* per main and
  killmail, on the Corporation page and in the settings tab. Before, a
  killmail with two characters of one main showed two rows with a tick
  each, while the marker counted it once - the page said *Blue kills (3)*
  over four rows. The characters of the main now stand together in one
  row; two mains on one killmail still get a row each. Saving writes the
  note and the tick to every `BlueKill` row of that killmail whose
  character belongs to the same main, so no migration is needed; a row
  reviewed alone before keeps the killmail open until all are cleared.
- The tick is a checkbox in its own column *Cleared*, no longer hidden in
  the popup. Ticking a row without a note opens the popup with the tick
  set (clearing still needs a note); a row with a note is ticked and
  unticked at once.

## [0.0.14] - 2026-11-06

### Added

- A note and a tick *Cleared* per blue kill row (own character and
  killmail), in a popup on the Corporation page and in the new settings tab
  *Blue kills*, editable with `view_suspects`; as the GM transaction notes
  of eos-tax, up to 160 characters, with who changed them last. A cleared
  kill stays in the table, greyed, but no longer counts for the marker - a
  main whose kills are all cleared and who has nothing else is clean, and
  `api.character_markers()` leaves the character out, so eos-auth-monitor
  shows no problem for it. The review is applied when the stored result is
  read, not stored in it, so it takes effect at once without a
  recalculation; it lives on the `BlueKill` copy, which a later calculation
  updates by name only and so leaves alone. Clearing needs a note: the
  next reader must see why a kill was let go (the popup enables the tick
  only with a note, the server refuses it without). Migration 0007.
- Settings tab *Blue kills*: every blue kill stored for the Alliance, also
  those outside the time frame, sortable, paged and searchable (the note
  included). Before, a kill outside the time frame could not be seen at all.

### Changed

- `api.character_markers()` reads the reviewed blue kills in a third query
  when the snapshot holds blue kills; without them it stays at two.

## [0.0.13] - 2026-11-06

### Added

- New marker *Blue kills*: a character was among the attackers of a
  killmail whose victim is in the Alliance (awox) or blue to it - the victim,
  its Corporation or Alliance has at least the new setting *Blue from
  standing* (default 5) with the Alliance. Only the Alliance's own contacts
  in aa-contacts count, not the ticked Corporations': a Corporation's private
  friendship makes nobody blue for the Alliance. The killmails come from
  killtracker's own tables (`EveKillmail`), which it fills only with
  `KILLTRACKER_STORING_KILLMAILS_ENABLED`; corptools keeps no killmails, and
  killtracker's trackers store nothing. A killmail counts once per account,
  with a row per own character, linked to zKillboard. The marker needs no
  hostile, so it runs even without a ticked source. killtracker stays
  optional: the marker pages say when it is missing or does not store.
  killtracker deletes its killmails after a few days (default 30), so every
  calculation copies the blue kills it finds into a table of its own
  (`BlueKill`) and the marker reads that: a kill stays as long as one
  calculation ran before the purge. Awox or blue and the standing are fixed
  when copied, the names follow killtracker until it deletes the killmail

## [0.0.12] - 2026-11-04

### Added

- A row of the ISK marker with contract payments (`contract price`, reward,
  collateral ...) has a *View details* button: a popup lists the contracts
  behind those payments of the character and the counterpart - issuer,
  assignee, acceptor, dates, price, reward, collateral, locations, items.
  corptools' React pages cannot be embedded, so the popup is its own small
  view (`contracts/<character>/<counterpart>/`, needs `view_suspects` and
  `view_evidence`) reading corptools' wallet journal (`context_id`) and
  contracts live, within the time frame and without the ignored entry types.
  Rows carry the character's EVE ID for this; a result stored by 0.0.11 or
  older shows no button until the next recalculation

## [0.0.11] - 2026-11-04

### Fixed

- *Friendly to hostiles* no longer marks a hostile on the watch list with a
  standing of 0: only a standing above 0 counts, watched or not

## [0.0.10] - 2026-11-04

### Added

- Every marker now records the own characters behind it (`character_ids`
  per marker in the stored result): for membership and Corporation changes
  the character concerned, for contacts the one holding the contact, for
  mails the one whose mailbox holds the mail, for ISK and contracts the one
  whose journal or contract it is. Until now a marker knew only the
  account, so another app could not show it at the character in its own
  Corporation. A result stored by 0.0.9 or older names no characters until
  the next recalculation
- `eos_spy_network.api`, a small read API for other apps (eos-auth-monitor):
  `character_markers()` maps each EVE character ID to its marker kinds,
  from the stored result only, empty when that is missing or of another
  Alliance, and without the markers switched off in the settings, as on
  the pages; `label(kind)` and `description(kind)` give the texts the pages
  show, `KINDS` the kinds in page order. Permissions stay with the calling app

## [0.0.9] - 2026-11-04

### Added

- Settings, tab *Markers*: a switch per marker. A marker switched off is
  still calculated, but the Markers pages leave it out, and a main marked
  by nothing else counts as clean. Some markers fire for routine play in
  one Alliance and not another; until now they could only be read past.
  The pages filter the stored result, so switching a marker back on shows
  it at once, without a recalculation. A notice above the Markers pages
  names the switched-off ones

### Changed

- Settings: the page is split into the tabs *Alliance*, *Contact sources*
  and *Markers*. The source table of a large Alliance pushed the Save
  button far down. It is still one form: each tab's Save button saves all
  three and comes back to its own tab, and after an error the tab holding
  it opens

## [0.0.8] - 2026-10-09

### Changed

- Recalculation: corptools' wallet journal, mails, contracts, contacts and
  Corporation history are read by the CharacterAudit IDs, looked up once.
  Filtering on the EVE ID joined the audit and EveCharacter in every one of
  these queries and left MySQL to guess the join order; now each query
  ranges over corptools' (character, date) index
- Network: the journal is read without the names of both parties. Two joins
  on corptools' names per payment, although most payments are inside the
  Alliance and drop out; the names of the partners that stay are looked up
  afterwards
- Recalculation: the hostile list, the mains and their characters are read
  once per run; the markers and the network each read them again

## [0.0.7] - 2026-10-09

### Changed

- *Friendly to hostiles*: a watched hostile with a negative standing no
  longer counts. PvP pilots watch their enemies routinely, so the marker
  fired for ordinary fleet work; a positive standing, or a watched hostile
  at 0 or above, still counts
- Network graph: the payment count is back on the lines; the tooltip alone
  hid it

## [0.0.6] - 2026-10-09

### Added

- Settings: a time frame in days (default 365, 0 takes everything). Wallet
  entries, contracts, mails, the network's payments and former Corporations
  count only within it. The hostile list is today's: a payment to a
  Corporation that was a friend three years ago marked the account as if it
  had been hostile then. A mail without a date still counts; contacts have
  no date in corptools and are checked as they are today
- Settings: wallet entry types to ignore, chosen from the types in
  corptools' wallet journals (default `market_transaction`). Buying from a
  hostile's sell order is anonymous and made *ISK with hostiles* fire for
  ordinary market trading; the ignored types drop out of the network's
  payments as well
- Corporation page: *ISK with hostiles* and *Contracts with hostiles* show
  the counterpart's Corporation and Alliance, red with the standing when
  hostile. Only the name was shown, so a character hostile through its
  Alliance gave no hint which one. The task looks them up like the
  network's partners (Auth, corptools, then ESI's public endpoints); a
  snapshot of 0.0.5 or older shows the columns after the next run

### Changed

- *Hostile membership* from the Corporation history counts only a
  membership that lasted into the time frame

## [0.0.5] - 2026-10-09

### Added

- Corporation page: *ISK with hostiles* and *Contracts with hostiles* list a
  row per own character and hostile - count, ISK moved (wallet), period from
  the first to the last one, kinds - where only the hostiles' names were
  shown, which said nothing about how much or how long
- Corporation page: *Frequent Corporation changes* names the Corporations
  joined, with the day, in a tooltip per character instead of only a count
- Network: period of the payments per connection in the table and in the
  line's tooltip

### Changed

- Network: a shared payment partner or a trade counts only with a hostile
  partner (itself, its Corporation or its Alliance below the standing
  threshold). Sharing a trader or hauler outside the Alliance is everyday
  business and filled the page with harmless accounts
- Network graph: a Corporation or Alliance gets a node only when it is the
  reason the partner is hostile, or sits between the partner and a hostile
  Alliance; the others are named in the partner's tooltip. Neutral groups
  doubled the nodes without saying anything
- Network graph layout: wider columns so names wrap less, more space between
  nodes, the height follows the fullest column, and a short repulsion run
  pushes labels apart before the graph freezes; the payment count moved
  from the lines into their tooltip, where the labels covered each other

## [0.0.4] - 2026-10-09

### Added

- Network graph follows each counterpart to its Corporation and Alliance, so
  the reason a partner is hostile - a Corporation or Alliance below the
  standing threshold - shows as a node of its own with its standing and
  sources. The affiliation comes from Auth and corptools first; only for
  counterparts neither knows the task asks ESI's public endpoints (corptools
  never fills a counterpart's Corporation, so without that the chain ended
  at the character)
- Network: *Hostile partner* count per main and per Corporation tile, and
  Corporation and Alliance columns with standings in the connection table
- Switch on the network tiles to hide the Corporations without connections
- Progress bar with the current step while the recalculation runs; the page
  reloads when it is done instead of asking the viewer to reload

### Changed

- Network Corporation page lists the mains first; graph and table appear
  only after a click on a main (and with `#main-<id>` in the address), where
  every graph used to be drawn at once
- Graph colours and layout: own characters in greens, hostiles in reds,
  laid out in columns left to right - main, alts, partners, Corporations,
  Alliances

## [0.0.3] - 2026-10-09

### Added

- Network page: per Corporation the mains whose main and alts exchanged ISK
  with the same character outside the Alliance (donations, player trading,
  contract payments), or traded with someone outside it, with a graph of the
  connections (vis-network) and a table per main. Needs `view_suspects` and
  `view_evidence`: the connections are wallet counterparts
- Recalculate: markers and connections are calculated by the task
  `update_snapshot` and stored (migration 0003); a button on the pages and
  saving the settings start it. The pages had computed everything on every
  view, over every wallet journal of the Alliance
- Footer with what the last calculation cost and how long the page took
- Switch on the marker tiles to hide the Corporations without markers

### Changed

- The Corporations tab is now called Markers; the new tab is Network

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
