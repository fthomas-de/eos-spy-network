# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.1.9] - 2026-11-27

### Added

- The Corporation tile on the Network page shows a *Payments* row, as the
  Corporation page already did: the Network page named the shared partner,
  player trading and private contracts but left out the plain payments, so a
  tile and its page disagreed. It counts the mains with a plain payment (no
  trade) and reads the same links as the page, so ignored counterparts and
  characters stay out of it. No migration, no `collectstatic`.

## [0.1.8] - 2026-11-27

### Added

- Marker *Owner changes*: a character that changed hands. Alliance Auth keeps
  an `OwnershipRecord` per owner hash of a character; a record whose hash is
  not the one the character holds today is an earlier owner, shown by the
  main of its Auth account (else the user name). Only the hash counts: the
  same hash under another Auth account is the same player moving the
  character, not a sale. The whole history counts, whatever the time frame -
  a record's `created` is `auto_now`, the day Auth first saw the owner, no
  date to cut by. A case is one character with its earlier owners, with a
  note and a *Cleared* tick like the Corporation changes; a further earlier
  owner after the tick opens a new case with that owner alone. It has a
  settings tab, a row in the log and a place in `api.KINDS`, so eos-auth-monitor
  shows it without a change. Limits: a record goes with its user (cascade), so
  an earlier owner's deleted Auth account takes the finding with it, and Auth
  knows nothing of owners from before it kept records. No migration; the
  marker needs one recalculation to appear, and `collectstatic` is not needed.

## [0.1.7] - 2026-11-27

### Fixed

- **403 instead of the login page**: a logged-in user without the permission
  of a page was sent to the login page, as if they were not signed in. They
  now get "403 Forbidden", as in eos-auth-monitor. A user who is not logged
  in still goes to the login page. The permission checks in
  `permissions._required` raise `PermissionDenied` instead of failing
  `user_passes_test`.

## [0.1.6] - 2026-11-27

### Added

- Markers *Mails with hostiles*, *ISK with hostiles* and *Contracts with
  hostiles*: a note and a *Cleared* tick per case, as the blue kills and
  contacts had - before, a checked trade or mail kept marking the account
  forever. A case is one own character with one counterpart, summed; an info
  button shows each journal entry, contract or mail of it (a mail with its
  direction and subject, never its text). Mails had no table before, only
  the counterparts' names; they now have one like ISK, without an ISK
  column and without the ignore button (mails keep an ignored counterpart).
  The first tick fixes the entries the case holds:
  whatever comes after - also an entry corptools fetches late with an older
  date, which a split by time would have hidden - is a new open case. On the
  Corporation page the open cases stand under a row per date of their last
  interaction, to clear a whole day at once; each marker has a settings tab,
  and the log names the case. Needs migration 0026, `collectstatic` and one
  recalculation: an older snapshot holds no entries and shows no tick.
- Marker *Hostile membership*: a note and a *Cleared* tick per hostile
  group of an account, in a table instead of a list of names, each
  membership (character, day joined) behind the info button. A tick fixes
  the memberships it saw; a character joining the group again, or one newly
  added to the account who is or was in it, is a new case - leaving it is
  not. A membership only Auth knows (no Character Audit) becomes a new case
  once, when corptools' history names it.
- Marker *Frequent Corporation changes*: a note and a *Cleared* tick per
  character, in a table instead of the tooltip, the Corporations joined
  behind the info button. A tick fixes the joins it saw; a later join opens
  the character again as a new case with every join of the last 365 days -
  the number is the finding, not the one join.

### Changed

- Corporation page: the cleared findings of every marker with a tick no longer
  stand greyed between the open ones but folded below them, under one
  *Cleared* row per marker (user, 2026-11-27). A day row of the blue kills is
  only shown while one of its kills is open.

## [0.1.5] - 2026-11-26

### Added

- Network search: the column *Age* of the own character, as on the Network
  Corporation page - the result rows had none.
- Network Corporation page: a *View details* button in the *Payments* column
  when payments of the link are contracts (paid through the wallet, or
  without any ISK). Its popup lists those contracts; before, only private
  contracts with items had one. Needs one recalculation: an older snapshot
  holds no count of contract payments and shows no button.
