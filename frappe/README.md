# The Frappe kit

Four files. Two of them run. Portable to any Frappe bench, app or version — nothing here
hardcodes a path, a site, a doctype or a domain.

```
probe.py        where am I, and what is already true here          every session, ~1s
CONTRACTS.md    the ladder, then what frappe guarantees            per action
frame.py        what has not been thought of yet                   once per app or feature
README.md       this — the index, and what it does not establish
```

`CONTRACTS.md` opens with **§0 · I am about to create a file — any file**, because that row
fires before every other one: take the lowest rung that fits — a framework record, then a
low-code record, then app code — and write the line that says why the rung below cannot do it.

The `frappe-*` skills live in `skills/` and load **only in Frappe projects**. Link them into a
project once with `bash link-skills.sh [project dir]`; `detect.sh` reminds you in any Frappe
folder where they are not linked yet.

---

## Start here, every session

```sh
python3 probe.py                 # from anywhere inside a bench or an app
python3 probe.py --wide          # + every other bench on this disk
```

It prints the bench, the frappe version, the sites and whether `developer_mode` is on; the
reference implementations reachable **on this disk rather than in this bench**; what the app
you are in already measures; **which conventions this app has already chosen**; and the script
blocks with your bench and site already filled in.

Then read only the section of `CONTRACTS.md` whose trigger matches the action you are about to
take. If no trigger matches, no row applies.

Before deciding *what* to build:

```sh
python3 frame.py --new-app dukan                              # a whole new app: the runbook
python3 frame.py "Delivery Note" --app /path/to/apps/myapp/myapp   # one document
```

`--new-app` is the only ordered thing in the kit, because four of its steps cannot be redone
later without a migration: `developer_mode` before the first doctype, the module list, the
naming strategy, and the doctype routing. Everything else can be fixed in place.

Before saying it is done:

```sh
python3 probe.py --gate /path/to/apps/myapp/myapp     # exit 1 on a framework contract breach
```

---

## Why this shape, and not the shape of the material it came from

This was built from a research record and a manual. Both are honest and neither has this
shape, on purpose.

**The research is organised by evidence weight** — one move accounting for 6 of 13 defects,
then a tail. That is the right shape for a research report and the wrong one for a working
kit: a session doing a one-field change should not read a ranking of someone else's defect
tally. **The manual is organised by topic**, mirroring the concerns of the accounting app it
was extracted from, and points at a specific reference app in a specific bench. Neither
travels.

Re-cut from the same evidence by a different question — *what kind of belief was wrong?* —
the thirteen defects fall out as: **6 about scope** (what the document needed), **4 about
whether the operation actually did anything**, **2 about consequence** (the downstream
document), **1 about authority**. That is a partition you can act on, and it is why this kit
is a probe, a contract card and a scope generator rather than chapters.

**The one design rule, taken from the material and applied to itself:** a rule is in force
only if its countermeasure is a string you can paste or a command you can run. Anything that
could only be *described* was cut.

### Rare and frequent are separated — here is the reasoning, since you asked for it

They are separated, but **not by frequency**. Frequency is the symptom; the real split is
**what kind of evidence is even available at that moment.**

- **While you are building, execution is available.** You can run the thing, read the file
  back, run as the clerk. So the artifacts are *contracts and gates* — mechanical, checkable,
  identical in every Frappe project. `probe.py` + `CONTRACTS.md`. Cheap per hit, many hits.
- **While you are deciding what to build, nothing executes.** No gate can save you, because
  every check you can write at that moment is derived from the same model that is about to be
  wrong. The only counter to a narrow frame is **enumeration against a source outside the
  session** — a mature implementation's field list, the reversal list, the role list. So the
  artifact is a *generator that emits the enumeration with the commands already resolved*.
  `frame.py`. Expensive per hit, few hits, and worthless if consulted mid-build.

The evidence for the split is in the material itself: the highest-yield move in the whole
record — diffing against a mature reference — was run at **audit** time, after the app was
built, and the record says so explicitly. It is a design-time move filed in a build-time
document. Separating them is what puts it back where it fires.

