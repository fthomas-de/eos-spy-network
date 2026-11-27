# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. At most 300 lines:
`/push` rewrites it and never appends.

Elsewhere: lasting rules and traps in `CLAUDE.md`, the history in
`CHANGELOG.md`, the user's lasting decisions in `docs/DECISIONS.md` - read
that one only when a task touches it (`grep -n <topic> docs/DECISIONS.md` or
one section), not at session start.

## State

- Version: `0.1.10`, 2026-11-27 (tag `v0.1.10`): the Highlights tiles are
  sorted (Alliance, Corporation, Character; most mains first).
- Possibly not deployed yet (the user deploys every release right away):
  - `0.1.10`, `0.1.9` (Payments row on the Corporation tile): no migration,
    no `collectstatic`, no recalculation.
  - `0.1.8`: no migration, no `collectstatic`, one recalculation - until
    then the marker does not show.
  - `0.1.7`: no prod steps (403 instead of the login page).
  - `0.1.5`: migration 0025, `collectstatic` (`ignore.js`), one
    recalculation.
  - `0.1.6`: migration 0026, `collectstatic` (`items.js`, `items.css`), one
    recalculation - until then membership, Corporation changes, mails, ISK
    and contracts show no tick (the snapshot holds no items yet).
- What the app does today: from the contacts of the Alliance and its
  Corporations it builds a hostile list and checks every account with a
  character in the Alliance against it - markers per main (membership,
  Corporation changes, owner changes, friendly hostile contacts, mails, ISK,
  contracts, blue kills, capital ships in public contracts) and a Network of ISK and contract
  links to hostile (optionally neutral) partners, scored by points. A Celery
  task stores the result as a snapshot; the pages read only that, and
  eos-auth-monitor reads the markers through `api.py`. Every marker but
  *Capital in contract* takes a note and a *Cleared* tick per case; the
  cleared ones are folded below the open ones.

## Open

- Not seen in a browser (SSO, and `aa_dev` lacks the data): the info
  button's popover (`items.js`, scrolls when long), the folded *Cleared*
  rows and the day rows of the new case tables, and the *Owner changes* case
  table and settings tab. Only rendered in tests.
- Possible next steps the user may want:
  - A filter, should the folded *Cleared* lists grow too long (user's word).
  - Capital: structure names (need a token with docking rights); a contract
    of a character no account owns is not shown; Reward and Collateral show
    0 ISK for a capital contract, and its popup says "corptools has not
    stored this contract." once the sweep dropped the row (shared template).
  - Markers weighted into a score; an account page with the evidence.
  - More markers: clones/assets in staging systems (needs a setting for the
    systems), audit gaps as a data gap.
  - Owner changes: a record goes with its user (cascade), so an earlier
    owner's deleted Auth account takes the finding away; a time frame is not
    possible (`created` is `auto_now`).
  - The same 403 is still missing in eos-sig-checker and eos-invoices (their
    own sessions).
- Not decided, left as built: a `BlueKill` copy is never deleted (few rows,
  the time frame hides old ones; after a change of the Alliance the old
  copies stay unused); the settings tabs stay flat (no grouping per main,
  cleared rows greyed in place, not folded).
- Known quirks, left as is: a contact hostile only through its group shows
  the same standing twice when the Alliance is the source (reference, and the
  held badge of its Corporation or Alliance cell) and still reads "Name
  (Corp)" next to the Corporation column. A case of ISK/mails ticked off
  again keeps its fixed items, so new entries make a second open case beside
  it.

## Dev instance

- Installed editable, in `INSTALLED_APPS` of `myauth/settings/local.py`;
  migrations up to 0026 applied, `collectstatic` current, snapshot rebuilt
  2026-11-25 with 0.1.4 (recalculate to see the 0.1.5, 0.1.6 and 0.1.8
  changes).
- `local.py` has a `## eos spy network` block with the sweep's beat entry.
  The periodic task row `contacts` (id 7) is disabled; the hourly
  `CELERYBEAT_SCHEDULE` entry in `local.py` is the one to keep. A Celery
  worker runs (`-P solo`), no beat: no periodic task fires on its own. Since
  2026-11-27 it runs in the background (`setsid nohup`, started from
  `myauth`), its log in `~/aa-dev/celery-worker.log`; before, it ran in a
  terminal.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815).
- `aa_dev` has no hostile Network partner, no ISK, contract, mail or contacts
  marker and no capital contract of the Alliance, and no owner change (12
  `OwnershipRecord` rows, one per character): those pages and popups
  were only rendered in tests. A seed of an earlier owner is an Auth table
  and needs the user's yes. Seeding corptools rows for them (journal,
  `Contract`, `CharacterContact`, mails) needs the user's yes (foreign
  tables).
- Held data: 7 `CapitalContract` rows and the `SweepStats` row of the
  2026-11-20 hand run (no capital among them); 1 `CorporationAlliances` row;
  4 `BlueKill` rows with fake killmail IDs 99000000101-103 (Ether Element,
  test seed of unknown origin, never pruned); killtracker itself stores
  none (no beat). No `FindingReview` rows of the new kinds yet.
- The configured Alliance holds 30 Corporations `T000`-`T029` without mains,
  apparently another app's leftover seed: ask before removing anything.
- `auth_permission` still has the stale `view_evidence` row; untouched.