- Corporation page and settings tab *Friendly to hostiles*: the ISK,
  contract and contact tables show the standing the Alliance itself holds
  for the counterpart, its Corporation and its Alliance, as the Network table
  does; red text still marks a hostile one. Needs one recalculation: an older
  snapshot shows dashes.
- Ignoring a counterpart: the button is also in the ISK and contract tables
  of a Corporation page, and an ignored counterpart no longer counts for the
  markers ISK and Contracts either (mails still do) - before, it left only
  the Network. The popup asks for a reason; the list of ignored counterparts
  (now under *Hostile and data basis*) shows it with who and when, and the
  *Log* page records ignoring and taking back. Migration 0025 keeps the
  counterparts ignored before, without a reason.

### Changed

- Settings: the two help texts on the contact sources no longer speak of a
  "hostile list" - no page of that name exists, the sources decide who counts
  as hostile.

### Fixed

- *Log* page: an entry whose user was deleted since (the log keeps the entry
  and drops the user) broke the whole page with a server error. It shows "?"
  as *Changed by* now.
- Network: a highlight tile's *View details* searched for its name as a
  substring, so a short name also listed every longer name containing it -
  more rows than the tile counts. The link now names the party by its ID, and
  the search lists exactly the rows the tile counts.

## [0.1.4] - 2026-11-25

### Fixed

- Network: in the list of a Corporation's mains, a main whose partners had
  only plain payments (no trade, no contract, not shared, not hostile) showed
  no badge. A grey badge with the number of those partners is there now.

## [0.1.3] - 2026-11-24

### Changed

- The Network and the markers *ISK with hostiles* and *Contracts with
  hostiles* ignore public contracts: neither the contract nor the wallet
  entries that belong to it (journal `context_id` = a public contract) count.
  *Capital in contract* is unchanged - public contracts are what it looks at. Whoever takes a public contract is a stranger on the
  market, not someone the character chose to deal with. The wallet entries are
  matched against every public contract corptools holds, without the time
  frame, so a contract issued before the time frame and paid in it goes too.
  One that corptools does not hold still counts.

### Fixed

- Network: a contract assigned to a Corporation and accepted by one of its
  members counted twice - once for the Corporation, once for the member - so
  the Corporation reached two points, the default minimum, with one contract.
  Once accepted, only the acceptor is the contract's party now; before that
  the assignee.

- Network graph: lines between partners, Corporations and Alliances crossed
  into figure eights. vis-network's hierarchical layout stacks each column in
  the order of the data and its physics run then shuffles it further, with no
  regard to the lines. `network.js` now orders each column itself (the mean
  height of the neighbours, a few passes both ways, the order with the fewest
  crossings kept) and gives every node a fixed point; no physics run, so the
  graph also no longer moves after it is drawn. Lines of several alts to the
  same partners may still cross where no order avoids it.

## [0.1.2] - 2026-11-24

### Changed

- The Network counts connections instead of three kinds of rule. A payment, a
  contract without ISK and a private contract with items are one point each;
  a main shows up when its characters together reach *Network: minimum
  connections* (new setting, default 2, migration 0024) with one counterpart,
  or with one hostile Corporation or Alliance, all its members added up (a
  neutral one too with *Network: neutral partners too*, never a blue one).
  Before, "two characters with the same partner", one trade or one private
  contract was enough, and two payments of one character were not. A group
  that reaches the minimum shows the rows of all its members, so the table
  shows what added up. Highlights stay what they were and add nothing.
- A private contract with items and ISK is one point: the wallet entries that
  belong to it (journal `context_id` = the contract) still add their ISK to the
  row, but are no payments of their own - it would have counted twice.
- The calculation looks up the Corporation and Alliance of every counterpart
  of an account that has enough points in all, not only of those that met one
  of the old rules: a group can only be told from the affiliations. Expect
  more ESI name and affiliation requests per run (bulk, 1000 IDs each).

## [0.1.1] - 2026-11-24

### Changed

