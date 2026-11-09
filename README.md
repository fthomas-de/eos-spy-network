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

- **Menu badge**: the menu item shows how many mains have open markers
  (switched-off markers and cleared findings left out), for users with
  `view_suspects`
- **Markers**: a tile per Corporation of the Alliance with its number
  of mains, how many of them have markers, and per marker how many mains
  have it. A switch hides the Corporations without markers; the browser
  remembers it
- **Corporation page**: every main of the Corporation with at least one
  marker, the most marked first, with the number of characters on the
  account and per marker what was found. The counterparts of mails, ISK and
  contracts are evidence and only shown with `view_evidence`; without it
  the marker and its count are. ISK and contracts show a row per own
  character and hostile: the hostile's Corporation and Alliance (red with
  the standing when hostile themselves), how many entries or contracts, the
  ISK moved (for the wallet), the period from the first to the last one and
  their kinds.
  The Corporation changes name the Corporations joined, with the day, in a
  tooltip per character. Blue kills show a row per own character and
  killmail: the day (linked to zKillboard), the victim, its Corporation and
  Alliance, the ship and the reason - *Awox* or *Blue* with the standing.
  Killmails are public, so they need no `view_evidence`. Each row has a
  note (up to 160 characters) and a tick *Cleared*, editable with
  `view_suspects` here and in the settings tab *Blue kills*; clearing needs
  a note here, while an admin with `manage_settings` ticks a row off in the
  settings tab without one. A cleared kill
  stays in the table, greyed, but no longer counts - at once, without a
  recalculation, on these pages and for eos-auth-monitor; a main whose kills
  are all cleared and who has no other marker counts as clean
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
  - *Blue kills*: a character was among the attackers of a killmail whose
    victim is in the Alliance (awox), or whose victim, its Corporation or
    Alliance has at least the blue standing with the Alliance (default 5).
    Only the Alliance's own contacts in aa-contacts make a blue, not those
    of the ticked Corporations. A killmail counts once per account however
    many of its characters were on it; a kill of a character of the same
    account does not count. A kill worth less than the minimum value
    (zKillboard's value, in million ISK; default 0 counts every kill) does
    not count; one without a known value does. Read from killtracker (see
    [Killmails](#killmails)); needs no hostile

  Mails, ISK and contracts between characters of the same account never
  count. Mails, ISK and contracts count only within the time frame (a mail
  without a date always counts); the contacts carry no date in corptools,
  so today's are checked whatever the time frame.
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
  tooltip; a line's tooltip gives the payments and their period. A main
  shows up when one of these is with a hostile partner - with anyone else
  they are everyday trading and hauling:
  - *Shared payment partner*: at least two characters of the account - main
    and alt, or two alts - exchanged ISK with the same character outside the
    Alliance; one payment each is enough. Payments are the wallet journal's
    `player_donation`, `player_trading` and contract payments
    (`contract_price`, `contract_price_payment_corp`, `contract_reward`,
    `contract_collateral`, `contract_collateral_payout`)
  - *Player trading*: any trade window deal (`player_trading`) of one of its
    characters with someone outside the Alliance

  "Outside" is everything Auth does not know as part of the Alliance, so a
  character Auth has never seen counts as outside. NPCs (agents, NPC
  Corporations, factions) never count. Only payments within the time frame
  count, and none of the ignored entry types. The page needs `view_suspects` and
  `view_evidence`: the connections are wallet counterparts
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
- **Settings page**, in five tabs; the first three saved together. *Alliance*: the Alliance, chosen from a searchable dropdown; the
  standing below which a contact is hostile (default: below 0); the
  standing from which a contact of the Alliance is blue for the blue kills
  (default 5); the minimum value of a blue kill in million ISK (default 0:
  every kill); the number
  of Corporation changes per year that sets a marker; the time frame in days
  (default 365, 0 takes everything): the hostile list is today's, and the
  further back a payment, mail, contract or former Corporation, the likelier
  the standing was different then; the ignored wallet entry types, chosen
  from those in corptools' wallet journals (default `market_transaction`:
  nobody picks the other side of a market order). *Contact sources*: a
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
  with `manage_settings` and `view_suspects` ticks a row off without a note
- **Notices** above the marker and network pages for every ticked source aa-contacts has
  no contacts of yet, and when aa-contacts or corptools is not installed;
  above the marker pages for the markers switched off, and - while the
  blue kills are switched on - when killtracker is not installed or does
  not store its killmails

## What the markers can see

The markers decide without ESI. Who belongs to a hostile Corporation or Alliance
is known to them only for the characters and Corporations Auth has in its own
tables; corptools stores the names of mail, wallet and contract partners
without their Corporation. A mail, an ISK transfer or a contract with a
character Auth has never seen counts only when that character is a hostile
contact itself, or - for contracts - the issuer's Corporation, which the
contract names, is hostile.
A past Corporation counts when it is hostile itself; the Alliance it
belonged to back then is not stored anywhere.

The markers read corptools' data; an account without a working Character
Audit simply shows fewer markers. corptools is read when installed and is
not a dependency; without it only the current Corporation and Alliance of
the characters are checked.

The network is the exception: for each counterpart outside the Alliance
the task looks up its Corporation and Alliance - first in Auth's and
corptools' tables, and only for what neither knows through ESI's public
endpoints (names, character affiliation, Corporation), without a token. A
failed request leaves that counterpart without Corporation; the
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
| `eos_spy_network.view_suspects` | the Corporations and their mains with markers; the *Recalculate* button |
| `eos_spy_network.view_evidence` | the counterparts behind the mail, ISK and contract markers; together with `view_suspects` the network pages (later: mail headers and subjects, wallet entries, contracts) |
| `eos_spy_network.manage_settings` | the settings page |

The menu entry shows for anyone holding one of them.

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
