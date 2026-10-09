# EOS Spy Network

An [Alliance Auth](https://gitlab.com/allianceauth/allianceauth) app that
points leadership at members who may be spies: accounts whose characters are
close to the Alliance's enemies - in their Corporations, in their contacts,
mails, wallets and contracts.

The enemies are taken from the Alliance's own contacts as
[aa-contacts](https://github.com/Maestro-Zacht/aa-contacts) holds them: the
contacts of the Alliance and of the Corporations ticked on the settings page,
every one with a standing below a configurable value.

> **Status: in development.** This first version builds the hostile list.
> The checks of the members (see [Planned](#planned)) come next.

## Features

- **Hostile list**: every contact of a ticked source with a standing below
  the threshold, the lowest standing first, with the sources that hold it and
  their standing each. One source is enough: the Alliance may stay neutral to
  an entity one of its Corporations is at war with. The Alliance itself and
  its Corporations never count as hostile
- **Settings page**: the Alliance, chosen from a searchable dropdown; the
  standing below which a contact is hostile (default: below 0); a searchable
  table of the Alliance and its Corporations to tick the contact sources,
  each with whether aa-contacts has a token for it, the time of the contacts
  aa-contacts holds, the number of contacts and of hostiles. A ticked
  Corporation that left the Alliance stays in the table, marked, until it is
  unticked
- **Notices** on the hostile list for every ticked source aa-contacts has no
  contacts of yet, and when aa-contacts is not installed

## Where the contacts come from

The app reads the Alliance and Corporation contacts from
[aa-contacts](https://github.com/Maestro-Zacht/aa-contacts) and makes no ESI
call of its own. Tokens are added on aa-contacts' page (*Add alliance token*,
*Add corporation token*), and aa-contacts' own periodic task
(`aa_contacts.tasks.update_all_contacts`) keeps the contacts up to date. A
source without a token in aa-contacts adds nothing to the hostile list.

aa-contacts is read when installed and is not a dependency; without it the
pages say so and the hostile list stays empty. Contact names come from Auth's
own tables, the way aa-contacts' list shows them; an entity Auth does not
know yet is shown by its ID.

## Permissions

| Permission | What it allows |
|---|---|
| `eos_spy_network.view_suspects` | the hostile list (later: the suspects) |
| `eos_spy_network.view_evidence` | later: the evidence - mail headers and subjects, wallet entries, contracts |
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

5. Give the permissions to the groups or states that should have them, then
   open *Spy Network* > *Settings*, choose the Alliance and tick the sources.

## Planned

Signals per account, each switchable and weighted, read from corptools:

- a character currently in a hostile Corporation or Alliance, or recently
  (`CorporationHistory`); frequent Corporation changes
- contacts with a positive standing to hostiles, or hostiles watched
  (`CharacterContact`)
- mails to or from hostiles - headers and subject only (`MailMessage`)
- ISK to or from hostiles (`CharacterWalletJournalEntry`), contracts with
  hostiles (`Contract`)
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