- Fewer ESI requests per run. A stored alliance or corporation history is
  asked again after a day only when it changed lately: only its last entry can
  still change, so the wait is a thirtieth of the time since that entry,
  between one day and one week. The Alliance's own Corporations (and a
  Corporation whose stored history still puts it in the Alliance) and a
  counterpart in one of its Corporations stay at one day, because the day one
  joins or leaves must show. A Corporation counterpart Auth has no Alliance
  for no longer costs a `get_corporation` call in every run: its Alliance is
  the last entry of the stored alliance history, which the tenure check
  needs anyway; NPC Corporations are not asked at all. Trade-off: a
  Corporation that moves into another Alliance after a long time without a
  change is seen up to a week late (`tenure.MAX_STALE`).

### Fixed

- A Corporation or character ESI answers with 404 (closed Corporation, deleted
  character) was never stored and came first in every run's list; five of
  them in a row stopped the refresh for everyone else. The 404 is now kept as
  an empty history and asked again only after a week.

## [0.1.0] - 2026-11-24

### Changed

- Network and markers decide by the counterpart's Alliance at the time, not by
  today's. A counterpart that was in a Corporation of the Alliance when the
  payment, contract or mail happened is a member then and counts nowhere, even
  when it is hostile today (a former member who left for a hostile Alliance no
  longer makes the old payments to him a finding). One that joined later counts
  for the time before it joined: with *Network: neutral partners too* such
  payments to today's members now show, before they were dropped as "inside".
  Hostility itself is still today's. The counterpart's Corporations come from
  corptools when it has a Character Audit, else from ESI's public corporation
  history, fetched by the calculation task once a day per character and kept
  in the new table `CharacterCorporations` (migration 0023; at most 500 per
  run); the Corporations' Alliances from the existing `CorporationAlliances`.
  Without a history the counterpart's Corporation and Alliance of today stand
  in. Only the counterparts left after the hostile filter are looked up, so
  most payments inside the Alliance need no request. Blue kills are unchanged:
  a victim in the Alliance at the time is the awox the marker is about.

## [0.0.47] - 2026-11-24

### Changed

- The Network graph colours a highlighted counterpart (Settings, *Highlighted
  counterparts*) red like a hostile one: the node itself, and a partner whose
  Corporation or Alliance is highlighted. Only the colours change; the hostile
  list, the Network's filter and the tables stay as they are.

## [0.0.46] - 2026-11-24

### Added

- The legend of the Network graph is clickable: Partner, Hostile partner,
  Corporation, Hostile Corporation, Alliance and Hostile Alliance each show or
  hide that kind of node, with the lines that end at it. A button *Show all*
  appears while something is hidden. Hidden nodes keep their place, so the graph
  does not move, and a Corporation whose partner is hidden stays until it is
  hidden itself. The choice holds for every account's graph on the page and
  ends with a reload. Main, Alt and the lines are not switchable: without the
  main the graph has no anchor. One new text (*Show all*).

## [0.0.45] - 2026-11-23

### Changed

- Network and markers count only what a character did while it was in a
  Corporation of the Alliance: payments, contracts, mails and blue kills from
  before it joined or after it left no longer count (ISK with hostiles,
  Contracts with hostiles, Mails with hostiles, Blue kills, and the Network's
  payments and contracts). Before, everything within the time frame counted,
  whatever Corporation the character was in at the time - a main that joined
  last month brought its old trading partners along. The Corporations a
  character was in come from corptools; whether a Corporation was in the
  Alliance back then comes from ESI's public alliance history of that
  Corporation, which the calculation task fetches once a day and keeps in the
  new table `CorporationAlliances` (migration 0022; at most 500 Corporations
  per run, the rest the next run). Without a history the present stands in:
  a character corptools has not read counts through its current Corporation,
  a Corporation ESI could not be asked about counts when Auth has it in the
  Alliance. The first calculation after the update needs ESI and takes longer.
  A blue kill copied before this change stays stored (the Blue kills settings
  tab still lists it) but no longer counts.
- Highlights moved from the Markers page to the Network page, above the
  Corporations. The Network page also carries the search box now; its result
  is still the page *Network search*, which no longer has a menu entry of its
  own (the *Network* tab stays current there).

### Fixed

- Network: the Alliance can no longer be a counterpart. A character Auth does
  not know, whom ESI puts into the Alliance or one of its Corporations, stayed
  a counterpart (Auth only drops the characters it knows), so the Network, its
  search and the highlight choices offered the own Alliance. Such a partner is
  a member now and dropped; a snapshot made before still holds it until the
  next calculation, but the search and highlight choices leave the Alliance
  and its Corporations out at once.