A third moment turned out to matter as much: **arriving at an app you did not build.** The
central finding upstream of this kit is *good at establishing a convention, poor at inheriting
one* — and neither source document has anywhere for that moment to live. That is what
`probe.py`'s "convention this app has already chosen" section is for. Match it; do not
re-establish it.

### Absorbed from the bench-level `Frappe-first protocol`

That file was written earlier, from the problem as it was being felt. Five things in it were
not in the research, the manual, or the first cut of this kit, and are now here:

| from the protocol | where it landed | made mechanical how |
|---|---|---|
| **Gate 1, the ladder** — take the lowest rung that fits, state rung + why | `CONTRACTS.md` **§0 / L1**, `frame.py` §7 | the rung inventory is verified present in the frappe on this machine, and the reference counts show which rungs the references actually use (43 dashboard charts, 41 number cards, **0 workflows**) |
| **Gate 0, boilerplate or real?** | `probe.py` "is the code real, or is it what the generator emitted?" | counted: erpnext 76% / hrms 78% real controllers, 83% / 87% real form scripts |
| **Gate 4, validation at the moment of the mistake — never only at save, never silent** | `CONTRACTS.md` **F20**, `probe.py` display-vs-intervene split | the event list splits into events that fire when a form *appears* and events that *intervene*; erpnext 31 intervening files / 116 client throws, hrms 7 / 19, the surveyed failure 0 / 0 |
| **Gate 4, three audiences** — end user · configurator · next developer | `frame.py` §8 | the only part of your file with no analogue anywhere in the research; it is judgement, so it sits in the design-time generator, not in a gate |
| **Gate 5, a negative test per validation** | `CONTRACTS.md` **F21** | a validation that has never refused anything has been typed, not tested |
| **Gate 2, prior art includes permission-carrying contracts** | `CONTRACTS.md` F7, extended | rewriting a util costs maintenance; rewriting `get_list` scoping silently drops the permission layer, and nothing tells you |
| **Gate 3, both sides of every write** | `CONTRACTS.md` **F14** and **F26** | F14 is a record in the database and not on disk. F26 is the same question inverted — a doctype folder on disk and not in the database, which the next `bench migrate` puts straight back |

Two things in the protocol this kit **replaces rather than keeps**:

- **The bench adapter block** — the one part you marked non-portable and edit by hand per
  bench. `probe.py` detects all of it, including which sites have `developer_mode` on.
- **Gate 2's search scope**, "grep `apps/frappe` (+ installed apps)". That scoping is exactly
  what missed `StatusUpdater`, `get_gl_dict` and `get_balance_on` in the research: correctly
  scoped, and the richest prior art in the ecosystem was one bench away on the same disk.
  `probe.py --wide` resolves the grep across every bench it can find.

And one difference of kind: your gates are *stated in order and passed visibly*; this kit is
*indexed by trigger*. Both are needed and they are not the same discipline — a sequence is
what you follow, an index is what fires. The sequence lives in `frame.py` §9, which is a
checklist with commands beside each line.

---

## What is deliberately absent

There are 122 `frappe-*` skills installed on this machine. Counted across all of them:

```
not self.istable              0 skills        before_export        0 skills
base_document.py              0 skills        export_to_files      0 skills
remove_orphan / Orphaned      0 skills        StatusUpdater        0 skills
DocPerm flags default to 1    0 skills        _validate_links      0 skills
check_if_submittable          0 skills        get_user_default_value  0 skills
```

Every one of those is a framework contract whose breach is silent or destructive. **None of
them is documented anywhere in the catalogue.** So this kit carries only what that catalogue
does not: fieldtype tables, syntax examples and API reference already exist and are not
repeated here.

Five claims that appear in the source material are **deliberately not carried forward**,
because they were refuted or withdrawn by measurement: test-stub counts as a quality signal,
behaviour-outside-modules as a structural defect, file line-counts as the shape of a problem,
a permission-omission rate measured from JSON, and a client-code volume target. Each is listed
with what killed it at the end of `CONTRACTS.md`, so they are not quietly re-acquired.

---

## Portability

