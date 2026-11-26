# Decisions

The user's decisions on `eos-spy-network` that hold for good and cannot be
seen in the code, sorted by topic. No session dates: an entry says what holds
and why. When a decision changes, its entry is replaced; superseded entries
are deleted. Not read at session start - look things up with `grep` or by
section.

## Purpose and scope

- Detect suspected spies - not run an own spy network, not an intel board.
- One Alliance, as in eos-auth-monitor.
- No new files (templates, partials, scripts) without asking - hence the
  standing badge written out twice and the search form copied onto the
  Network page.

## Hostiles and contacts

- Hostile = contact of a ticked source (the Alliance and/or its
  Corporations, ticked in a searchable table) with a standing below a
  configurable value, default below 0. One negative source is enough. The
  Alliance and its own Corporations never count. Hostility is always
  today's.
- *Friendly to hostiles*: only a standing above 0 counts, watched or not - a
  neutral contact is no friendship.
- Blue = the configured Alliance's own contacts only, not the ticked
  Corporation sources.
- ESI only in tasks, through public endpoints without a token, and only for
  what Auth and corptools do not hold (affiliations, Corporation and
  Alliance histories); plus the daily capital sweep. Whether a counterpart
  is hostile is decided without ESI.
- A failed names or affiliation request in `affiliations.py` gets no second
  try: it costs that run's affiliations only, the next run asks again.

## Time frame and tenure

- Time frame is "last N days", not fixed dates; it limits mails, ISK,
  contracts, Network payments and the Corporation history - standings change
  and the hostile list is today's.
- Only what a character did while in a Corporation of the Alliance counts
  (mails, ISK, contracts, Network, blue kills), by the Corporation's own
  alliance history. Membership, Corporation changes, contacts and capital
  contracts are not filtered.
- The counterpart's Alliance at the time of the payment, contract or mail
  decides, both ways: ours then -> no counterpart even if hostile today;
  joined later -> counts for the time before. Network and the markers ISK,
  Contracts, Mails; blue kills unchanged (awox is the point).
- The own Alliance and its Corporations are never a counterpart, also not
  for a character Auth does not know whom ESI puts there.
- ESI answers are buffered (user asked for it). Not done on purpose: no table
  for names or character affiliations (bulk POSTs, a table would save
  little); no "ask only when an event is newer than the stored history".

## Markers

- A switched-off marker is hidden, not skipped: it takes effect at once and
  back on without a recalculation.
- Ignored wallet entry types: one list for the ISK marker and the Network,
  default `market_transaction`.
- Public contracts never count for the Network and the markers ISK and
  Contracts - neither the contract nor the wallet entries paying for it.
  *Capital in contract* keeps them (they are its point).
- Ignored characters: one list for *Friendly to hostiles*, one for the
  Network; single characters, not accounts; the choices are the characters
  with a finding in the stored snapshot plus the IDs already stored. No
  history of who ever had a finding (offered, declined). A character that is
  only the counterpart of another account's payment is not ignored: the
  list ignores actors. Other markers have none.

### Blue kills

- One marker for awox and blue; every own attacker counts, not only the final
  blow; blue from a standing of 5 by default. Killmails come from
  killtracker's storage and are copied into `BlueKill`, so a kill survives
  killtracker's purge. A copy is the state when found: reason and standing
  stay when the victim is no longer blue.
- A kill whose victim belongs to the attacker's own account is never stored;
  old copies are hidden, not deleted.
- Minimum kill value in million ISK, default 0 (off); below it hidden
  everywhere (marker, API, settings tab); a kill without a known value
  counts.
- Ignored ships: the victim's ship, hidden like the minimum value; the
  choices are what killtracker offers as a victim's ship; default empty.
- Value columns in million ISK in both blue kill tables; contract value =
  price + reward, the collateral stays out (a deposit); the ISK marker's own
  column stays in full ISK.
- Headings *Victim Corporation* / *Victim Alliance* in the long form: a bare
  "Corporation" reads as the member's own.

