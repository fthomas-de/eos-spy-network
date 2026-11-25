# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-11-25 (version 0.1.4, tag `v0.1.4`).

## State

- Version `0.1.4`, 2026-11-25 (see `CHANGELOG.md`): a main of the Network Corporation page whose partners had only
  plain payments showed no badge in the list. `Connections.paying` (counterparts with a payment and no trade,
  per link, as the graph's payment edges) gives a grey `text-bg-secondary` badge titled *Payments* in the list and
  in the card header (`network_corporation.html`); no new text. User's choice (2026-11-25): the Corporation tile
  on the Network page gets no Payments row (`payments_count` is not in the snapshot). A partner traded with from
  one character and only paid from another is in both `paying` and `trading` (per link, not per partner). Test:
  `TestPlayerTrading.test_should_list_a_plain_payment_partner_apart_from_a_trading_one`, not checked red by hand
  (it needs `paying`, so it fails without it). Suite 603 without translation tests, green. Prod: no migration, no
  static file, no recalculation (the property reads the stored links). Not seen in a browser.
- Remote was at 0.1.3 (0.1.2 and 0.1.3 pushed 2026-11-24 together, only `v0.1.3` tagged). Prod for those: run
  migration 0024, `collectstatic` (`network.js`), recalculate once. Expect fewer Network accounts, fewer ISK
  and Contracts markers (public contracts gone), and a graph without figure eights.
- Version `0.1.3`, 2026-11-24 (see `CHANGELOG.md`): public contracts out, double count fixed, graph order.
  - `markers.PUBLIC` and `markers.without_public_contracts(entries)`: drops journal entries with
    `context_id_type == "contract_id"` whose context is any public `Contract` corptools holds (subquery, no time
    frame - a contract issued before the time frame and paid in it goes too; one corptools does not hold still
    counts). Used by `markers._check_wallet` and `network.connections`; `_check_contracts` and the Network's
    contract query `.exclude(availability=PUBLIC)`. *Capital in contract* unchanged (public contracts are its point).
  - Network: a contract's party is `acceptor_id or assignee_id` (plus the issuer), no longer both - a contract to
    a Corporation accepted by a member scored the Corporation twice and reached the default minimum of 2 alone.
  - `network.js`: `place(graph)` orders each column by barycentre (8 sweeps alternating, fewest crossings kept),
    nodes get fixed `x = level * LEVEL_SEPARATION (320)`, `y` from `place`; `physics: false`, no hierarchical
    layout, then `fit()`. Checked in a browser only with a synthetic graph served as a static page; alts sharing
    partners may still cross where no order avoids it.
  - Tests: `TestPublicContracts`, `TestContractParty`, one more in `TestMinimumConnections` (`test_network`); three
    in `test_markers` (`TestWallet` public/private price, `TestContracts` public). All mutation-checked red.
    Suite 602 without translation tests, green. No new texts. Point "contract issued before joining, paid after"
    was looked at and left as is (user).
- Version `0.1.2`, 2026-11-24: *Network by points* (user). `network._cut(account, minimum, blues)`
  replaces the three rules: `Link.points` = payments + contracts; the points of every link count for the
  counterpart and for each Corporation/Alliance of its chain that is in `account.hostiles` or, with `blues` (the
  neutral switch), not blue; whatever reaches `minimum` keeps the links of all its members. Setting
  `SpyConfiguration.network_min_connections` (default 2, 1-100, migration 0024, applied to `aa_dev`;
  `snapshot._inputs`, form, Network section of the settings). `connections(..., minimum=1)` cuts only by the
  account's total (no group can score more, no affiliations needed yet); `drop_ours(..., minimum, blues)` does the
  real check after `kept_partners` and the replay. `snapshot.build` computes `blues` once for both.
  - A private contract with items counts once: `connections` reads the contracts first and `counted` holds their
    `contract_id`s; a journal entry with `context_id_type == "contract_id"` and a context in `counted` goes in as
    `Link.add(..., with_contract=True)` (ISK, direction, dates, no point; stored in `events` for the replay).
  - `Connections.shared/trading/contracting` stay, only as the badges' descriptions (no longer a rule).
  - Highlights do not score (user: they are links to important counterparts, not a calculation basis); their
    choice list is still the stored Network, so a party below the minimum cannot be picked.
  - Tests: `TestMinimumConnections` (15), `NetworkTestCase` runs with `network_min_connections=1` (most fixtures
    are one connection), `connections`/`drop_ours` default to 1; `TestNetworkPages` and the visitors' `trade()` set 1.
    Eight mutations checked red; not red: `snapshot.build` leaving `minimum` out of `connections` (only
    an optimisation, the final check is in `drop_ours`). Real ESI cost not measured: every counterpart of an
    account with enough points in all is now looked up, not only the ones that met an old rule.
  - Prod: migration 0024, recalculate. Expect other accounts than before: a single trade or private contract no
    longer shows, two payments of one character do.
- Version `0.1.1`, 2026-11-24: fewer ESI requests (user asked to buffer the new calls).
  - `tenure._stale(row, now, daily)`: a stored history is trusted for a thirtieth of the time since its last entry,
    between `STALE_AFTER` (1 day) and `MAX_STALE` (7 days); an empty history (ESI 404, or a Corporation never in an
    Alliance) waits `MAX_STALE`. Daily regardless: `first` (Auth's `corporations_now`) and a row whose last value
    `daily` accepts (`_histories`: last Alliance is ours; `Tenure.prepare`: counterpart's last Corporation is ours).
  - `_esi_alliance_history` / `_esi_corporation_history` return `[]` on a 404 (`_not_found`, `status_code` of the
    exception), `None` stays "could not ask"; `_refresh` stores `[]` rows but leaves them out of its answer, so
    callers still fall back to today's data. Before, a dead ID was never stored, sorted first every run and five of
    them tripped `MAX_FAILURES`.
  - `affiliations._esi_corporation_alliance` (`get_corporation`) is gone: `resolve` takes the Alliance of a
    Corporation counterpart Auth has none for from `tenure.current_alliances` (last entry of the stored alliance
    history, ESI only when stale; NPC Corporations skipped). First sight of a Corporation now costs one request, not two.
  - Not done on purpose: no table for names or character affiliations - both are bulk POSTs (1000 IDs per request),
    a few requests per run, a table would save little. Point 4 of the proposal (ask only when an event is newer than
    the stored history) was left out: `Tenure` would need the event dates first.
  - Tests: 12 new (`TestCorporationAlliance` 4 in `test_affiliations`, five in `test_tenure.TestLoad`,
    `TestEsiAnswers`, two in `TestPrepare`); `SpyTestCase` no longer patches `_esi_corporation_alliance`. Eight
    mutations checked red. Suite 577 without translation tests, green. Not measured on prod: how many requests a run
    saves; a log line per request would give the number.
  - Prod: no migration. Expect the first run after the update to ask as before for Corporations with no stored row.
- Version `0.1.0`, 2026-11-24: *Counterpart by its Alliance at the time* (user).
  - `tenure.Tenure.was_ours(eve_id, when)` (character through its Corporation records, Corporation through
    `alliances`/`corporations_now`, the Alliance ID itself; undated = today; unknown = outside) and
    `Tenure.prepare(ids, entities=None)`: resolves unknown IDs (`affiliations.resolve`, ESI names/affiliations
    in the task), Corporations from corptools' `CorporationHistory` (audit) else `CharacterCorporations`
    (new model, migration 0023, applied to `aa_dev`) via ESI `GetCharactersCharacterIdCorporationhistory`,
    fallback the entity's Corporation of today from the beginning; an entity whose Alliance today is ours puts
    its Corporation into `corporations_now`. `prepared` remembers looked-up IDs (a Corporation ESI fails on is
    not asked twice per run). `_histories` now goes through the generic `_refresh(model, ids, fetch, first)`.
  - Network: `connections(..., tenure=)` uses `tenure.was_ours(party, date)` instead of today's
    `alliance_ids` (kept only without tenure); `Link.events` (not stored) keeps each `add`;
    `network.drop_ours(accounts, tenure, entities)` after `kept_partners` (whose `inside` parameter is gone)
    replays the events without the ones while the counterpart was ours and re-applies the rules (`_cut`,
    shared with `connections`).
  - Markers: `counterparts(user_id, when, *ids)` drops a hostile that was ours then; `_check_mails/_wallet/
    _contracts` read their rows into a list and `prepare` the hostile parties first. Blue kills unchanged
    (awox is the point), contacts and membership unchanged.
  - Tests: `TestWasOurs` (3), `TestPrepare` (4) in `test_tenure`, `TestCounterpartTenure` (3) in `test_network`,
    three in `test_markers.TestTenure`; `SpyTestCase` patches `tenure._esi_corporation_history` (None). Nine
    mutations checked red (two tests had to be rewritten first: the network one went through the markers'
    `prepare`, the once-per-run one through `characters`). Suite 565 without translation tests, green
    (fresh test database once, then kept). Real run on `aa_dev` 0.58 s, no counterpart looked up (no hostile
    partner there). No new texts, no template or static change.
  - Prod: migration 0023, recalculate. The first run asks ESI for the corporation history of every remaining
    counterpart corptools has no audit of (hostile ones, plus all neutral ones with *neutral partners too*).
- Version `0.0.45`, 2026-11-23 (see `CHANGELOG.md`), four requests of the user:
  - *Own Alliance is no counterpart*: `network.kept_partners(accounts, blues=None, inside=frozenset())`
    drops a partner whose chain (`Connections.chain`: itself, its Corporation, its Alliance, as `affiliate`
    found them) holds one of `inside`; `snapshot.build` passes the Alliance ID and the IDs of its tiles.
    `Report.parties` leaves them out as well, so a snapshot made before shows no own Alliance in the search
    suggestions or the highlight choices (`forms.network_parties` reads `parties`).
  - *Only what was done while the character was in the Alliance* (`tenure.py`, new): `tenure.load(config,
    roster.characters, since)` -> `Tenure.counts(character_id, when)`. Corporations of the character from
    corptools' `CorporationHistory` (a character without any: its current Corporation from the beginning);
    whether the Corporation was in the Alliance then from `CorporationAlliances` (new model, migration 0022,
    applied to `aa_dev`): ESI's public `GetCorporationsCorporationIdAlliancehistory` through an own
    `ESIClientProvider` (as `capital_sweep`), refreshed when older than a day, NPC Corporations and ones outside
    the time frame skipped, at most `MAX_PER_RUN` (500) per run, stop after `MAX_FAILURES` (5) failures in a
    row; no stored row -> Auth's alliance of today (`corporations_now`). Used by `network.connections(...,
    tenure=)` (journal and contracts), `markers._check_mails/_wallet/_contracts/_kills`, `_copy_kills` (an
    out-of-time kill is not copied; one copied before is hidden in `_check_kills`; the Blue kills settings tab
    still lists it). `snapshot.build` loads it first (new step `tenure`, first in `progress.STEPS`).
    `tests.base.SpyTestCase` patches `tenure._esi_alliance_history` (None = ESI unavailable).
    Not touched: Membership, Corporation changes, Contacts (no date), Capital contracts (open now), the
    contract popups (they read corptools at the click, unfiltered).
  - *Highlights* moved from `corporations.html` to `network.html` (view `network` passes `highlights`);
    *Search*: the select form sits on the Network page (copy of the one on `network_search.html`, no shared
    partial on purpose - no new files without asking), `action` = the search page; the menu entry is gone and
    the search page uses `NAV_NETWORK`.
  - Tests: `test_tenure.py` (new, 13), `TestTenure` and `TestOwnAlliance` in `test_network` (10), `TestTenure`
    in `test_markers` (5), `TestKillsTenure` in `test_kills` (3), changes in `test_network_search`,
    `test_visitors` (a main outside the Alliance paying now counts nothing: the payment moved to the alt in
    the Alliance), `test_progress`. Suite: 550 without translation tests, green (fresh test database);
    14 mutations checked red. Real run on `aa_dev`: 0.7 s,
    one Corporation history fetched. Not seen in a browser (SSO): the search box on the Network page (Tom
    Select there), the highlights above the tiles.
  - Two glossary texts, machine-translated, not reviewed by the user: *Reading Alliance histories* (progress
    step) and the changed help text of *Highlighted counterparts* ("... tile on the Network page ...").
  - Dev instance: migration 0022 applied to `aa_dev`; `CorporationAlliances` holds the one history the real
    run fetched; no Celery worker runs there. Trap of this session: WSL restarted uncleanly after the commit
    and left the new git objects empty (the commit was unreadable, `git fsck` red); repaired by resetting
    `main` to the previous commit, deleting the 0-byte object files and committing again, then `sync`. After
    a commit, `sync` costs nothing; check `git fsck` once if WSL restarted meanwhile.
  - Prod: run migration 0022; no static file; recalculate once. The first run asks ESI for the alliance
    history of every Corporation any account character was in within the time frame (up to 500 per run, so
    a large Alliance may need a few runs before every history is stored; until then the present stands in).
    Expect fewer markers and Network accounts than before: a main that joined recently no longer brings its
    old partners. ESI's cache may delay a Corporation that joined the Alliance today by a day (its first
    day's payments then do not count until the history is refreshed).
- Version `0.0.44`, 2026-11-23 (see `CHANGELOG.md`): Network, three requests of the user.
  - *Private contract* as a third kind of link (`network.PRIVATE = "personal"`, `Link.contracts`,
    `Connections.contracting`): a corptools `Contract` with availability personal and at least one
    `ContractItem` (`Exists` annotation), any type/status, with or without ISK; it counts alone
    (`keep = shared | trading | contracting`) and no longer as a 0-ISK payment. Everything else is as
    before (no items or public = payment of 0 ISK without ISK). Popup: `views.network_contracts`
    (`network/contracts/<char>/<counterpart>/`, `view_suspects`, 404 unless the stored Network has a
    link with `contracts`), `contract_details.private()` reads the contracts from corptools at the
    click and renders `partials/contract-details.html`; `contracts.js` and its modal sit on
    `network_corporation.html`. Tile list and badges got an entry (`text-bg-primary`), legend class
    `contract-edge`, graph edge kind `contract`.
  - Arrowheads: `Link.direction` ("o" own character gave: negative journal amount or issuer of the
    contract; "i" received; both letters sorted), stored as the 9th value of a snapshot link
    (`[..., first, last, contracts, direction]`; older snapshots read without, no arrowheads until a
    recalculation). `network.js`: `arrows: {to, from}` on payment/trading/contract lines, `to` on
    account and membership lines.
  - Column *Age* (`Connections.birthdays`, `network.fill_birthdays`, one query in
    `views.network_corporation` only, so the search page rows carry `birthday` None): `timesince`
    of `EveCharacter.birthday`, date as tooltip, `data-order` in days, dash when Auth has none.
  - Tests: `TestPrivateContracts`, `TestDirection`, `TestAge` (`test_network`), eight in
    `TestNetworkPages`; seven mutations checked red (not the new permission guard of the popup).
    Suite at the commit: 515 without translation tests, green (fresh test database); `collectstatic`
    run. Not seen in a browser (SSO): arrowheads, the contract line colour, the popup, the column.
    4 new glossary texts (Private contract, Private contracts with items with characters outside
    the Alliance., Arrow: from the giver to the receiver, Age), machine-translated, not reviewed by
    the user. *Age* carries the `eos-spy-network` context in the template (Alliance Auth's "Age"
    differs in zh_Hans and turned the catalogue test red).
    Prod: no migration, `collectstatic`, recalculate once (arrowheads and the contract kind need a
    new snapshot); expect more accounts, one private contract now suffices.
- Version `0.0.43`, 2026-11-23: *Network search* and *Highlights*.
  - `views.network_search` (`network/search/`, nav key `network_search`, `view_suspects`) and
    `templates/.../network_search.html`: a GET form with one `<select name="q">` that
    `searchable.js` turns into Tom Select (no new JS file; `data-eos-spy-network-create` keeps a
    typed text). `Report.search(q)` (counterpart, Corporation, Alliance names, casefolded
    substring; own characters not searched), `Report.suggestions()` (names grouped Character /
    Corporation / Alliance), `Report.parties` (cached: ID -> name, category of every counterpart
    and its chain). Rows link to `network_corporation/<tile>#main-<id>`.
  - `SpyConfiguration.highlight_counterparts` (JSON dict `{"<EVE id>": "<name>"}`, migration 0021,
    applied to `aa_dev`), form field with Tom Select, choices from `forms.network_parties(config)`
    (the stored Network) plus the stored ones; the stored name wins. `Report.highlight_tiles(dict)`
    gives per party: standing held, hostile standing, `groups` (its Corporation/Alliance with
    theirs), `accounts` (distinct users whose counterparts have it in their chain). Markers page:
    section *Highlights* above the Corporations (headings only when a highlight exists),
    `partials/highlight-tile.html`; tile link = search with `?q=<name>` (a substring search, so a
    short name may list more rows than the tile counts mains). New partial
    `partials/standing-badge.html` (the three older copies of that badge were left alone).
  - Decided (user, 2026-11-23): Network data only - a neutral or blue party the Network does not
    hold shows 0; no free names in the settings; count = mains; own page for the search.
  - Tests: `test_network_search.py` (22; six mutations checked red, the permission guards not).
    Affected modules 198 green; whole suite not run. Not seen in a browser (SSO): the Tom Select
    box (Enter on a typed partial text picks the first suggestion, "Add ..." keeps the text),
    the tiles. 9 new glossary texts (Network search, Highlights, Highlighted counterparts + help
    text, Counterpart, Corporation or Alliance, Search, Corporation of the main, Nothing in the
    Network matches., the search hint), machine-translated, not reviewed by the user. Suite at
    the commit: 491 without translation tests, green (fresh test database). On prod: run
    migration 0021, no static file; nothing shows until a highlight is picked. A counterpart's name that only ESI knows shows as its ID in the
    Network (`_fill_names` falls back to the ID, the entity's ESI name is unused) - so the
    search cannot find it by name; left as is.
- Version: `0.0.42`, 2026-11-23 (see `CHANGELOG.md`): the Network table shows
  the standing the Alliance itself holds for each party.
  - `hostiles.alliance_standings(config)`: the Alliance's own contacts
    (`ContactSource` of kind alliance, unsaved, as `blue_entities`), every
    standing, by EVE ID. Corporation sources never count (test red against
    `ContactSource.objects.all()`). `snapshot.build` keeps only the IDs in
    `entities` and stores them as `data["standings"]` (`[[id, "-10.0"]]`);
    `Report.standings` reads them with `data.get`, so an older snapshot shows
    dashes until the next run. `Connections.standings` is set in
    `Report._network_tile` only; `rows` gains `counterpart_held`, `_group`
    gains `held` (next to the hostile `standing`, which stays).
  - Templates: `group-cell.html` has the parameter `with_held`; only
    `network_corporation.html` sets it. The badge (EVE bands: >=5 primary,
    >0 info, 0 secondary, >-10 warning, else danger; dash when none) is
    written out twice (counterpart cell, group cell) because the user wants
    no new files without asking. Red text still marks a hostile party; a
    party hostile only through a Corporation source gets a dash.
  - Tests: four in `TestHostileChain` (`test_network`), one in
    `TestNetworkPages` (`test_views`); `TestQueries` now expects 3 reads of
    the Alliance contacts. Suite at the commit: 469 without translation
    tests, green (fresh test database). 1 new glossary text ("Standing held
    by the Alliance"), machine-translated, not reviewed by the user. Not seen
    in a browser (SSO).
- Before (0.0.41), 2026-11-23: button *Ignore this
  counterpart* on the Network Corporation page.
  - `network_corporation.html`: next to each row's *Counterpart* a button
    (`perms.eos_spy_network.manage_settings`; the page itself needs
    `view_suspects`) opens one Bootstrap modal that names the counterpart and
    asks; `static/.../js/ignore.js` fills it (`show.bs.modal`,
    `event.relatedTarget`, `textContent`). The row dict has `counterpart_id`
    now (`network.Connections.rows`).
  - `views.ignore_counterpart` (`network/ignore/`, POST,
    `all_permissions_required(MANAGE_SETTINGS, VIEW_SUSPECTS)`): the ID must be
    a counterpart of a stored Network account (404 otherwise, 400 for a bad
    number), the name is the stored one, never the posted one. It writes
    `SpyConfiguration.ignored_network_counterparts` (JSON dict `{"<EVE id>":
    "<name>"}`, migration 0020, default `{}`), starts the rebuild
    (`_start_rebuild`) and redirects to the Network overview - the
    Corporation's own page would be a 404 once its last connection is gone.
  - `network.connections(..., ignored_counterparts=)` skips the party in
    `add()`, so the counterpart counts for neither the shared-partner rule nor
    player trading. `snapshot.build` passes the int IDs, `_inputs()` has the
    field. The ISK marker (`markers._check_wallet`) is untouched.
  - Settings, section *Network*: `forms.ignored_network_counterparts` is a
    multi-select of the stored entries (names as labels, all selected), shown
    only when one is stored; removing and saving takes it back
    (`clean_ignored_network_counterparts` keeps a subset of the stored dict;
    an ID that was never ignored is refused). A POST without the field clears
    the list, like every multi-select here.
  - Tests: `TestIgnoredCounterparts` (4, `test_network`), seven in
    `TestNetworkPages` (button for managers, none for viewers, ignore +
    rebuild, viewer refused, manager without `view_suspects` refused, unknown
    ID, GET 405) and three in `TestSettingsPage`. The four calculation tests
    are red without the one filter line (checked). The permission guards were
    **not** checked red: auto mode refused to weaken the decorator for a
    moment. Suite at the commit: 464 without translation tests, green (fresh
    test database); 8 new glossary texts, machine-translated, not reviewed by
    the user. Not seen in a browser (SSO).
- Before (0.0.40), 2026-11-23: the two lists of
  ignored characters offer only characters with a finding.
  `forms.marked_characters(config, contacts)` reads the stored snapshot
  (the `character_ids` of the `contacts` marker of every suspect and visitor;
  for the Network the first value of every `links` row), ignores a snapshot
  of another Alliance; `character_choices(config, marked, stored)` adds the
  IDs already stored (an ignored character leaves the findings and would
  vanish on save) and labels them from `markers.roster`. No history is kept
  (user's choice): a finding that went away on its own drops the character
  from the list. Before the first calculation only the stored IDs show.
  Tests: `TestSettingsPage` (`store_findings`, `choices` helpers; three new
  tests red against the old `forms.py`, the save test seeds a snapshot - a
  posted ID outside the choices is refused). Suite at the commit: 450
  without translation tests, green (fresh test database); no new texts.
  Not seen in a browser (SSO), `aa_dev` has no contacts marker.
- Before (0.0.39), 2026-11-23: two lists of ignored
  characters and the settings tab *Alliance* in sections.
  - `SpyConfiguration.ignored_contact_characters` /
    `ignored_network_characters` (JSON lists of EVE IDs, migration 0019).
    `markers._check` hands `_check_contacts` only the audits of characters
    not on the contact list; `network.connections(..., ignored_characters=)`
    reads the wallet and contracts of the others only, but keeps the ignored
    ones in `owner` - a payment to an own alt outside the Alliance must stay
    "own", not an outsider. `snapshot.build` passes the network list,
    `_inputs()` has both. Both are in `forms.SpyConfigurationForm`
    (`character_choices`: every character of `markers.roster`, an alt as
    "Name (Main)", stored IDs not held any more stay selectable; the clean
    methods turn the posted strings into sorted ints).
  - `settings.html`, tab *Alliance*: cards *Alliance*, *Hostile and data
    basis* (hostile below, time frame, ignored wallet types), *Markers*
    (h6 per marker: Blue kills, Capital in contract, Frequent Corporation
    changes, Friendly to hostiles) and *Network*. Template only, one form
    as before.
  - Tests: `TestContacts` (2), `TestIgnoredCharacters` in `test_network` (5),
    four in `TestSettingsPage` (offer, save, reject, section order). The
    positive ones red against the old code; the two guards (ignored
    character stays own, the network ignores the contact list) red against
    one broken line each. The first version of the "stays own" test passed
    against the mutation: an alt inside the Alliance is in `inside` anyway -
    the test uses an alt outside. Suite at the commit: 448 without
    translation tests plus the translation tests of `tools/translate.py`,
    all green (fresh test database). 4 new glossary texts (*Hostile and data
    basis*, *Ignored characters*, two help texts), machine-translated, not
    reviewed by the user. Not seen in a browser (SSO), only rendered by the
    test client.
- Before (0.0.38), 2026-11-23: Network with contracts without ISK
  (`network.connections()` reads `Contract` once more: price, reward and
  collateral 0, every type/status, time frame on `date_issued`) and the
  switch *Network: neutral partners too* with `network_blue_above`
  (`kept_partners(accounts, blues=None)`, `hostiles.network_blue_ids`,
  migration 0018). Decisions below. The user's example "E 'o" / "E' o"
  (95864929 / 2114054940) still does not show: only one own character has
  the contract, below the two-character rule.
- Before (0.0.37), 2026-11-23: copy button for the in-game link of a
  capital contract (`partials/ingame-link-button.html`,
  `<url=contract:0//ID>ships</url>`, `copy.js` with Alliance Auth's
  clipboard bundle); not in the ISK popup - corptools' contracts are
  private.
- Before (0.0.36), 2026-11-21: page *Statistics* (`statistics/`, numbers
  of the last sweep in `SweepStats`, migration 0017) and *Log* (`log/`) as
  own pages, both `manage_settings` **and** `view_suspects`
  (`permissions.all_permissions_required`); nav order Markers | Network |
  Statistics | Log | Settings.
- Before (0.0.35), 2026-11-20: three fixes of the
  capital sweep after an ESI review (user asked for the token use, buckets,
  timeouts and duplicate requests).
  - Both public contract calls run `results(use_etag=False,
    store_cache=False)`. Before, django-esi's stored ETags (7 days) made
    every unchanged region answer 304 from the second sweep on; the sweep
    counted that as failed and never dropped accepted or withdrawn
    contracts.
  - A region that fails gets one more try at the end of the same sweep
    (`for _attempt in range(2)`, `failed` is a list of (id, name)).
  - `ESIErrorLimitException` is re-raised by the sweep; the task is
    `bind=True` with `esi.decorators.rate_limit_retry_task` (Alliance Auth's
    own pattern) and retries after the reset.
  - Budget: the public contract endpoints have no ESI rate-limit group, so
    no bucket applies, only the error limit shared per IP with every other
    app. One sweep is about 113 region pages plus the items of new
    contracts (counted from the ETag keys of the hand run).
  - 6 new tests in `test_capital_sweep.py`, all red against 0.0.34.
- Before (0.0.34), 2026-11-19: *Capital in contract*
  no longer reads corptools. `capital_sweep.sweep()` (task
  `tasks.sweep_capital_contracts`, daily 03:15 UTC) walks
  `/contracts/public/{region}/` for every region below 11000000, keeps
  `item_exchange`/`auction` contracts of the Alliance's Corporations
  (`issuer_corporation_id` against Auth's `EveCorporationInfo`) and fetches
  the items once into `CapitalContract`/`CapitalContractItem` (migration
  0016). Rows leave when no longer listed (only if every region answered) or
  expired. `markers._check_capital_contracts` joins the table with the
  accounts' characters (a contract of a character no account owns has no main
  and is not marked); the popup `contract_details.contract` renders a row
  through the ISK popup's template with nested dicts. Own `ESIClientProvider`
  in `capital_sweep.py`: Alliance Auth's `open_api_provider` loads a fixed
  list of operations without the public contracts.
- Rules of the marker (0.0.32, user), still: only offered ships
  (`is_included`), no hostile, no time frame, no note/Cleared; the group
  setting `capital_ship_groups` (migration 0015, default Dreadnought, Lancer
  Dreadnought, Carrier, Command Carrier, Force Auxiliary, Supercarrier,
  Titan, Capital Industrial Ship; Freighters selectable) is unchanged.
  Changed in 0.0.34: no `outstanding`/`public` columns (ESI lists only open
  public ones), `for_corporation` is not read - the issuer's Corporation
  decides. Two item rows of one ship type in a contract add up now.
- Tests (0.0.37): 427 without translation tests plus the translation tests
  of `tools/translate.py`, all green (fresh test database). The 10 sweep
  tests of 0.0.34 and the
  capital tests in `test_markers` and `test_views.TestCapitalContractDetails`
  were not checked red one by one; nothing of the capital marker seen in a
  browser.
- Real ESI on `aa_dev`: 2026-11-19 (0.0.34) 24.6 s, 7 contracts of
  Invidia Gloriae Comes (an Ishtar fit in a structure in Esoteria), none
  with a capital - a hit has only been seen in tests. 2026-11-20 with the
  0.0.36 code: 26.8 s, 70 regions, 0 failed, 50989 public contracts, 7 of
  the Alliance (2 issuers, Ether Element [3THEL], all in Esoteria), 1 added,
  1 removed - no "failed" warnings, so the 0.0.35 fixes work for real.
- 0.0.31 (earlier today), both parts from the
  permission review of all eos-* apps (coordination session; its notes in
  the side-session notes folder).
- 0.0.31, part 1: permission `view_evidence` removed (user: on prod nobody holds
  `view_suspects` without it). `view_suspects` now sees the counterparts,
  the contract popup and the network pages; `sees_evidence`,
  `all_permissions_required`, `markers.EVIDENCE`/`Marker.is_evidence` and
  the template flag `evidence` are gone (`sees_corporation` covers it).
  Migration 0014 only changes `General`'s Meta (applied to `aa_dev`); the
  permission row stays in `auth_permission` - Django never deletes one,
  and a migration deleting it would take its group assignments behind the
  admin's back. Tests: the `view_evidence` ones dropped (4), the rest log
  in with `view_suspects` alone; run against the old code they failed
  (network pages, counterparts, contract popup and its button).
- 0.0.31, part 2: visitors (decisions below). `markers.roster` takes
  every account with its main or any character in a Corporation of the
  Alliance (`UserProfile` filter with a `CharacterOwnership` subquery);
  `corporation_tiles` gives each tile `visitors` (`markers.Visitor`:
  suspect, alts there, `page`), a main outside the Alliance gets no tile
  and no `mains` count. Snapshot: per Corporation `visitors` (suspect data
  plus `main_corporation_name/_ticker` and `alts`); network accounts of a
  main outside go to their alts' Corporations. `Report._suspect` is the
  old per-suspect part of `_tile`, shared by both lists; `views._accounts`
  (suspects + visitors) feeds `open_mains` (distinct accounts),
  `contracts` and the victim links; `_contact_rows` and `api` read the
  visitors too, `_contact_rows` once per main. Templates:
  `partials/markers-cell.html` (moved out of `corporation.html`), the
  block, head and tile lines, `readonly` in `kill-note-button.html`.
  `test_visitors.py` (16 tests, 14 red against the old code; the two
  green ones pin what stays). `test_network` counts the ownership table
  twice now (the subquery). Glossary: 5 new messages, translated with
  `tools/translate.py` at the commit (not reviewed by the user).
  README: the group-not-state hint for `view_own_corporation`.
- Tests (0.0.31): 372 without translation tests plus 3 translation tests, all green
  in the dev instance at 0.0.31 (fresh test database).
- Before (0.0.30): `api.character_markers(*, corporation_id=None)`
  (keyword-only): only the snapshot entry whose `id` matches, the page's
  own `Report.tile` lookup - what a CEO with `view_own_corporation` sees;
  since 0.0.31 its visitors' whole accounts too. eos-auth-monitor calls it
  for CEOs and checks the permission itself; an eos-spy-network before
  0.0.30 raises `TypeError` on the keyword.
- Before (0.0.29):
  - Permission `view_own_corporation` for CEOs (migration 0013, only the
    permission). `permissions.py`: `own_corporation_id(user)` (the main's
    Corporation, `None` without the permission or a main),
    `sees_corporation(user, id)` (`view_suspects` or own),
    (`sees_evidence` and the `evidence` flag of that version went with
    `view_evidence` in 0.0.31). Used by
    `views.index` (CEO -> own Corporation page), `views.corporation` (404
    for any other), `views.contracts` (pairs of tiles the viewer sees),
    `views.rebuild_progress` (the CEO page polls it), the menu badge
    (`open_mains(corporation_id)`). Templates: *Markers* nav for a CEO
    points at the index, *Back* and *Recalculate* only with
    `view_suspects`; note/tick controls were already gated on
    `view_suspects`, so a CEO sees them read-only. 12 tests in
    `test_own_corporation.py`, 10 failed against the old code (the other
    two are negative ones).
  - *Reason* heading of both blue kill tables now has the
    `eos-spy-network` context: eos-tax's plain "Reason" (zh_Hans left
    English) hid ours.
- Before (0.0.28): column *Reference standing* (stored per contact row by
  `snapshot._reference_rows`, "–" for an older snapshot) and the headings
  *Victim Corporation* / *Victim Alliance*.
- Before (0.0.27): card *Cleared findings* at the foot of the Corporation
  page (`CorporationTile.cleared`, `cleared.js`).
- Before (0.0.26): note buttons (`note_presets`, migration 0012) and
  clearing a day (`views.kill_day_note`).
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
  `aa_dev`). Since 0.0.36 the log is its own page `log/`.
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
  `character_markers(*, corporation_id=None) -> dict[int, list[str]]`, `label`, `description`,
  `KINDS`; change it only together with eos-auth-monitor. Colours
  (0.0.21/0.0.22): spy markers Bootstrap info, `text-info-emphasis` for
  text, legend from Bootstrap classes, only the hostile Alliance keeps
  `#8b1a1a` in `network.css`.
- What the app does today: settings (tab Alliance in sections: Alliance;
  hostile threshold, time frame, ignored wallet entry types; per marker blue
  threshold, minimum kill value, ignored ships, note buttons, capital ship
  groups, Corporation changes per year, ignored characters for friendly
  hostiles; Network: neutral partners, blue threshold, ignored characters;
  contact sources; marker switches; every
  stored blue kill and every friendly hostile contact with note and Cleared
  tick, an admin clears without a note); Markers: the Corporations as
  tiles, per Corporation the mains with markers (hostile membership now and
  in the history, frequent Corporation changes, friendly hostile contacts,
  mails, ISK, contracts, blue kills - over main and alts); Network: the ISK
  connections with hostile partners. Pages read only the stored snapshot.
- Tests: count and state in the 0.0.39 bullet above (the capital tests: see
  0.0.37). `tests.base.SpyTestCase` patches
  `views.update_snapshot` and the three ESI calls of `affiliations.py`.
  `testauth` has `eveuniverse` and `killtracker` installed for the tests.
- Translations: de, ru, zh_Hans, machine-generated, in `tools/glossary.py`;
  not reviewed by the user (0.0.13 added the blue kill texts, 0.0.14 the
  note texts, 0.0.19 the minimum value and contacts tab texts, 0.0.25
  "Ignored ships" and its help text, 0.0.26 the note buttons and day texts,
  0.0.27 the three *Cleared findings* texts, 0.0.28 the four headings
  "Victim Corporation", "Victim Alliance", "Reference standing", "Suspect
  standing" - Standing stays English; Awox and
  Blue stay English; "Cleared" carries the `eos-spy-network` context -
  another app translates it differently in ru).

| Page | Permission | What |
|---|---|---|
| Markers | `view_suspects` | a tile per Corporation: mains, mains with markers, alts of other mains with markers, count per marker; switch to hide clean ones (a marked visitor makes a tile not clean) |
| Corporation | `view_suspects` | mains with markers and what was found, the counterparts of mails/ISK/contracts and the contract popup; below it *Alts of mains in other Corporations* (visitors' whole accounts, read only, main's Corporation linked when it has a page); blue kills as a table with zKB links, note and Cleared tick, grouped by date with a row to clear the day's open kills; at the foot *Cleared findings*: mains with everything cleared, folded per main, searchable, read only |
| Network | `view_suspects` | a tile per Corporation: mains with connections to hostile partners |
| Network Corporation | `view_suspects` | the mains; on click a graph (partner, up to the reason, arrowheads show the flow) and a table of the connections with the own character's age, periods and, for private contracts, a button with the contract popup; with `manage_settings` too a button next to each counterpart ignores it (popup first) |
| Corporation (CEO) | `view_own_corporation` | only the main's own Corporation, with its evidence, its visitors' whole accounts (no link to their mains' pages) and the contract popup; notes and ticks read-only; no Back, no Recalculate; any other Corporation 404 |
| Statistics | `manage_settings` + `view_suspects` | the last contract sweep: tiles (regions, failed, public contracts, Alliance contracts, characters, Corporations, new, gone), a warning for items not fetched, Alliance contracts per region and per Corporation |
| Log | `manage_settings` + `view_suspects` | every save of a note or tick of both review tabs |
| Settings | `manage_settings` (+ `view_suspects` for the tabs Blue kills, Friendly to hostiles) | tabs: Alliance (sections Alliance; Hostile and data basis: hostile threshold, time frame, ignored wallet types; Markers: blue threshold, minimum kill value, ignored ships, note buttons, capital ship groups, Corporation changes per year, ignored characters; Network: neutral partners, blue threshold, ignored characters, ignored counterparts once one is ignored), Contact sources with aa-contacts' token state, Markers (switch per marker), Blue kills (all stored at or above the minimum value), Friendly to hostiles (all of the snapshot); in those two note and tick editable with `view_suspects`, clearing without a note |

## Open

- 0.0.44 on prod: no migration; `collectstatic` (`network.js` changed, `contracts.js` is used on
  the Network Corporation page); recalculate once - an older snapshot reads (no arrowheads, no
  contract links) but shows neither until then. Not seen in a browser: the arrowheads (direction
  of the flow; a link with both letters has a head on each end), the contract line colour, the
  popup (`contracts.js` on the Network page), the Age column. No JS syntax check was possible (no
  node in the dev WSL). Possible next steps the user may want: age on the search page rows (they
  carry `birthday` None on purpose, `fill_birthdays` runs on the Corporation page only); the
  popup for contracts without items.
- 0.0.43 on prod: run migration 0021 (one JSON field, default empty); no static file. Nothing
  changes until an admin picks highlights (Settings, tab *Alliance*, section *Highlights*;
  the list offers only parties of the stored Network, so recalculate first if it is empty).
  Not seen in a browser: the Tom Select search box (does Enter on a typed partial text keep the
  text, or pick the first suggestion?), the tiles, the new nav entry. Possible next steps the
  user may want: highlights beyond the Network (ISK/contract marker counterparts, or a neutral
  party kept in the snapshot on purpose - decided against for now); an exact-ID search link
  from a tile instead of the name substring; using `partials/standing-badge.html` in the three
  older copies of the badge (`group-cell.html`, `network_corporation.html`).
- 0.0.42 on prod: no migration, no static file. Recalculate once: the table
  shows dashes until a snapshot holds `standings`. Not seen in a browser: the
  badges in the Network table, the dash for a party the Alliance has no contact
  with, the tooltip. The *Dealings* and *Friendly to hostiles* tables are
  unchanged (no `with_held`). Possible next step the user may want: the same
  badges there.
- 0.0.41 on prod: run migration 0020 (one JSON field, default empty) and
  `collectstatic` (new `ignore.js`); nothing changes until an admin ignores a
  counterpart, which recalculates at once. Not seen in a browser: the button
  in the table (DataTables re-draws rows; the modal opens through Bootstrap's
  delegated `data-bs-toggle`), the popup, the settings list. An ignored
  counterpart still counts in the ISK marker (user's scope: Network only).
  Possible next steps the user may want: the same button for the ISK marker's
  counterparts; a note on why it was ignored.
- 0.0.40 on prod: no migration, no static file. Recalculate once so the
  snapshot is of the current code; an older snapshot has the needed keys
  (`character_ids`, `links`) since 0.0.10/0.0.4. If the user wants a lasting
  history of who ever had a finding, it needs a stored set per list
  (migration) - offered and declined for now.
- 0.0.39 on prod: run migration 0019 (two JSON fields, default empty), no
  static file; nothing changes until an admin picks characters. Not seen in
  a browser: the sections of tab *Alliance* and the two searchable lists
  (Tom Select in a tab that is initially hidden, as the other lists there).
  (Since 0.0.40 the lists hold only characters with a finding, so they stay
  short.) A character that is only the counterpart of another
  account's payment is not ignored, only its own payments and contracts
  (the user's reading: ignore characters as actors).
- 0.0.38 on prod: run migration 0018 (only the two fields), no static
  file. Nothing changes until an admin ticks *Network: neutral partners
  too*; contracts without ISK with hostile partners show after the next
  recalculation. Once switched on, expect clearly more accounts on the
  Network pages (traders, haulers outside the Alliance) - check whether the
  blue threshold 0 is right there. Not seen: the two fields in the
  Network section, a neutral partner (grey) in the graph.
- Possible next step the user may want: the user's example ("E 'o" and
  "E' o") still does not show - one own character with one contract is
  below the two-character rule (user's decision); contacts (+10) are not a
  Network connection at all.
- 0.0.37 on prod: no migration; `collectstatic` (new `copy.js`). Not seen
  in a browser (SSO) and the copied text not pasted in game: click the
  button once in the table and once in the popup, paste into an EVE chat,
  click the link. The user's own test pasted the same text typed by hand
  and it worked. `aa_dev` has no capital contract, so the button shows
  nowhere there.
- 0.0.34/0.0.35 on prod: run migration 0016 (0.0.35 adds none), add the
  beat entry from the README (`eos_spy_network_sweep_capital_contracts`),
  restart Celery (worker and beat - the task's signature changed to
  `bind=True` in 0.0.35), then run the task once by hand and recalculate -
  until the first sweep the marker finds nothing. The sweep needs eve_sde
  (regions, stations).
- 0.0.36 on prod: run migration 0017; *Statistics* shows "No contract
  sweep has run yet." until the first sweep with the new code. Neither page
  was seen in a browser (SSO) - only rendered through the test client;
  the tiles in light and dark theme are unseen.
- Not done, possible next steps: `affiliations.py` (network task) has the
  same django-esi weakness - its timeouts are not retried either; not
  reviewed. The django-esi retry bug (its check tests httpx2's exception
  classes, aiopenapi3 raises its own) could be reported upstream - only
  with the user's yes, it is a public post.
- Capital popup (`views.capital_contract`, `capital-contract/<id>/`) and the
  table are only rendered in tests: `aa_dev` has no open public capital
  contract of the Alliance. The popup shows "corptools has not stored this
  contract." when the sweep dropped the row since the last calculation (the
  text is the ISK popup's; left as is). Reward and Collateral show 0 ISK for
  a capital contract (shared template).
- Next steps the user may want: the capital groups default to the eight
  above, not "classic only" (asked in the session, the user kept the
  setting); structure names would need a token with docking rights; a
  contract of a character no account owns is not shown at all.
- 0.0.32 on prod: the folded `<tr>` rows (collapse animation on
  table rows, light and dark) are unseen - fallback would be class toggling
  in `kills.js` (ask the user first). The group choices need eve_sde
  installed (else only stored names). A tick reloads
  the page, so a day just completed shows folded afterwards.
- 0.0.31 on prod: run migration 0014, then recalculate once (an older
  snapshot has no visitors; the pages then show none, without an error).
  Release together with eos-auth-monitor dropping `view_evidence` from its
  `sources/spy_network.py` `PERMISSIONS` (that repo's own session) - until
  then eos-auth-monitor shows the spy markers to nobody who lacks the
  stale permission. The stale `view_evidence` row may be deleted by the
  admin afterwards. Not seen in a browser: the *Network* nav and the
  counterparts for a `view_suspects`-only user (rendered in tests). Not seen in a
  browser: the block, the head and tile lines, the read-only controls -
  only the tests rendered them, and the `aa_dev` snapshot was not
  recalculated with this code. Expect more accounts on prod than before:
  every player with a main outside the Alliance and an alt inside is
  checked now. eos-auth-monitor's side (spy badge on its visiting cards,
  its "Spy network" link pointing at the CEO's Corporation instead of the
  visitor's main's) is that repo's session.
- Permission review (user, 2026-11-19), decided to leave: a CEO sees the
  own account's markers (cannot clear them), settings changes stay
  unlogged, the CEO's side channels (footer counts, standing tooltip,
  victim audit link). Full review: side-session notes of the coordination
  session.
- 0.0.30 on prod: no migration, no static file. The eos-auth-monitor side
  (CEO sees the spy markers of the own Corporation through
  `character_markers(corporation_id=...)`) is built in that repo's own
  session, not here; it needs eos-spy-network >= 0.0.30 there.
- 0.0.29 on prod: run migration 0013, then give `view_own_corporation` to
  the CEO group, never a state (the app assigns it to nobody and checks
  no CEO role). Not seen in a
  browser: the CEO's page, the progress bar without the button, the
  *Markers* nav pointing at the index. A CEO whose Corporation is not in
  the configured Alliance lands on a 404 from the start page (no notice;
  left as is).
- 0.0.28 on prod: no migration, no new static file. *Reference standing*
  shows "–" until the next calculation (button, saving the settings or the
  periodic task). Neither change was seen in a browser: `aa_dev` has no
  contacts marker, so the column, its tooltip and its sorting in the
  settings tab were only rendered in tests. A contact hostile only through
  its group shows the same standing twice: as the reference and as the red
  badge in its Corporation or Alliance cell (left as is).
- 0.0.27 on prod: no migration; `collectstatic` (new `cleared.js`). Look
  once at a Corporation with a fully cleared main: the folded group, the
  search, the dark theme. Not decided: the settings tabs stay flat (no
  grouping per main there).
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
  changes, Mails/ISK/Contracts (mails need rows).
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
- Markers weighted, a score; account page with evidence (mail headers
  and subjects, wallet entries, contracts).
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

- Public contracts (user, 2026-11-24): never count for the Network and the markers ISK and Contracts - neither
  the contract nor the wallet entries paying for it; *Capital in contract* keeps them. A contract counts for one
  partner: the acceptor, before acceptance the assignee.
- Network by points (user, 2026-11-24): every payment, contract and trade is one point, a private contract with
  items one point however many wallet entries it has; a main shows up at X points (setting, default 2) with one
  counterpart character or with one hostile Corporation/Alliance (neutral ones too with the neutral switch, blue
  never), summed over all its characters; a group hit shows all rows of its members; the hostile filter has no
  exception; highlights are links to counterparts, not a basis of the calculation.

- Counterpart at the time (user, 2026-11-24): the counterpart's Alliance at the time of the payment, contract
  or mail decides, both ways (ours then -> no counterpart even if hostile today; joined later -> counts for the
  time before); existing data first (corptools), ESI's public corporation history otherwise; Network and the
  markers ISK, Contracts, Mails. Hostility stays today's.
- Alliance as counterpart and tenure (user, 2026-11-23): the own Alliance (and its Corporations) is never a
  counterpart, also not for a character Auth does not know whom ESI puts there; mails, ISK, contracts,
  Network payments and contracts and blue kills count only from the time the character was in a Corporation
  of the Alliance, with the Corporation's own alliance history from ESI; highlights and the search box
  belong to the Network tab (the search result stays on its own page, no menu entry).
- Network contracts, arrows, age (user, 2026-11-23): a private contract with items is an own kind
  that counts alone (not a 0-ISK payment); the arrows show the direction of the flow (from the
  giver to the receiver); the age of the source character is a new column *Age* in the table
  under the graph.
- Network search and highlights (user, 2026-11-23): own page *Network search* with its own menu
  entry; searched are the counterpart, its Corporation and its Alliance, not the own characters;
  the suggestions are Tom Select with a free text allowed; the result table has the columns of
  the Network table plus main and its Corporation, the main links to the Network Corporation page
  with that main opened. Highlights: tiles above the Corporations on the Markers page, chosen in
  the settings from the Network's parties (no free names), counted in mains, Network data only;
  a click opens the search with the name filled in.

- Ignored characters (user, 2026-11-23): for *Friendly to hostiles* and for
  the Network, one list each; single characters, not whole accounts; picked
  from a searchable list of every character of the checked accounts. Other
  markers have none. The Network's shared-partner rule still needs two
  remaining own characters.
- Ignored characters, choices (user, 2026-11-23, after 0.0.39): each list
  offers only the characters with a finding in the stored snapshot (a
  friendly hostile contact / a Network link, `forms.marked_characters`) plus
  the IDs already stored; no history is kept, so a finding that went away on
  its own drops the character from the list.
- Ignored counterparts (user, 2026-11-23): a button in the Network table,
  with a confirmation naming the counterpart; kept by EVE ID, the name only
  for display; Network only (the ISK marker keeps it); the counterpart falls
  out completely (rows, graph, counts, shared-partner rule); taken back by a
  list in the settings' Network section; the recalculation starts at once;
  only `manage_settings` sees the button.
- Settings layout (user, 2026-11-23): one tab *Alliance* in sections with a
  heading - Alliance, then what Markers and Network share (hostile
  threshold, time frame, ignored wallet types), then Markers per marker,
  then Network; not own tabs.
- In-game link (user, 2026-11-23): copy button for the capital contracts
  in the table and in the popup; link text = the ships. The solar system
  is `0`: the user tried `<url=contract:30000142//ID>` (wrong system) and
  `<url=contract:0//ID>` in game, both open the contract - and a
  structure's system is unknown without a token. Not for the ISK popup:
  corptools' contracts are private.
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
  Since 2026-11-23 the default only: the setting *Network: neutral partners
  too* keeps the neutral ones as well, the blue never (see State).
- Network (2026-10-09): payments are donations, player trading and
  contract payments; one payment per character is enough, it is the overlap
  of two own characters that counts; player trading shows on its own. A
  counterpart Auth does not know counts as outside; NPCs never. The graph
  is vis-network from cdnjs.
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
- Capital sweep and ESI (user, 2026-11-20): no ETag and no response cache
  for its calls, one more try per failed region in the same sweep, the
  error limit retried as Alliance Auth's own tasks do. A failed region still
  keeps every row (no deletion that day); deletion per region would need a
  region column and was not asked for.
- ESI (changed 2026-10-09; the exception since 2026-11-19: the capital sweep
  asks ESI's public contracts once a day, the marker itself still does not):
  the markers make no ESI call - a counterpart
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
- Cleared findings (user, 2026-11-13): only mains with nothing open (a
  main still listed above keeps its cleared rows greyed there, no
  duplicate); one table for blue kills and contacts; read only - a note is
  changed in the settings tabs; groups folded at first.
- Reference standing (user, 2026-11-13): the lowest standing of the ticked
  sources as the value, the sources only in a tooltip; headings
  *Reference standing* and *Suspect standing*; in both tables; stored
  with the calculation rather than looked up at view time (one place
  instead of two, at the price of a recalculation).
- Victim headings (user, 2026-11-13): *Victim Corporation* / *Victim
  Alliance* in the long form, in both blue kill tables - a bare
  "Corporation" reads as the member's own.
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
- Statistics (user, 2026-11-20): an own nav page, not a settings tab; only
  numbers the sweep has anyway, simple counts, computed by the sweep, only
  the last run kept, plus counts per region and per Corporation; needs
  `manage_settings` + `view_suspects`. The log moved next to it (user).
- Review log (user, 2026-11-11): every save of a note or tick is kept,
  shown on its own (since 0.0.36 its own page, not a popup per row); the reviews made
  before the log are seeded once with their last state. Blue kills stay
  grouped per main and killmail in both tables, nothing more (user).
- Audit (user, 2026-11-12): `manage_settings` alone does not see the
  findings - the three review tabs need `view_suspects` too. A reviewer
  may clear findings of their own account; the log marks it, no refusal.
  The contract popup is bound to the pairs the ISK marker shows, not to
  every character of the Alliance. A save during a running calculation
  makes that run repeat itself once, rather than a message to the admin.
- Menu badge (user, 2026-11-07): counts the mains with open markers (not
  markers or findings), only for `view_suspects`; since 2026-11-19 the
  accounts, each once, and for a CEO the visitors too.
- Own kills (user, 2026-11-07): a blue kill whose victim belongs to the
  attacker's account is never stored; old copies are hidden, not deleted.
- Mails: headers and subject, never the body.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `manage_settings`, `view_own_corporation`;
  no `basic_access`, it would have opened nothing. `view_evidence` removed
  (user, 2026-11-19): nobody held `view_suspects` without it, and
  eos-auth-monitor demanded it for labels that carry no evidence.
- CEO permission (user, 2026-11-17): `view_own_corporation`, assigned by
  the admin (no automatic CEO detection by `ceo_id`); own = the main's
  Corporation; it shows the Corporation page and its evidence only - no
  network pages, no notes or *Cleared*, no *Recalculate*, no settings; the
  menu badge counts the own Corporation's mains.
- Visitors (user, 2026-11-19): an account with an alt in a Corporation
  and its main elsewhere is that Corporation's CEO's problem too. Its
  whole account shows there - main, main's Corporation, all alts, every
  marker with everything found, mails/ISK/contracts of all its characters
  included - in an own block below the mains, to the CEO and to
  `view_suspects` alike, read only (notes on the main's page; a main
  outside the Alliance only in the settings tabs). A player is all of his
  characters: a main outside the Alliance is checked through an alt
  inside. Head and tile count the visitors, a tile with one is not clean,
  the CEO's menu badge counts them, `view_suspects` counts every account
  once. Levels (user): member (none in this app - he would see his own
  suspicion), CEO (the main's Corporation plus its visitors; an own alt
  elsewhere opens nothing), leadership (everything).
- CEO in eos-auth-monitor (user, 2026-11-17): eos-auth-monitor honours
  `view_own_corporation` and shows a CEO the markers of the own
  Corporation only, exactly by this app's rule; hence the API argument
  (0.0.30), the permission check stays in eos-auth-monitor.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migrations 0001 to 0021
  applied to `aa_dev` (0021 on 2026-11-23), `collectstatic` run (0.0.44; 0.0.41 added `ignore.js`). `SweepStats` holds
  the row of the 2026-11-20 hand run. `local.py` has a `## eos spy
  network` block with the sweep's beat entry (2026-11-19); no Celery
  process runs, so it fires only once worker and beat are started. The
  tables `CapitalContract`/`CapitalContractItem` hold the 7 contracts of the
  2026-11-20 hand run. Redis still holds that run's 120 ETag keys
  (`eos-spy-network_etag_*`); 0.0.35 no longer reads them, they expire
  about 2026-11-26. The snapshot was rebuilt by
  hand with 0.0.10 (so it has no `standings` of 0.0.42), not since the 0.0.11 contacts change (`snapshot.update()` in the shell; time frame 365,
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
  testing the button. `collectstatic` ran with the 0.0.27 static files (`cleared.js`; 0.0.28 adds none). Its snapshot was not rebuilt since 0.0.28, so it holds no visitors. Its `auth_permission` still has the stale `view_evidence` row (Django keeps it), untouched.

## Traps

- A test fixture that wants a counterpart's name in the Network needs a corptools `EveName`:
  `_fill_names` falls back to the ID, the name ESI gave the entity is not used.
- A mutation check by script: `mutate.py`-style (replace one line asserting it occurs once, run,
  restore in `finally`) run with the venv Python by its full path from the PowerShell tool
  (`wsl.exe -d Ubuntu-22.04 -e /home/allianceserver/aa-dev/venv/bin/python <script>` - `~` is not
  expanded there). A mutation that comments a template line with `{# ... #}` must close it on
  the same line, or it breaks nothing.

- From the PowerShell tool, double quotes inside `wsl.exe ... bash -lc '...'`
  are dropped: `grep -E "^FAIL|^OK"` dies with "command not found". Use a
  pattern without quotes or a script file; `| tail -n 8` needs no quotes.
- Auto mode refuses a mutation check that weakens a permission decorator (even
  briefly, even restored at once); mutate calculation code instead, or leave
  the guard test unchecked and say so.
- A `ModelForm` field whose model field is a JSON dict needs
  `self.initial[name] = list(keys)` for a `MultipleChoiceField`, or the
  initial value is the dict itself (`forms.ignored_network_counterparts`).
- `sri_static` renders the hashed file name (`copy.<hash>.js`): a test that
  a page loads a script asserts on `eos_spy_network/js/copy.`, not on
  `copy.js`.
- django-esi 10: `.results()` uses ETags by default and raises
  `HTTPNotModified` when every page answered 304 - a caller that needs the
  data must pass `use_etag=False` or catch it. Its built-in retry
  (`_httpx_exceptions`) never fires for timeouts or 5xx: aiopenapi3 wraps
  them in its own `RequestError`/`HTTPServerError`. Buckets exist only for
  operations with an `x-rate-limit` group in the spec and only with a
  token; check the group in `https://esi.evetech.net/meta/openapi.json`.
- Asserting the arguments of an ESI call: `patch.object(capital_sweep,
  "esi")` replaces the provider without touching `esi.client`. A bound task
  runs in a test by calling it directly with `retry` patched
  (`TestSweepTask`).
- Git Bash rewrites a `/mnt/c/...` path handed to `wsl.exe`: run a script
  from the scratchpad through the PowerShell tool, not the Bash tool.
- A test that fakes ESI for the sweep patches `capital_sweep._region_contracts`
  and `_contract_items`, never the provider; `esi.client` would try to load
  the OpenAPI spec over the network.
- The `corptools`-based `TestCapitalContracts` fixtures are gone: its
  `add_offer` writes `CapitalContract`/`CapitalContractItem`; the popup tests
  borrow it and need `self.main` (set in their own `setUp`).
- `test_network.TestQueries` counts queries per table with a `FROM <table>`
  regex: a subquery inside another query counts as one more (since
  0.0.31 `authentication_characterownership` counts 2: the subquery in the
  mains' query and the characters' query - still one read per run).
- The dev venv has no `flake8`; line length (120) is checked by eye.
- `aa-test` takes several test labels in one run
  (`aa-test eos_spy_network.tests.test_views eos_spy_network.tests.test_menu`).

- A test class borrowing another class's `setUp` (`setUp =
  Other.setUp`) fails on the zero-argument `super()` inside it: move the
  fixture part into a method (`add_donation`, `add_audit` in
  `test_views`) and borrow that. Importing a TestCase class into another
  test module runs its tests a second time: reach it through the module
  (`test_views.TestEvidence.add_donation`).
- Another AA app of this machine adding a plain short msgid (eos-tax's
  "Reason") can turn a translation test red without a change here: give
  ours the `eos-spy-network` context, the glossary stays keyed by msgid.
- The Edit tool refuses a file under `\\wsl.localhost\...` that was only
  seen through Grep: Read it (the lines are enough) first.
- A new test is cheapest checked against the old code by writing it
  before the change and running it red, instead of stashing afterwards.

- Checking new tests against the unfixed code in one go: `git stash push
  -- <the changed code files>` (tests left in place), run the modules,
  `git stash pop`. Name the paths, or the tests go into the stash too.
  Stashing a template-facing `forms.py` alone turns every settings page
  test into an error (the template asks for the new field), not only the
  new one.
- A guard test of a new feature ("leaves X out") passes against the old
  code, which knew nothing of X: check it against the new code with that
  one line broken instead - a script that replaces the line (asserting it
  occurs once), runs the test and writes the file back in `finally`.

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
  the pipes; put such lines into a script and run it with
  `wsl.exe -d Ubuntu-22.04 -e bash -l /home/allianceserver/<script>` from
  the PowerShell tool - the Bash tool (Git Bash) rewrites that path to
  `C:/Program Files/Git/home/...`.
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
