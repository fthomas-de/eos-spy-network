# EOS Spy Network

An [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) app that
points leadership at members who may be spies: accounts whose characters are
close to the Alliance's enemies - in their Corporations, in their contacts,
mails, wallets and contracts.

The enemies are taken from the Alliance's own contacts as
[aa-contacts](https://github.com/Maestro-Zacht/aa-contacts) holds them: the
contacts of the Alliance and of the Corporations ticked on the settings page,
every one with a standing below a configurable value.

> **Status: in development.** Markers per account are shown per
> Corporation; scores and the review of suspects (see [Planned](#planned))
> come next.

## Features

- **Menu badge**: the menu item shows how many accounts have open markers
  (switched-off markers and cleared findings left out), each counted once:
  for `view_suspects` all of them, for `view_own_corporation` those its
  Corporation page shows, visitors included
- **Markers**: a tile per Corporation of the Alliance with its number
  of mains, how many of them have markers, how many alts of other mains
  with markers it holds (visitors, see below), and per marker how many mains
  have it. A switch hides the Corporations without markers or marked
  visitors; the browser remembers it
- **Accounts checked**: every account whose main is in a Corporation of the
  Alliance, and every account with an alt in one, its main elsewhere or
  outside the Alliance - a player is all of his characters, inside the
  Alliance or not
- **Corporation page**: every main of the Corporation with at least one
  marker, the most marked first, with the number of characters on the
  account and per marker what was found, with the counterparts of mails,
  ISK and contracts. ISK and contracts show a row per own
  character and hostile: the hostile's Corporation and Alliance (red with
  the standing when hostile themselves), how many entries or contracts, the
  ISK moved (for the wallet), the period from the first to the last one and
  their kinds.
  The Corporation changes name the Corporations joined, with the day, in a
  tooltip per character. Blue kills show a row per own character and
  killmail: the day (linked to zKillboard), the victim, its Corporation and
  Alliance, the ship and the reason - *Awox* or *Blue* with the standing.
  Each row has a
  note (up to 160 characters) and a tick *Cleared*, editable with
  `view_suspects` here and in the settings tab *Blue kills*; clearing needs
  a note here, while an admin with `manage_settings` ticks a row off in the
  settings tab without one. A cleared kill
  stays in the table, greyed, but no longer counts - at once, without a
  recalculation, on these pages and for eos-auth-monitor; a main whose kills
  are all cleared and who has no other marker counts as clean. A day whose
  kills are all cleared is folded to its day row; a click on the date
  unfolds it. *Capital in contract* shows a row per contract: the
  character, the ships, the type, price and buyout in million ISK, the
  location, the dates and the title; a button next to *View details* and
  one in its popup copy the contract's in-game link with the ships as its
  text, to paste into EVE's chat or a mail.
  Below, *Alts of mains in other Corporations*: every marked account with
  an alt in this Corporation whose main is elsewhere, with its main, the
  main's Corporation, its alts here and all its markers with everything
  found - the CEO answers for the alt. Read only: notes and ticks are set on
  the page of the main's Corporation (linked for `view_suspects`), for a
  main outside the Alliance in the settings tabs
- **Markers** per account, over the main and all its alts:
  - *Hostile membership*: a character is in a hostile Corporation or
    Alliance, or was in a hostile Corporation within the time frame
    (`CorporationHistory`)
  - *Frequent Corporation changes*: a character joined as many Corporations
    within the last 365 days as configured (default 4)
  - *Friendly to hostiles*: a character's own contacts hold a hostile with a
    positive standing (`CharacterContact`; 0 and below do not count)
  - *Mails with hostiles*: mails from or to hostiles, counted once per mail
    (`MailMessage`; the body is never read)
  - *ISK with hostiles*: wallet journal entries with a hostile as a party,
    except the ignored entry types (`CharacterWalletJournalEntry`)
  - *Contracts with hostiles*: a hostile issued, was assigned or accepted the
    contract, or its issuer is in a hostile Corporation (`Contract`)
  - *Capital in contract*: a character of the account offers a ship of one
    of the chosen capital groups in an open public contract. ESI lists these
    per region; the daily sweep (`tasks.sweep_capital_contracts`) keeps those
    issued by a Corporation of the Alliance, with their items, and drops one
    that is no longer listed or has expired. It needs neither corptools nor a
    token, so the data is up to one day old; the expiry is checked on every
    calculation. Only ships the contract offers count, not those a
    want-to-buy asks for. The location is the region and the station; a
    structure's name needs a token, so it shows as its ID. A contract of a
    character no account owns has no main and is not marked. It needs no
    hostile and no time frame
  - *Blue kills*: a character was among the attackers of a killmail whose
    victim is in the Alliance (awox), or whose victim, its Corporation or
    Alliance has at least the blue standing with the Alliance (default 5).
    Only the Alliance's own contacts in aa-contacts make a blue, not those
    of the ticked Corporations. A killmail counts once per account however
    many of its characters were on it; a kill of a character of the same
    account does not count. A kill worth less than the minimum value
    (zKillboard's value, in million ISK; default 0 counts every kill) does
    not count; one without a known value does. Neither does a kill of one
    of the ignored ships. Read from killtracker (see
    [Killmails](#killmails)); needs no hostile

  Mails, ISK and contracts between characters of the same account never
  count. Mails, ISK and contracts count only within the time frame (a mail
  without a date always counts) and only from the time the character was in a
  Corporation of the Alliance (see [What the markers can see](#what-the-markers-can-see));
  the contacts carry no date in corptools, so today's are checked whatever the
  time frame.
- **Network**: a tile per Corporation with the mains that have ISK
  connections with hostile partners outside the Alliance (a switch hides the
  Corporations without any), and per Corporation the list of such mains; a
  click on a main shows the graph of its characters and their hostile
  partners, and a table of the connections with the period from the first
  to the last payment. A counterpart is a *hostile partner* when it, its
  Corporation or its Alliance is a hostile contact. The graph follows a
  partner only as far as the reason: a partner hostile itself has no
  Corporation node, one hostile through its Alliance keeps its Corporation
  between them; the partner's tooltip names its Corporation and Alliance.
  The own characters are green (main darker, alts lighter), hostiles red,
  the rest neutral; a hostile carries its standing, the sources in its
  tooltip; a line's tooltip gives the payments and their period. Every
  connection is worth one point, and a main shows up when its characters
  together reach *Network: minimum connections* (default 2) points with one
  counterpart - or with one hostile Corporation or Alliance, all its members
  added up; then the table lists every row with a member of that group, also
  the ones with a single connection. A partner that is not hostile does not
  count - with anyone else they are everyday trading and hauling. The setting
  *Network: neutral partners too* lets the neutral partners show as well:
  then only a blue one stays out - it, its Corporation or its Alliance above
  *Network: blue above standing* (default 0) at a ticked source, and none of
  the three hostile; a neutral Corporation or Alliance adds up its members
  then as well. Highlights do not count as a group. The connections are:
  - a payment: the wallet journal's `player_donation`, `player_trading` and
    contract payments (`contract_price`, `contract_price_payment_corp`,
    `contract_reward`, `contract_collateral`, `contract_collateral_payout`)
    between a character of the account and someone outside the Alliance
  - a contract without ISK (price, reward and collateral 0 - a gift of items
    leaves no journal entry with the partner) from corptools' contracts, of
    any type and status, issued, assigned or accepted, as a payment of 0 ISK
  - a private contract: any contract with items that corptools holds with
    availability *personal* (private), of any type and status, issued,
    assigned or accepted by one of its characters with someone outside the
    Alliance - with or without ISK. It counts once: the wallet entries that
    belong to it add their ISK but no point. A button in its row opens a
    popup with the contracts and their items (`view_suspects`; the contracts
    are read from corptools at the click)

  The badges on the main's entry say what the shown rows are: *Shared payment
  partner* (two characters of the account with the same counterpart), *Player
  trading* and *Private contract*.

  The graph's arrowheads follow the giver: a line points to the partner when
  the own character paid or issued, to the own character when it was paid or
  was handed a contract, both ways when both happened; the lines to alts and
  Corporations point away from the main and the partner. A snapshot of an
  older version shows no arrowheads until the next calculation. The table
  shows the age of each own character (from Auth's birthday, a dash when Auth
  has none).

  "Outside" is whoever was not in the Alliance when the payment or contract
  happened: a counterpart that was in one of its Corporations then is a
  member, also when it is hostile today, and one that joined later counts for
  the time before. NPCs (agents, NPC Corporations, factions) never count.
  Only payments within the time frame
  count (a contract by its issue date), only those made while the own character
  was in a Corporation of the Alliance, and none of the ignored entry types. An account whose main is
  outside the Alliance shows at the Corporations of its alts. The page
  needs `view_suspects`
- **Network search** (`view_suspects`; the search box sits on the Network page and
  leads to a page of its own for the result): one search box
  over the Network tables of every Corporation. Rows whose counterpart, its
  Corporation or its Alliance has the typed text in its name are listed with
  the main (linked to its Corporation's Network page, the main opened) and
  its Corporation; the own characters are not searched. The box suggests the
  parties of the stored Network; a typed text works as well.
- **Highlights**: the Network page shows a section above the Corporations
  with a tile per highlighted counterpart (Character, Corporation or
  Alliance, chosen in the settings): the standing the Alliance holds for it,
  its hostile standing if any, its Corporation and Alliance with theirs, and
  the number of mains that deal with it in the Network - itself or through a
  counterpart it is the Corporation or Alliance of. A tile links to the
  Network search. Only what the Network holds is found: a party it leaves
  out (a neutral one while *Network: neutral partners too* is off) counts 0
- **Recalculate**: the markers and connections are calculated by a task and
  stored; the pages read the stored result and show when it was calculated.
  The button *Recalculate* on the pages, saving the settings and the
  periodic task (see [Installation](#installation)) start it. While it runs, a
  progress bar with the current step replaces the button, and the page
  reloads once the result is stored. A footer shows
  what the last calculation cost: time per phase, queries, accounts,
  characters, wallet entries read, the size stored, and the time the page
  took
- **Hostiles**: every contact of a ticked source with a standing below the
  threshold. One source is enough: the Alliance may stay neutral to an
  entity one of its Corporations is at war with. The Alliance itself and its
  Corporations never count as hostile. A hostile Corporation or Alliance
  also makes its members hostile - as far as Auth knows them (see below)
- **Settings page**, in five tabs; the first three saved together. *Alliance*,
  in five sections. *Alliance*: the Alliance, chosen from a searchable
  dropdown. *Hostile and data basis*, shared by Markers and Network: the
  standing below which a contact is hostile (default: below 0); the time
  frame in days (default 365, 0 takes everything): the hostile list is
  today's, and the further back a payment, mail, contract or former
  Corporation, the likelier the standing was different then; the ignored
  wallet entry types, chosen from those in corptools' wallet journals
  (default `market_transaction`: nobody picks the other side of a market
  order). *Markers*: for the blue kills the standing from which a contact of
  the Alliance is blue (default 5), the minimum value of a blue kill in
  million ISK (default 0: every kill), the ignored ships of a blue kill's
  victim, chosen from the types killtracker offers as a victim's ship
  (default none) and the note buttons; for *Capital in contract* the capital
  ship groups, chosen from the ship groups eve_sde holds (default
  Dreadnought, Lancer Dreadnought, Carrier, Command Carrier, Force Auxiliary,
  Supercarrier, Titan and Capital Industrial Ship; Freighters and Jump
  Freighters can be added); for the Corporation changes the number per year
  that sets a marker; for *Friendly to hostiles* the ignored characters,
  whose contacts are not checked. *Network*: whether neutral partners show
  too and the standing above which a partner is blue, the minimum number of
  connections with one counterpart or group (default 2), and the ignored
  characters, whose payments and contracts leave the Network. Both lists of
  ignored characters offer the characters with a finding in the last
  calculation (a friendly hostile contact, respectively a Network link) and
  the ones already ignored (default none); the alts and the main of an
  ignored character stay checked. A counterpart is ignored with the button
  next to *Counterpart* on a Network Corporation page (needs
  `manage_settings` as well as `view_suspects`, asks first): it is then no
  connection at all and shows in the Network list of ignored counterparts,
  where removing it takes it back. *Highlights*: the counterparts that get a
  tile on the Network page, chosen from the parties of the last Network
  calculation and the ones already chosen (default none). *Contact sources*: a
  searchable table of the Alliance and its Corporations to tick the
  contact sources, each with whether aa-contacts has a token for it, the
  time of the contacts aa-contacts holds, the number of contacts and of
  hostiles. A ticked Corporation that left the Alliance stays in the
  table, marked, until it is unticked. *Markers*: a switch per marker; a
  switched-off marker is still calculated but left out of the Markers
  pages (a main marked by nothing else counts as clean), and switched on
  again it shows at once, without a recalculation. *Blue kills*: every blue
  kill stored for the Alliance at or above the minimum value, also those
  outside the time frame, as a table to sort, page and search, with the
  note and the tick of each row and who changed them last. *Friendly to
  hostiles*: every friendly hostile contact of the last calculation, the
  cleared ones too, per main, contact and standing, alike. In both a user
  with `manage_settings` and `view_suspects` ticks a row off without a note.
  These two tabs show who is suspected and need `view_suspects` as well
- **Log page**: every save of a note or a tick, on the Corporation pages or
  in the settings tabs, the latest first, with who and when, the main, the
  finding, the tick and the note before and after; reviews made before the
  log are in it with their last state only; a save a reviewer made on their
  own account carries an *Own account* badge. Needs `manage_settings` and
  `view_suspects`
- **Statistics page**: the numbers of the last daily contract sweep - when
  and how long, regions asked and failed, open public contracts listed, how
  many of them belong to the Alliance's Corporations, their issuing
  characters and Corporations, new and gone contracts - and the Alliance's
  contracts per region and per Corporation. Empty until the first sweep.
  Needs `manage_settings` and `view_suspects`
- **Notices** above the marker and network pages for every ticked source aa-contacts has
  no contacts of yet, and when aa-contacts or corptools is not installed;
  above the marker pages for the markers switched off, and - while the
  blue kills are switched on - when killtracker is not installed or does
  not store its killmails

## What the markers can see

The markers decide who is hostile without ESI (only the time a character
was in the Alliance needs it, see below). Who belongs to a hostile Corporation or Alliance
is known to them only for the characters and Corporations Auth has in its own
tables; corptools stores the names of mail, wallet and contract partners
without their Corporation. A mail, an ISK transfer or a contract with a
character Auth has never seen counts only when that character is a hostile
contact itself, or - for contracts - the issuer's Corporation, which the
contract names, is hostile.
A past Corporation counts when it is hostile itself; the Alliance it
belonged to back then is not stored anywhere.

What a character did counts only from the time it was in a Corporation of
the Alliance: mails, ISK, contracts, the Network's payments and contracts,
and blue kills before it joined or after it left are left out. That needs
two histories - corptools' list of the Corporations a character was in, and
ESI's public alliance history of each of those Corporations, which the task
asks for once a day per Corporation - less often the longer its last entry
has stood, up to once a week, but daily for the Alliance's own Corporations
(no token, at most 500 per run; the rest follows the next runs) - and keeps
in a table of this app. Where one is
missing the present stands in: a character corptools has not read yet counts
through its current Corporation, a Corporation ESI could not be asked about
counts when Auth has it in the Alliance now.

The same goes for the counterpart: a mail, an ISK transfer or a contract
with a hostile counts only if the hostile was not in the Alliance at the
time. Its Corporations come from corptools when it has a Character Audit,
else from ESI's public corporation history (no token, once a day per
character, or up to once a week when its last entry has stood for long, at
most 500 per run, kept in a table of this app); to tell a
character from a Corporation the task looks the counterpart up as the
network does. Without a history its Corporation and Alliance of today stand
in.

The markers read corptools' data; an account without a working Character
Audit simply shows fewer markers. corptools is read when installed and is
not a dependency; without it only the current Corporation and Alliance of
the characters are checked.

The network is the exception: for each counterpart outside the Alliance
the task looks up its Corporation and Alliance - first in Auth's and
corptools' tables, and only for what neither knows through ESI's public
endpoints (names, character affiliation; a Corporation's Alliance from the
stored alliance history above, so a Corporation is not asked again every
run), without a token. A failed request leaves that counterpart without
Corporation; the
calculation goes on. The rows of *ISK with hostiles*, *Contracts with
hostiles* and *Friendly to hostiles* get their counterpart's or contact's
Corporation and Alliance from the same lookup; whether one is hostile is
still decided without it.

## Killmails

The blue kills read the killmails
[aa-killtracker](https://github.com/AllianceAuth-Apps/aa-killtracker) keeps in its
own tables, and only those: its trackers post to Discord and store nothing.
killtracker keeps them only with this in `local.py`:

```python
KILLTRACKER_STORING_KILLMAILS_ENABLED = True
```

It then stores every killmail it receives from zKillboard, not only those
of the Alliance, and deletes them after `KILLTRACKER_PURGE_KILLMAILS_AFTER_DAYS`
(its default: 30). Each calculation copies the blue kills it finds into a
table of this app, and the marker reads that copy: a kill stays after
killtracker deleted it, as long as one calculation ran before - the periodic
task (see [Installation](#installation)) has to run more often than the
purge. Awox or blue is decided once, when copied: a standing changed later
does not undo the kill; a name killtracker resolves later is taken over
while it still holds the killmail. The time frame applies to the copies as
well. The blue kills start with the day the storing was switched on.
killtracker is read when installed and is not a dependency; without it, or
without storing, the marker pages say so and there are no new blue kills.

## Where the contacts come from

The app reads the Alliance and Corporation contacts from
[aa-contacts](https://github.com/Maestro-Zacht/aa-contacts) and makes no ESI
call of its own. Tokens are added on aa-contacts' page (*Add alliance token*,
*Add corporation token*), and aa-contacts' own periodic task
(`aa_contacts.tasks.update_all_contacts`) keeps the contacts up to date. A
source without a token in aa-contacts adds no hostiles.

aa-contacts is read when installed and is not a dependency; without it the
pages say so and nothing counts as hostile. Contact names come from Auth's
own tables, the way aa-contacts' list shows them; an entity Auth does not
know yet is shown by its ID.

## Permissions

| Permission | What it allows |
|---|---|
| `eos_spy_network.view_suspects` | the Corporations and their mains with markers and evidence (mail, ISK and contract counterparts, the contract popup); the network pages; notes and *Cleared* ticks; the *Recalculate* button |
| `eos_spy_network.manage_settings` | the settings page; its tabs *Blue kills* and *Friendly to hostiles* and the pages *Log* and *Statistics* only together with `view_suspects` |
| `eos_spy_network.view_own_corporation` | for CEOs: the Corporation page of the user's main's Corporation with its evidence (mail, ISK and contract counterparts) and its visitors' whole accounts; no other Corporation (an own alt elsewhere opens none), no network pages, no *Recalculate*, no notes or *Cleared* ticks |

The menu entry shows for anyone holding one of them.

Give `view_own_corporation` to a group of the CEOs, never to a state: the
app does not check who is CEO, and every holder sees the suspects of the
own main's Corporation - on a state, every member would see whether they
are suspected themselves.

Up to 0.0.30 a fourth permission, `view_evidence`, held the counterparts
and the network pages back from `view_suspects`. It is gone; Django does
not delete a permission it no longer defines, so the row stays in the
admin, assigned but without effect, until an admin deletes it.

## Installation

1. Install and set up [aa-contacts](https://github.com/Maestro-Zacht/aa-contacts)
   if it is not there yet, with its periodic task, and add the tokens of the
   Alliance and the Corporations whose contacts should count.
2. Install the app into the venv of Alliance Auth:

   ```bash
   pip install git+https://github.com/fthomas-de/eos-spy-network.git
   ```

3. Add `"eos_spy_network",` to `INSTALLED_APPS` in `myauth/settings/local.py`.
4. Run migrations and collect the static files, then restart Auth:

   ```bash
   python manage.py migrate eos_spy_network
   python manage.py collectstatic --noinput
   ```

5. Add the periodic recalculation to `myauth/settings/local.py`, then
   restart Celery (worker and beat):

   ```python
   CELERYBEAT_SCHEDULE["eos_spy_network_update_snapshot"] = {
       "task": "eos_spy_network.tasks.update_snapshot",
       "schedule": crontab(minute="30", hour="*/4"),
   }
   ```

   *Capital in contract* reads its own table, which a daily sweep of ESI's
   public contracts fills (about 120 requests, no token, no ESI rate-limit
   bucket):

   ```python
   CELERYBEAT_SCHEDULE["eos_spy_network_sweep_capital_contracts"] = {
       "task": "eos_spy_network.tasks.sweep_capital_contracts",
       "schedule": crontab(minute="15", hour="3"),
   }
   ```

6. Give the permissions to the groups or states that should have them, then
   open *Spy Network* > *Settings*, choose the Alliance and tick the sources.
   Saving starts the first calculation.

## Planned

The markers weighted, and more of them, read from corptools:

- clones and assets in configured staging systems
- a character that changed owner (`OwnershipRecord`)
- an incomplete corptools audit shown as a data gap, not as suspicion

Then the suspects list with a score per account, the account page with the
evidence, and a review per suspect: status (new, seen, harmless, watch,
confirmed), notes and history.

## Uninstall

```bash
python manage.py migrate eos_spy_network zero
```

Then remove the app from `INSTALLED_APPS` and
`pip uninstall eos_spy_network`.
