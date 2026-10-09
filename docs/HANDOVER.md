# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. Lasting rules live
in `CLAUDE.md`, the history in `CHANGELOG.md`.

Last updated 2026-10-09.

## State

- Version: `0.0.1`, 2026-10-09 - the first release (see `CHANGELOG.md`):
  package skeleton, settings page, hostile list from aa-contacts.
- What the app does today: a settings page to choose the Alliance, the
  standing threshold and the contact sources (the Alliance and its
  Corporations); a hostile list of every contact below the threshold, read
  from aa-contacts. The member checks do not exist yet.
- Tests: 39 without translation tests plus 3 translation tests, all green
  (standalone and in the dev instance); every test checked against
  sabotaged code.
- Translations: de, ru, zh_Hans, machine-generated, 37 messages in
  `tools/glossary.py`; not reviewed by the user yet.

| Page | Permission | What |
|---|---|---|
| Hostile list | `view_suspects` | contacts below the threshold, merged across sources |
| Settings | `manage_settings` | Alliance, threshold, contact sources with aa-contacts' token state |

## Open

- The signals per account, each switchable and weighted (README,
  *Planned*): character in a hostile Corporation now or recently, frequent
  Corporation changes, contacts, mails (headers and subject), wallet,
  contracts, clones/assets in staging systems, owner changes, audit gaps as
  data gap.
- Suspects list with score, account page with evidence (`view_evidence`),
  review per suspect: status (new, seen, harmless, watch, confirmed), note,
  history; a harmless one comes back only with new signals.
- Not tried in the browser yet: once aa-contacts' task has read the
  contacts, choose the Alliance on the settings page, tick the sources and
  look at the hostile list.
- Check the release against https://github.com/fthomas-de/aa-app-checklist.
- Staging systems for the clone/asset signal need a setting of their own.

## Decisions

- Purpose: detect suspected spies (not run an own spy network, not an intel
  board).
- Hostile = contact of a ticked source (Alliance and/or its Corporations,
  ticked in a searchable table) with a standing below a configurable value,
  default below 0. One negative source is enough. The Alliance and its own
  Corporations never count.
- Contacts come from aa-contacts, which runs in the dev and the prod
  instance; no ESI call and no task of our own. The first version fetched
  them itself - dropped before any commit.
- Mails: headers and subject, never the body.
- Review with status, note and history.
- Scope: one Alliance, as in eos-auth-monitor.
- Permissions `view_suspects`, `view_evidence`, `manage_settings`; no
  `basic_access`, it would have opened nothing.

## Dev instance

- Installed editable (`pip install --no-deps -e`), listed in
  `INSTALLED_APPS` of `myauth/settings/local.py`; migration 0001 applied to
  `aa_dev`, `collectstatic` run.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815), added 2026-10-09; its contacts were not read yet at
  that time (`last_modified_contacts` empty).

## Traps

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
  new clash of that kind.
