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

- **Markers**: a tile per Corporation of the Alliance with its number
  of mains, how many of them have markers, and per marker how many mains
  have it. A switch hides the Corporations without markers; the browser
  remembers it
- **Corporation page**: every main of the Corporation with at least one
  marker, the most marked first, with the number of characters on the
  account and per marker what was found. The counterparts of mails, ISK and
  contracts are evidence and only shown with `view_evidence`; without it
  the marker and its count are
- **Markers** per account, over the main and all its alts:
  - *Hostile membership*: a character is in a hostile Corporation or
    Alliance, or was in a hostile Corporation (`CorporationHistory`)
  - *Frequent Corporation changes*: a character joined as many Corporations
    within the last 365 days as configured (default 4)
  - *Friendly to hostiles*: a character's own contacts hold a hostile with a
    positive standing, or on the watch list (`CharacterContact`)
  - *Mails with hostiles*: mails from or to hostiles, counted once per mail
    (`MailMessage`; the body is never read)
  - *ISK with hostiles*: wallet journal entries with a hostile as a party
    (`CharacterWalletJournalEntry`)
  - *Contracts with hostiles*: a hostile issued, was assigned or accepted the
    contract, or its issuer is in a hostile Corporation (`Contract`)

  Mails, ISK and contracts between characters of the same account never
  count.
- **Network**: a tile per Corporation with the mains that have ISK
  connections outside the Alliance (a switch hides the Corporations without
  any), and per Corporation the list of such mains; a click on a main shows
  the graph of its characters, their counterparts and the counterparts'
  Corporations and Alliances, and a table of the connections. In the graph
  the own characters are green (main darker, alts lighter), hostiles red,
  everything else outside the Alliance neutral; a hostile Corporation or
  Alliance carries its standing, the sources in its tooltip. A counterpart
  is a *hostile partner* when it, its Corporation or its Alliance is a
  hostile contact. A main shows up when
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
  Corporations, factions) never count. The page needs `view_suspects` and
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
- **Settings page**: the Alliance, chosen from a searchable dropdown; the
  standing below which a contact is hostile (default: below 0); the number
  of Corporation changes per year that sets a marker; a searchable table of
  the Alliance and its Corporations to tick the contact sources, each with
  whether aa-contacts has a token for it, the time of the contacts
  aa-contacts holds, the number of contacts and of hostiles. A ticked
  Corporation that left the Alliance stays in the table, marked, until it is
  unticked
- **Notices** above the marker and network pages for every ticked source aa-contacts has
  no contacts of yet, and when aa-contacts or corptools is not installed

## What the markers can see

The markers make no ESI call. Who belongs to a hostile Corporation or Alliance
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
calculation goes on.

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

The markers switchable and weighted, and more of them, read from corptools:

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