## [0.0.44] - 2026-11-23

### Added

- Network: private contracts with items are a kind of their own next to
  *Shared payment partner* and *Player trading*. Every contract corptools holds
  with availability *personal* and at least one item shows an account on its
  own, with or without ISK, in any status. Before, a gift of items only counted
  as a payment of 0 ISK and needed two own characters with the same partner; a
  contract without items, or a public one, is unchanged. The table has a new
  column *Private contract* with a *View details* button that opens the
  contracts with their items in the popup of the Markers page
  (`network/contracts/<character>/<counterpart>/`, `view_suspects`, only for a
  pair the stored Network lists with contracts). The graph draws the contracts
  as a line of their own, and the legend and badges have an entry.
- Network graph: arrowheads follow the giver - to the partner when the own
  character paid or issued, to the own character when it was paid or handed a
  contract, both ways for both; the lines to alts and Corporations point away
  from the main and the partner. The direction is stored per link, so a
  snapshot made before shows no arrowheads until the next calculation.
- Network table: new column *Age*, the age of the own character from Auth's
  birthday (the date as tooltip, sortable; a dash when Auth has none). It is
  read with one query when the page is shown and not stored in the snapshot.

## [0.0.43] - 2026-11-23

### Added

- Page *Network search* (`network/search/`, own menu entry, `view_suspects`):
  one search box over the Network tables of every Corporation. It finds the
  rows whose counterpart, its Corporation or its Alliance has the typed text
  in its name; the own characters of an account are not searched, since the
  other side is what makes an account stand out. The box is the app's Tom
  Select, filled with every party of the stored Network grouped as Character,
  Corporation and Alliance; a typed text is kept as it is, so part of a name
  works too. The result table lists the same columns as the Network page plus
  the main and its Corporation, and the main links to its Corporation's
  Network page with that main already open (`#main-<id>`). It reads the
  stored snapshot only.
- Markers page: a section *Highlights* above the Corporations. The new
  setting *Highlighted counterparts* (Settings, tab *Alliance*, section
  *Highlights*; migration 0021, default empty) takes characters, Corporations
  and Alliances out of the parties the stored Network holds. Each gets a tile
  with the standing the Alliance holds for it (and the hostile standing, if
  it has one), its Corporation and Alliance with theirs, and the number of
  mains that deal with it - the party itself, or any counterpart it is the
  Corporation or Alliance of. The tile links to the Network search with the
  name filled in. Without a highlight the page is as before. It searches the
  Network only: a party the Network does not hold (neutral and blue ones
  unless *Network: neutral partners too* is on) shows 0 mains. A highlight
  is kept by EVE ID with its name, so one that has left the snapshot keeps
  its tile and stays selectable; the names offered come from the snapshot.

## [0.0.42] - 2026-11-23

### Added

- Network table: next to the *Counterpart*, its *Corporation* and its *Alliance*
  a badge shows the standing the Alliance itself holds for that party - or a
  dash when it holds none - coloured by EVE's bands (blue from +5, light blue
  above 0, grey at 0, orange above -10, red at -10). Until now only a hostile
  Corporation or Alliance showed a standing at all, and that was the lowest of
  every ticked source, so a neutral or friendly party showed none. It is the
  Alliance's own contact list only: a Corporation source's private standing is
  not what the Alliance holds. The snapshot stores the standings of the parties
  of the table (`standings`, no migration); one stored by 0.0.41 or older shows
  dashes until the next recalculation. The other tables keep their red badge
  with the hostile standing.

## [0.0.41] - 2026-11-23

### Added

- Network: a button next to a row's *Counterpart* (only with
  `manage_settings`) ignores that counterpart. A popup asks first and names
  it; on *Ignore* the counterpart goes into the new setting *Ignored
  counterparts* (migration 0020, default empty) and the Network is
  recalculated at once. An ignored counterpart is no connection at all: it
  counts for neither the shared-partner rule nor player trading, so an
  account that showed up only through it leaves the Network. The ISK marker
  is untouched. It is kept by EVE ID, the name is stored beside it - an
  ignored counterpart leaves the snapshot, so the settings could not name it
  otherwise. Settings, section *Network*: the list appears once one is
  ignored; removing an entry and saving takes it back. The view takes the
  name from the stored result, not from the post, and refuses an ID the
  Network does not list.