Every command in this kit resolves its own paths. To use it on another project, pick one:

```sh
cp -r <this dir> /path/to/other/project/.frappe-kit      # travels with the repo
```
```sh
cp -r <this dir> ~/.claude/skills/frappe-kit             # available in every session
```
```sh
alias fprobe='python3 <this dir>/probe.py'               # nothing copied at all
```

`probe.py` and `frame.py` are stdlib-only, never import frappe, and run outside a bench.
`frame.py` expects `probe.py` beside it.

**Verified portable, not asserted.** `python3 probe.py <bench> --app <app> --gate` was run
against **8 apps in 5 benches across frappe `16.0.0-dev` and `17.0.0-dev`**, from inside an app
package, from a bench root, and from an unrelated working directory:

```
6 apps  exit 0, 0 breaches       including both reference apps
2 apps  exit 1, 3 breaches each  the one lineage that shipped a private doctype generator
```

Those two are the same two the upstream survey separates at 86% and 100% child-table
deviation; this kit re-derives the split from the source contract without being told about it.

Line numbers are **not** portable and are not shipped as facts. Every contract carries a
`locate:` command instead; `make_controller_template` is `doctype.py:862` in 16.0.0-dev and
`:901` in 17.0.0-dev, and the mechanism is identical in both.

---

## What this kit does not establish

- **No session other than the one that wrote it has used it.** Every claim that it changes an
  outcome is design intent. The first real use is the test.
- **The gate has never been installed in a real repository**, here or upstream. The prediction
  that commit-time gating changes outcomes is untested. What *is* measured is the cost curve
  it argues from: on one lineage, at handoff 53 stray files were automatically removable and 1
  needed a human; ten weeks later 26 of those stubs had been filled with real code and become
  load-bearing.
- **Acceptance sentences are unproven as a prevention device.** Written after a build they
  converted eight known gaps into failing assertions, which is conversion, not detection.
  Written first, they have never been tried. `frame.py` says so where it asks for them.
- **Nothing about a human maintainer was ever measured**, anywhere upstream of this. Every
  claim about maintainability in the source material is inferred from structure. Do not cite
  this kit as a maintainability argument.
- **The reference bands rest on two apps from one publisher.** erpnext and hrms are both
  Frappe Technologies. A well-regarded third-party app would firm the bands and might break
  some.
- **`probe.py` never executes a document.** It cannot tell you the app works. Only running a
  transaction and reading back the *downstream* document can, and that is `CONTRACTS.md` F17.

---

## This kit run against its own rules

- **The generator was used, not hand-written.** An existing `structure_check.py` was the
  starting point; every band in `probe.py` was then **re-measured by the script's own
  definitions** rather than copied from prose, because a band computed under someone else's
  definition is not comparable with what the script prints. Two published figures moved when
  re-measured under one consistent definition, and both are noted at the band.
- **Assertions are tagged.** `[F]` framework source, `[R]` measured in erpnext + hrms, `[A]`
  mine. **Only `[F]` gates.** No `[A]` row can fail a build.
- **One published gate was corrected.** A threshold of "zero doctype directories without
  `__init__.py`, because every reference app has zero" is contradicted by the same record's
  own table, which shows erpnext at 2. Both were re-counted: measured by DocType JSON, erpnext
  is 0/527 and hrms 0/159; the two directories are `stock/doctype/sales_bom` and
  `sales_bom_item`, which contain no DocType at all. The gate is at zero and the reason is now
  the measurement rather than the claim.
- **Adds and deletes.** This kit adds 4 files and deletes 0. The merge candidate is
  `frappe-manual/checks/structure_check.py`, which `probe.py` supersedes — it carries a
  permission baseline (37% / 34%) that its own manual withdrew as unmeasurable. It is not
  deleted here because the manual is evidence, not a working tool, and deleting evidence is
  not mine to do.
- **What could not be run.** Nothing in this kit has been executed against a *live site* —
  the least-privileged run in F6, the settlement readback in F17, and every command in
  `frame.py` §6 are static text here. They were executed as file-level operations only.
  Redis was down throughout the upstream work for the same reason.