### Capital in contract

- Only offered ships, no hostile, no time frame, no note or *Cleared*. The
  ship groups are a setting (default the eight capital groups, Freighters
  selectable; the user kept that over "classic only"). The issuer's
  Corporation decides, not `for_corporation`.
- Capital sweep: no ETag and no response cache for its calls, one more try
  per failed region in the same sweep, the error limit retried as Alliance
  Auth's own tasks do. A failed region keeps every row that day; deletion
  per region was not asked for.
- Copy button for the in-game link in the table and in the popup; link text
  = the ships, solar system `0` (tested in game; a structure's system is
  unknown without a token). Not for the ISK popup: corptools' contracts are
  private.

## Network

- Points: every payment, contract and trade is one point; a private contract
  with items is one point however many wallet entries pay for it. A main
  shows up at X points (setting, default 2) with one counterpart character or
  with one hostile Corporation/Alliance, summed over all its characters; a
  group hit shows all rows of its members.
- Hostile partners only by default; the switch *Network: neutral partners
  too* keeps neutral ones as well, blue never. No other exception to the
  hostile filter.
- Payments are donations, player trading and contract payments. A
  counterpart Auth does not know counts as outside; NPCs never.
- A contract counts for one partner: the acceptor, before acceptance the
  assignee.
- A private contract with items is its own kind of link; arrows show the flow
  from the giver to the receiver; column *Age* of the own character.
- Ignored counterparts: one list for the Network and the markers ISK and
  Contracts (mails keep the counterpart); a button in the Network table and in
  the ISK and contract tables, a confirmation naming the counterpart with a
  reason that is required; kept by EVE ID, the name only for display; the
  counterpart falls out completely; taken back in the settings list, which
  shows reason, who and when; both steps on the *Log* page; recalculates at
  once; only `manage_settings` (with `view_suspects`) sees the button.
- Graph: counterpart -> Corporation -> Alliance, the hostile one is the
  reason node labelled with its standing; own side green (main darker),
  hostiles red, others neutral; columns left to right; vis-network from
  cdnjs. The payment count stands on the lines (overlap accepted). The
  Corporation page lists the mains, graph and table only after a click.
- Search: the box sits on the Network page, the result on its own page
  without a menu entry; searched are the counterpart, its Corporation and its
  Alliance, not the own characters; Tom Select with free text; the result
  has the Network table's columns plus main and its Corporation, the main
  links to the Network Corporation page with it opened.
- Highlights: tiles on the Network page, chosen in the settings from the
  stored Network's parties (no free names), counted in mains, Network data
  only (a party the Network does not hold shows 0); a click opens the search
  for exactly that party (by ID, the name only in the box). Highlights do not
  score. Highlights beyond the Network:
  decided against for now.
- The Corporation tile on the Network page has no Payments row.
- Left as is: a counterpart only ESI knows shows as its ID, so the search
  cannot find it by name.

## Reviews (note and Cleared)

- A review belongs to the main + finding: a later alt with the same finding
  is cleared too; a different finding (other standing, new payment/mail/
  join) is always a separate row, never a reopened one - for dated markers
  the calculation splits the rows at the review time.
- Blue kills: one row, note and tick per main and killmail (two mains on one
  killmail, a row each). Editable with `view_suspects` on the Corporation
  page and in the settings tab; clearing needs a note, except for admins in
  the settings tabs. A cleared kill no longer counts (pages and API) but
  stays greyed; at once, no recalculation. The settings tab lists every kill
  of the Alliance regardless of the time frame.
- Every reviewable finding gets a settings tab where `manage_settings` +
  `view_suspects` clears with the tick alone; the Corporation page keeps the
  note.
- Note buttons: a click enters the text, ticks *Cleared* and saves; blue
  kills only; free texts in tab *Alliance*, default "bomb" and "sb ratting".
- Clearing a day: Corporation page only, a head row per date; it touches only
  that day's open kills, a cleared one keeps its note.