## [0.0.40] - 2026-11-23

### Changed

- Settings: the two lists of *Ignored characters* offer only the characters
  that have a finding in the last calculation - a friendly hostile contact
  for *Friendly to hostiles*, a link to a hostile partner for the Network -
  plus the IDs already stored. Before, they offered every character of every
  checked account, a list that grows with the Alliance. An ignored character
  leaves the findings, so the stored IDs stay in the list or it would
  vanish the moment it is saved. A result of another Alliance is not read;
  before the first calculation only the stored IDs are offered. A character
  whose finding went away on its own is not offered any more.

## [0.0.39] - 2026-11-23

### Added

- Settings: *Ignored characters* for *Friendly to hostiles* and for the
  Network, one list each (migration 0019, default empty). A character the
  list names is a source of no finding: its contacts are not checked for
  friendly hostiles, respectively its payments and contracts leave the
  Network. Its alts and its main stay checked, so a partner the account's
  other characters share still shows. The ignored character stays known as
  the account's own: a payment to it from another alt is no connection
  outside. Picked from every character of the checked accounts (an alt with
  its main); a stored ID no account holds any more stays selectable.

### Changed

- Settings, tab *Alliance*: grouped in sections with a heading, in the order
  of the work - *Alliance*, *Hostile and data basis* (hostile standing, time
  frame, ignored wallet types: shared by Markers and Network), *Markers*
  (Blue kills, Capital in contract, Frequent Corporation changes, Friendly to
  hostiles) and *Network*. Before, twelve fields stood in one list.

## [0.0.38] - 2026-11-23

### Added

- Network: contracts without ISK count as payments. A gift of items
  (price, reward and collateral 0) leaves no journal entry with the partner,
  so two characters handing items to the same outsider never showed up. They
  are read from corptools' contracts - every type and status, issued,
  assigned or accepted, within the time frame by the issue date - and count
  like a payment of 0 ISK, with the same two-character rule. A contract with
  any ISK stays with the journal; collateral included, which has journal
  entries of its own, so nothing counts twice.
- Network: setting *Network: neutral partners too* (default off, so nothing
  changes until switched on) and *Network: blue above standing* (default 0;
  migration 0018). Switched on, partners without a hostile standing stay
  too; one goes only when it, its Corporation or its Alliance is above the
  blue standing at a ticked source and none of the three is hostile.

## [0.0.37] - 2026-11-23

### Added

- *Capital in contract*: a copy button next to *View details* and in the
  contract's popup puts the in-game link on the clipboard
  (`<url=contract:0//ID>ships</url>`), to paste into EVE's chat or a mail
  and open the contract with a click. The solar system is `0`: the client
  ignores it (tried in game with a wrong one and with 0), and a structure's
  system is unknown without a token. The link text is the ships of the
  *Ships* column, never empty unlike the title. The ISK marker's contract
  popup gets no button: corptools' contracts are private, nobody else could
  open them. The copying is Alliance Auth's clipboard.js bundle, as in
  eos-invoices (`copy.js`).

## [0.0.36] - 2026-11-21

### Added

- Page *Statistics* (`statistics/`): the numbers of the last contract sweep -
  regions asked and failed, public contracts listed, contracts of the
  Alliance, their issuing characters and Corporations, new and gone
  contracts, new contracts whose items could not be fetched - and the
  Alliance's contracts per region and per Corporation. The sweep counts what
  it fetches anyway, no extra ESI call, and keeps only its last run
  (`SweepStats`, migration 0017). The contracts gone are counted without
  their items: `delete()`'s total would add those.

### Changed

- The review log moved from the settings tab *Log* to its own page *Log*
  (`log/`) next to *Statistics*; the settings keep their review tabs *Blue
  kills* and *Friendly to hostiles*. Both pages need `manage_settings` and
  `view_suspects`, as the tab did; the menu shows them only then.

## [0.0.35] - 2026-11-20

### Fixed

