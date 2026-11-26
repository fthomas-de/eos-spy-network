# Handover

Where the work on `eos-spy-network` stands, for the next session. Describes a
moment; where it contradicts the code, the code is right. At most 300 lines:
`/push` rewrites it and never appends.

Elsewhere: lasting rules and traps in `CLAUDE.md`, the history in
`CHANGELOG.md`, the user's lasting decisions in `docs/DECISIONS.md` - read
that one only when a task touches it (`grep -n <topic> docs/DECISIONS.md` or
one section), not at session start.

## State

- Version: `0.1.4`, 2026-11-25 (tag `v0.1.4`).
- Not deployed yet: none - the user deploys every release right away.
- `0.1.5` committed 2026-11-26, not pushed yet (search age, contract-payment
  popup, highlight search by ID, held standings in the marker tables,
  ignoring ISK/contract counterparts with a reason, log page fix). Prod steps
  once deployed: migration 0025, `collectstatic` (`ignore.js`), one
  recalculation.
- What the app does today: from the contacts of the Alliance and its
  Corporations it builds a hostile list and checks every account with a
  character in the Alliance against it - markers per main (membership,
  Corporation changes, friendly hostile contacts, mails, ISK, contracts, blue
  kills, capital ships in public contracts) and a Network of ISK and contract
  links to hostile (optionally neutral) partners, scored by points. A Celery
  task stores the result as a snapshot; the pages read only that, and
  eos-auth-monitor reads the markers through `api.py`.

## Open

- Possible next steps the user may want:
  - Note and *Cleared* for the remaining markers: Membership, Corporation
    changes, Mails/ISK/Contracts (mails need rows).
  - Capital: structure names (need a token with docking rights); a contract
    of a character no account owns is not shown; Reward and Collateral show
    0 ISK for a capital contract, and its popup says "corptools has not
    stored this contract." once the sweep dropped the row (shared template).
  - Markers weighted into a score; an account page with the evidence.
  - More markers: clones/assets in staging systems (needs a setting for the
    systems), owner changes, audit gaps as a data gap.
- Not decided, left as built: a `BlueKill` copy is never deleted (few rows,
  the time frame hides old ones; after a change of the Alliance the old
  copies stay unused); the settings tabs stay flat (no grouping per main).
- Known quirks, left as is: a contact hostile only through its group shows
  the same standing twice when the Alliance is the source (reference, and the
  held badge of its Corporation or Alliance cell) and still reads "Name (Corp)" next to the Corporation
  column.

## Dev instance

- Installed editable, in `INSTALLED_APPS` of `myauth/settings/local.py`;
  migrations up to 0025 applied, `collectstatic` current, snapshot rebuilt
  2026-11-25 with 0.1.4 (none of the `[Unreleased]` work yet).
- `local.py` has a `## eos spy network` block with the sweep's beat entry.
  The periodic task row `contacts` (id 7) is disabled; the hourly
  `CELERYBEAT_SCHEDULE` entry in `local.py` is the one to keep. A Celery
  worker runs (`-P solo`), no beat: no periodic task fires on its own.
- aa-contacts holds tokens for Invidia Gloriae Comes (99003995) and Ether
  Element (98633815).
- `aa_dev` has no hostile Network partner, no ISK, contract or contacts
  marker and no capital contract of the Alliance: those pages and popups
  were only rendered in tests. Seeding corptools rows for them (journal,
  `Contract`, `CharacterContact`) needs the user's yes (foreign tables).
- Held data: 7 `CapitalContract` rows and the `SweepStats` row of the
  2026-11-20 hand run (no capital among them); 1 `CorporationAlliances` row;
  4 `BlueKill` rows with fake killmail IDs 99000000101-103 (Ether Element,
  test seed of unknown origin, never pruned); killtracker itself stores
  none (no beat).
- The configured Alliance holds 30 Corporations `T000`-`T029` without mains,
  apparently another app's leftover seed: ask before removing anything.
- `auth_permission` still has the stale `view_evidence` row; untouched.