- *Cleared findings*: only mains with nothing open; one table for blue kills
  and contacts; read only (notes change in the settings tabs); folded at
  first.
- Review log: every save of a note or tick is kept, on its own page; reviews
  older than the log were seeded once with their last state.
- A reviewer may clear findings of their own account; the log marks it, no
  refusal.
- A save during a running calculation makes that run repeat itself once,
  rather than a message to the admin.

## Pages and layout

- Start page: a tile per Corporation of the Alliance; a click opens the
  Corporation page listing only the mains with markers. No plain hostile
  list page.
- Settings: one page, one form, in tabs; tab *Alliance* in sections
  (Alliance; what Markers and Network share; Markers per marker; Network),
  not own tabs.
- *Statistics*: own nav page, not a settings tab; only numbers the sweep has
  anyway, computed by the sweep, only the last run kept, plus counts per
  region and per Corporation. The *Log* page sits next to it.
- The standing the Alliance itself holds shows as a badge next to every party
  in the Network, search, ISK, contract and contact tables (one look
  everywhere); red text alone marks a hostile party there.
- *Reference standing*: the lowest standing of the ticked sources, the
  sources only in a tooltip; stored with the calculation rather than looked
  up at view time.
- Recalculation: stored in the database by a Celery task (not a cache, not
  live), started by the button, by saving the settings, or by a
  `CELERYBEAT_SCHEDULE` entry the admin adds.
- Colours: spy markers in Bootstrap info (cyan) here and in
  eos-auth-monitor - purple was dropped, hard to read in the dark theme.
  Coloured info text is `text-info-emphasis` (contrast). Red only for
  problems and hostiles, yellow for warnings, green for clean; cyan shared
  with *Player trading* (accepted). The menu badge stays Alliance Auth's own
  `text-bg-primary`. Legend colours are Bootstrap classes; only the hostile
  Alliance keeps `#8b1a1a`, because `text-danger-emphasis` turns lighter in
  the dark theme.

## Permissions and visibility

- `view_suspects`, `manage_settings`, `view_own_corporation`; no
  `basic_access` (it would open nothing). `view_evidence` was removed: nobody
  held `view_suspects` without it. Its row stays in `auth_permission` - a
  migration deleting it would take group assignments behind the admin's
  back.
- `manage_settings` alone does not see findings: the review tabs need
  `view_suspects` too. *Statistics* and *Log* need both.
- CEOs: `view_own_corporation`, given by the admin to a group (no automatic
  CEO detection); own = the main's Corporation. It shows that Corporation
  page with its evidence and its visitors - no Network pages, no notes or
  *Cleared*, no *Recalculate*, no settings. A CEO whose Corporation is not in
  the Alliance gets a 404 (left as is).
- Visitors: an account with an alt in a Corporation and its main elsewhere is
  that Corporation's problem too. Its whole account (main, main's
  Corporation, all alts, every marker with everything found) shows in an own
  block below the mains, to the CEO and to `view_suspects`, read only. A
  player is all of their characters: a main outside the Alliance is checked
  through an alt inside. A tile with a marked visitor is not clean. Levels:
  member (nothing - they would see their own suspicion), CEO (the main's
  Corporation plus its visitors), leadership (everything).
- Menu badge: counts accounts with open markers, each once, only for
  `view_suspects`; for a CEO the own Corporation's mains and visitors.
- Left as is after the permission review: a CEO sees the own account's
  markers (cannot clear them); settings changes stay unlogged; the CEO's side
  channels (footer counts, standing tooltip, victim audit link).

## eos-auth-monitor

- eos-spy-network stores the characters per marker, eos-auth-monitor shows
  them through `api.py` (display only, no problem counts); switched-off
  markers are left out as on the pages.
- eos-auth-monitor honours `view_own_corporation` and shows a CEO the
  markers of the own Corporation only, by this app's rule (`api.py`'s
  `corporation_id`); the permission check stays in eos-auth-monitor.