- The capital sweep no longer keeps contracts that were accepted or
  withdrawn until they expire. django-esi sends the ETag of the last answer
  and keeps it for seven days, so from the second sweep on every region
  whose list had not changed answered 304; the sweep took that as a failed
  region and then never dropped a contract that was no longer listed. Both
  calls now ask without ETag and without storing the answer in the cache:
  the sweep needs the full list to see what is gone, and a contract listed
  again after its row went would otherwise get a 304 for its items and
  never be stored.
- A region that fails is asked once more at the end of the same sweep
  instead of waiting a day. django-esi 10 retries no timeout and no 5xx:
  aiopenapi3 wraps both in its own exceptions, which django-esi's retry
  check does not recognise.
- ESI's error limit (420) no longer turns the rest of the sweep into failed
  regions: the sweep stops, and the task (now `bind=True` with django-esi's
  `rate_limit_retry_task`, as Alliance Auth's own ESI tasks) runs again after
  the reset.
- README: a sweep takes about 120 requests (measured on `aa_dev`), not 150
  to 400; the public contract endpoints have no ESI rate-limit bucket.

## [0.0.34] - 2026-11-19

### Changed

- *Capital in contract* no longer reads corptools. A daily sweep
  (`tasks.sweep_capital_contracts`, `capital_sweep.py`) asks ESI's public
  contracts of every region of known space, keeps those issued by a
  Corporation of the Alliance and fetches the items of each once, into the
  new tables `CapitalContract` and `CapitalContractItem` (migration 0016).
  The marker reads them, so it also finds contracts of members without a
  token or a Character Audit. The sweep needs no token; the admin adds the
  beat entry from the README. The data is up to a day old, the expiry is
  checked on every calculation, and a contract no longer listed is dropped
  when every region answered. The popup behind *View details* reads the
  same table. The place is the region and the station; a structure shows as
  its ID.
- The capital ship groups setting and the marker's rules are unchanged;
  `for_corporation` no longer matters, the issuer's Corporation does.

## [0.0.33] - 2026-11-19

### Added

- The *Capital in contract* table has a *Contract* column with a *View
  details* button. A row only named the ship and the price, so the reviewer
  could not see what else the contract holds or who it is made out to
  without opening EVE. The button reuses the ISK marker's popup
  (`contracts.js`, `partials/contract-details.html`) through a view of its
  own, `capital_contract`: the ISK popup is keyed by character and
  counterpart and a capital contract has no counterpart. The view serves
  only an ID that a capital row on a tile the viewer sees lists, so it opens
  no other contract of corptools. No live check on page load: a contract
  corptools no longer holds shows the popup's "has not stored" hint; a row
  of an older snapshot without `contract_id` shows a muted icon instead of
  the button.

## [0.0.32] - 2026-11-19

### Added

- Marker *Capital in contract*: a character of the account offers a ship of
  a chosen capital group in an open, public contract. Open means
  `outstanding` **and** `date_expired` in the future - ESI leaves an expired
  contract on `outstanding`, so the status alone would mark it for ever.
  Only ships the contract offers count (`is_included`), not those a
  want-to-buy asks for; a contract made in the name of the Corporation
  counts; a contract lying at several characters of the account counts once
  and only for its issuer's account. It needs no hostile list and has no
  time frame: an open contract is always current. The Corporation page shows
  a table per contract (ships, type, price, buyout, location, dates, title).
  eos-auth-monitor shows the marker through `api.py` without a change.
- Setting *Capital ship groups* (migration 0015), chosen like *Ignored ships*
  from the ship groups of eve_sde; default Dreadnought, Lancer Dreadnought,
  Carrier, Command Carrier, Force Auxiliary, Supercarrier, Titan and Capital
  Industrial Ship. Groups, not types: a new hull of a group counts without
  a change here. Freighters and Jump Freighters can be added.

### Changed

- Blue kills on the Corporation page: a day whose kills are all cleared is
  folded to its day row, a click on the date unfolds it. A long list of
  cleared days pushed the open kills out of sight; a day with an open kill
  stays open.

## [0.0.31] - 2026-11-19

### Added

- Visitors: a marked account with an alt in a Corporation whose main is
  elsewhere now shows on that Corporation's page as well, in its own block
  *Alts of mains in other Corporations* below the mains - its main, the
  main's Corporation, its alts there and all its markers with everything
  found. The page listed only the mains of the Corporation, so its CEO
  never learnt of a marked alt in it, though he answers for it. Read only
  there; for `view_suspects` the main's Corporation is linked. The head of
  the page and each tile count the visitors, a tile with one is no longer
  *clean*, the menu badge counts them for the CEO and every account once
  for `view_suspects`, the contract popup opens for them, and
  `api.character_markers(corporation_id=...)` gives their characters too.
- Accounts whose main is outside the Alliance are checked when one of
  their characters is in a Corporation of the Alliance: the calculation
  took only accounts with the main inside, so such a player was never
  checked at all. They show as visitors, on the network pages at their
  alts' Corporations, and are reviewed in the settings tabs. Needs a
  recalculation after the update.
- README: give `view_own_corporation` to a group, never to a state.

### Removed

- Permission `view_evidence`. It held the counterparts of mails, ISK and
  contracts, the contract popup and the network pages back from
  `view_suspects`, but nobody held `view_suspects` without it, and
  eos-auth-monitor demanded it too for marker labels that carry no
  evidence. `view_suspects` now opens all of it; `view_own_corporation`
  is unchanged. Migration 0014 only drops the permission from the model:
  Django keeps the existing row with its assignments, without effect,
  until an admin deletes it. Release together with eos-auth-monitor
  dropping it from its spy check.

## [0.0.30] - 2026-11-17

### Added

- `api.character_markers()` takes an optional keyword `corporation_id`.
  The API gave only the whole Alliance, so eos-auth-monitor could not
  show a CEO with `view_own_corporation` the markers of their own
  Corporation without showing all the others. With the argument it gives
  exactly what that Corporation's page shows - the snapshot entry with
  that id, its mains with all their characters - and nothing for a
  Corporation without a page. Without it nothing changes.

## [0.0.29] - 2026-11-17

### Added

- Permission `view_own_corporation` for Corporation CEOs (migration 0013,
  which only adds the permission). Every other permission showed the whole
  Alliance, so a CEO could only be given all Corporations or none. It
  opens the Corporation page of the user's main's Corporation - with its
  evidence (mail, ISK and contract counterparts, the contract popup) - and
  nothing else: another Corporation's page answers 404, and the tiles of
  the Alliance, the network pages, *Recalculate*, the settings and the
  note and *Cleared* controls stay closed. The start page and the
  *Markers* menu lead straight to that Corporation, the menu badge counts
  its mains only. Held together with `view_suspects`, it only adds the
  evidence of the own Corporation. The app assigns it to nobody: the admin
  gives it to a CEO group or state.

### Fixed

- The *Reason* column of the blue kill tables read "Reason" in Chinese
  instead of ours: eos-tax now ships a plain "Reason" left in English, and
  being earlier in `INSTALLED_APPS` its catalogue won. The heading carries
  the `eos-spy-network` context, like the other short words another app
  translates differently.

## [0.0.28] - 2026-11-13

### Added

- Friendly to hostiles (Corporation page and settings tab): a column
  *Reference standing* before the member's own, now headed *Suspect
  standing*. The table showed only the standing the member gave the
  contact, not how hostile the contact is: +10 towards a -10 reads
  differently than towards a -1. The reference is the lowest standing the
  ticked sources hold against the contact - or, for a contact hostile only
  through it, against its Corporation, else its Alliance; a tooltip names
  each source with its value. Stored with the calculation: a snapshot made
  before shows "–" until the next run.

### Changed

- Blue kill tables (Corporation page and settings tab *Blue kills*): the
  columns after *Victim* are headed *Victim Corporation* and *Victim
  Alliance*. Headed plain *Corporation* and *Alliance*, right after the
  member's character, they read as the member's own.

## [0.0.27] - 2026-11-13

### Added

- Corporation page: a card *Cleared findings* at the foot. A main whose
  every blue kill and friendly hostile contact was cleared dropped out of
  the table, and with it its cleared findings and their notes were nowhere
  on the page. Now each such main is a folded group (name, number of
  findings); inside one table for both markers with date, finding (zKB
  link for a kill), characters and note, read only. A search box above
  unfolds the groups whose main, finding or note matches and hides the
  rest. Built from the same snapshot and reviews, no extra query; a main
  marked only by switched-off markers stays out.

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
