#!/usr/bin/env python3
"""frame — the scope document, generated, with the commands already in it.

Run this ONCE before building a document, a feature or an app. Not per edit.
It is the opposite kind of thing from `probe.py`: probe measures what is, frame
enumerates what has not been thought of yet.

    python3 frame.py "Delivery Note"
    python3 frame.py "Delivery Note" --ref "Sales Invoice"
    python3 frame.py "Loan" --kind master
    python3 frame.py --references                # what is diffable on this disk
    python3 frame.py "Delivery Note" -o -        # to stdout instead of a file

Why a generator and not a checklist: the one move in the record that outperformed
everything else — comparing your document field-by-field against a mature implementation of
the same shape — found 6 of 13 defects, and it was run at AUDIT time, after the app was
built. Run at design time the same comparison puts those things in scope instead of finding
them missing four hours later. A checklist that says "compare against a reference" does not
survive contact with a session; a file containing the exact command, with the reference path
already resolved, does.

stdlib only. Never imports frappe.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from glob import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    from probe import find_bench_upward, scan_for_benches, bench_apps, jload  # noqa: E402
except ImportError:                                                          # pragma: no cover
    sys.exit("frame.py expects probe.py beside it")

# The reversal list. Every one of these is a transaction already made, being undone or
# altered. Tax, returns, currency and posting-time all went missing from one build at once,
# and every one of them is a reversal or a restatement of a transaction.
REVERSALS = [
    ("cancel", "the document is withdrawn after submission"),
    ("amend", "a cancelled document is re-issued with corrections"),
    ("return / credit note", "the counterparty sends it back"),
    ("refund", "money or goods go back the other way"),
    ("adjustment", "the figure is corrected without a new transaction"),
    ("correction", "a mistake in a submitted document is fixed"),
    ("partial fulfilment", "some of it happens and the rest is outstanding"),
    ("re-issue", "the same obligation is issued again"),
    ("settlement", "another document discharges this one"),
    ("after period close", "any of the above, once the period is locked"),
]

# The dimensions a document acquires that are not the forward path and are routinely missed.
DIMENSIONS = [
    ("posting date / time", "can this be backdated? if the answer is 'it is stamped at save',"
                            " you cannot enter yesterday's work"),
    ("currency", "is there more than one? every monetary field then needs a company-currency twin"),
    ("tax / charges", "an added amount that is not the line total"),
    ("company / branch scoping", "the Link field that User Permissions will bind to — without it"
                                 " there is no row-level restriction later"),
    ("attachments / evidence", "does anything have to be attached for this to be valid"),
    ("who sees it in a list", "the framework never generates _list.js; both references"
                              " hand-write it 77 and 30 times"),
    ("what it connects to", "_dashboard.py — erpnext 68, hrms 27. A document with no"
                            " connections panel hides its own consequences"),
]

KIND_ROUTER = """\
Does it exist only inside another document?      -> child table (istable)
Is there exactly one of it, app-wide?            -> single / settings (issingle)
Is it submitted, and does it have consequences?  -> transaction (is_submittable)
Is it queried AS a hierarchy?                    -> tree master (is_tree + NestedSet)
Otherwise                                        -> master
"""


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def scrub(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def find_reference_doctypes(benches):
    """Every doctype JSON in erpnext/hrms/frappe reachable on this disk.

    De-duplicated by (app, doctype): the same frappe ships in every bench on the machine,
    and 4,000 duplicate rows is not a richer choice of reference.
    """
    seen, out = set(), []
    for b in benches:
        for app in bench_apps(b):
            if app not in ("erpnext", "hrms", "frappe"):
                continue
            root = os.path.join(b, "apps", app, app)
            for p in glob(os.path.join(root, "**", "doctype", "*", "*.json"), recursive=True):
                if "__pycache__" in p:
                    continue
                d = jload(p)
                if not d or d.get("doctype") != "DocType":
                    continue
                name = d.get("name") or os.path.basename(p)[:-5]
                key = (app, name)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"name": name, "app": app, "path": p, "app_root": root,
                            "fields": len(d.get("fields", [])),
                            "submittable": bool(d.get("is_submittable")),
                            "istable": bool(d.get("istable"))})
    return out


def rank_references(refs, target, kind):
    """Rank candidates: same shape first, then name overlap, then size."""
    words = {w for w in re.split(r"\W+", target.lower()) if len(w) > 2}
    scored = []
    for r in refs:
        if r["istable"]:
            continue
        s = 0
        rw = {w for w in re.split(r"\W+", r["name"].lower()) if len(w) > 2}
        s += 40 * len(words & rw)
        if kind == "transaction" and r["submittable"]:
            s += 20
        if kind and kind != "transaction" and not r["submittable"]:
            s += 10
        if r["app"] == "frappe":
            s -= 15          # frappe's own doctypes are the framework, not an application
        s += min(r["fields"], 120) / 12.0          # a richer reference teaches more
        scored.append((s, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored]


def build(target, kind, refs_ranked, app_path, bench):
    ref = refs_ranked[0] if refs_ranked else None
    alts = refs_ranked[1:5]
    mine_guess = ""
    if app_path:
        cand = glob(os.path.join(app_path, "**", "doctype", scrub(target), f"{scrub(target)}.json"),
                    recursive=True)
        if cand:
            mine_guess = cand[0]
        else:
            module = "<module>"
            try:                       # modules.txt is the app's own answer, not a guess
                with open(os.path.join(app_path, "modules.txt")) as fh:
                    mods = [scrub(x) for x in fh.read().split("\n") if x.strip()]
                if len(mods) == 1:
                    module = mods[0]
                elif mods:
                    module = "{" + "|".join(mods) + "}"
            except OSError:
                pass
            mine_guess = os.path.join(app_path, module, "doctype",
                                      scrub(target), f"{scrub(target)}.json")

    L = []
    a = L.append
    a(f"# Scope — {target}")
    a("")
    a(f"Generated {date.today().isoformat()} by `frame.py`. **Fill it in before building.** "
      f"Nothing below is optional to *answer*; most of it is fine to answer `n/a`.")
    a("")
    a("> The point is not that every line applies. It is that a line you never saw cannot be "
      "declined. In the record this kit is built from, eight of sixteen things a shop had to "
      "be able to do were failing, and **not one of them was in an area anyone had asked "
      "about**.")
    a("")
    a("---")
    a("")

    # ---------------------------------------------------------------- 1 acceptance
    a("## 1 · What must be true when this is done")
    a("")
    a("Sentences in the language of the person who uses this. **No framework nouns** — no "
      "doctype, no field, no controller, no status. Write 5–20. Then make each one executable "
      "against a live site: post the documents, read the result, roll back.")
    a("")
    a("```")
    a("A <role> must be able to ______________________________________")
    a("A <role> must be able to ______________________________________")
    a("A <role> must be able to ______________________________________")
    a("A <role> must NOT be able to __________________________________")
    a("After ____________, a <role> sees ____________________________")
    a("When ____________ is undone, ________________________________")
    a("```")
    a("")
    a("Their one essential property is **provenance**: they come from the domain, not from the "
      "implementation. An app that is internally consistent and externally wrong can satisfy "
      "every other check in this kit. It cannot satisfy these.")
    a("")
    a("> **Stated honestly: this step is unproven.** In the record these sentences were "
      "written *after* a build and discovered nothing new — they converted eight already-known "
      "gaps into failing assertions, which is real, and is not detection. Whether writing them "
      "first prevents defects has never been tried. It costs ten minutes and needs no knowledge "
      "of the codebase.")
    a("")

    # ---------------------------------------------------------------- 2 reference diff
    a("## 2 · Diff against a mature implementation — before building, not after")
    a("")
    if ref:
        a(f"Closest reference on this disk: **{ref['name']}** ({ref['app']}, "
          f"{ref['fields']} fields).")
        if alts:
            a("Others worth a look: " + ", ".join(f"`{r['name']}` ({r['app']})" for r in alts) + ".")
        a("")
        a("```sh")
        a("python3 - <<'PY'")
        a("import json")
        a(f'REF  = "{ref["path"]}"')
        a(f'MINE = "{mine_guess or "<your doctype json>"}"')
        a('LAYOUT = {"Section Break", "Column Break", "Tab Break", "HTML", "Heading"}')
        a('e = {f["fieldname"]: f.get("fieldtype") for f in json.load(open(REF))["fields"]'
          ' if f.get("fieldtype") not in LAYOUT}')
        a('try:    m = {f["fieldname"] for f in json.load(open(MINE))["fields"]}')
        a('except FileNotFoundError: m = set()   # not built yet — that is the point')
        a('for k in sorted(set(e) - m): print(f"{e[k]:<18} {k}")')
        a("PY")
        a("```")
        a("")
        a("Artifact kinds the reference ships that you do not:")
        a("")
        a("```sh")
        refdir = os.path.dirname(ref["path"])
        a(f"REF={refdir}")
        a(f"MINE={os.path.dirname(mine_guess) if mine_guess else '<your doctype dir>'}")
        a("for k in '*_list.js' '*_dashboard.py' 'test_records.json' '*.js' '*.py'; do")
        a('  printf "%-20s ref=%s  mine=%s\\n" "$k" \\')
        a('    "$(find $REF -name "$k" 2>/dev/null | wc -l)" \\')
        a('    "$(find $MINE -name "$k" 2>/dev/null | wc -l)"')
        a("done")
        a("```")
    else:
        a("**No reference implementation was found on this disk.** That is a real limit, not a "
          "formality: this move works because Frappe has erpnext and hrms. A domain with no "
          "canonical implementation has nothing to diff against and this section does not "
          "travel there. Clone erpnext somewhere readable, or skip section 2 and say so here.")
    a("")
    a("**Write down every field you decide NOT to carry, and why:**")
    a("")
    a("| field the reference has | carried? | why not |")
    a("|---|---|---|")
    a("|  |  |  |")
    a("")
    a("Deciding not to carry something is fine. Not knowing it exists is what produced the "
      "failures. **Six of thirteen defects in one build came from exactly this comparison, run "
      "once, too late.**")
    a("")

    # ---------------------------------------------------------------- 3 reversals
    a("## 3 · Reversals — name each one before the forward path exists")
    a("")
    a("Discovering these after the fields are built means a migration.")
    a("")
    a("| reversal | means here | answer |")
    a("|---|---|---|")
    for name, gloss in REVERSALS:
        a(f"| **{name}** | {gloss} | |")
    a("")
    a("A document type that cannot express *\"this one was sent back\"* will grow a field "
      "called `is_cancelled_maybe` instead. erpnext gives returns their own shared module of "
      "1,343 lines — that is what treating a reversal as a first-class case costs, and it is "
      "cheaper than the alternative.")
    a("")

    # ---------------------------------------------------------------- 4 dimensions
    a("## 4 · Dimensions that are not the forward path")
    a("")
    a("| dimension | why it is asked | answer |")
    a("|---|---|---|")
    for name, why in DIMENSIONS:
        a(f"| **{name}** | {why} | |")
    a("")

    # ---------------------------------------------------------------- 5 state
    a("## 5 · State — split it before writing either kind")
    a("")
    a("```")
    a("a PERSON decides it        -> Workflow engine, declarative, no python   (CONTRACTS F9)")
    a("OTHER DOCUMENTS decide it  -> recompute, never adjust                   (CONTRACTS F8)")
    a("```")
    a("")
    a("| state / figure | who decides it | mechanism | source documents | bound to |")
    a("|---|---|---|---|---|")
    a("|  |  |  |  |  |")
    a("")
    a("For every derived row, name **one** recompute function, the `docstatus: 1` filter, and "
      "every event it binds to — your own `on_submit` / `on_cancel`, plus the settling "
      "document's, via `doc_events` if it lives in another app. If a `+=` or `-=` appears "
      "anywhere near the stored figure, the design is gone.")
    a("")

    # ---------------------------------------------------------------- 6 authority
    a("## 6 · Authority")
    a("")
    a("| role | does what | must NOT be able to |")
    a("|---|---|---|")
    a("| `<Domain> User` | the work | |")
    a("| `<Domain> Manager` | approve · cancel · amend · configure | |")
    a("| `System Manager` | administrative, not a business role | |")
    a("")
    a("Median across both references is **3 permission rows per non-child doctype** "
      "(erpnext max 11, hrms max 8). Do not invent a role per doctype.")
    a("")
    a("Nine DocPerm flags default to **1**, so an omitted flag is a granted flag, and "
      "`before_export` strips the zeros from the JSON — **the permission set cannot be "
      "reviewed by reading files.** Run it as the person:")
    a("")
    site = ""
    if bench:
        sites = [os.path.basename(p) for p in glob(os.path.join(bench, "sites", "*"))
                 if os.path.isfile(os.path.join(p, "site_config.json"))]
        site = sites[0] if sites else ""
    a("```sh")
    a(f"cd {bench or '<bench>'}/sites && ../env/bin/python - <<'PY'")
    a("import frappe")
    a(f'frappe.init(site="{site or "<site>"}", sites_path="."); frappe.connect()')
    a('frappe.set_user("<the least-privileged user who must still be able to work>")')
    a(f'for p in ("read","write","create","submit","delete","cancel","amend"):')
    a(f'    print(p, frappe.has_permission("{target}", ptype=p))')
    a("frappe.destroy()")
    a("PY")
    a("```")
    a("")

    # ---------------------------------------------------------------- 7 shape
    a("## 7 · Shape and the decisions this app makes once")
    a("")
    a("```")
    a(KIND_ROUTER.rstrip())
    a("```")
    a("")
    a(f"**This one is a:** `{kind or '____________'}`")
    a("")
    a("### One document, or two? — collapse below the waterline, separate above it")
    a("")
    a("Anything a user **names**, **reaches**, or is **authorised for** gets its own doctype. "
      "Anything only the system touches is shared. Three tests, and failing any one means "
      "separate:")
    a("")
    a("| test | if the answer is no |")
    a("|---|---|")
    a("| Do users call them **the same thing**? | separate. A cash sale and a credit sale are "
      "two words in every accounting package a client has used before, and habit is a real "
      "cost to fight for no gain |")
    a("| Is the **authority** to perform them the same? | separate. Two doctypes make it a "
      "DocPerm row — rung 1, declarative, fails safe. One doctype with a type flag makes it a "
      "role check inside `validate`, which is rung 3 and can regress silently |")
    a("| Is the **identity stable from every door**? | separate. A filtered list view is a "
      "route, and identity that depends on the route is not identity — the awesomebar, a "
      "breadcrumb, a connections panel and a typed URL all land on the unfiltered list. Frappe "
      "also remembers a user's list filters, so the failure is not \"they see too much\" but "
      "\"they cannot find it\" |")
    a("")
    a(f"**`{target}` is:** `one document` / `two, sharing a base` — ____________, because "
      "____________")
    a("")
    a("> Sharing belongs **below** the line: one controller base, one child table across "
      "several parents (framework-native — `Has Role` serves nine parents inside frappe "
      "alone). Duplicating a dozen fields of schema between siblings is cheap; duplicating "
      "behaviour is not, and merging or splitting a document type after clients are live is a "
      "data migration in either direction.")
    a("")
    a("### The rung — take the lowest that fits, and say why the one below cannot")
    a("")
    a("```")
    a("Rung 1  a framework record or a DocField property   (data, not code)")
    a("Rung 2  a Client Script / Server Script record      (site tweak; promote when it is product)")
    a("Rung 3  app code: controller, form .js, report, page, hook, whitelisted method")
    a("```")
    a("")
    a("| deliverable in this scope | rung | because rung below cannot ______ |")
    a("|---|---|---|")
    a("|  |  |  |")
    a("|  |  |  |")
    a("")
    a("Rung 1 is not a short list. Confirmed present in frappe: `depends_on`, "
      "`mandatory_depends_on`, `read_only_depends_on`, `fetch_from`, `fetch_if_empty`, "
      "`default`, `link_filters`, `non_negative`, `set_only_once`, `precision`, `unique`, "
      "`in_list_view`, `in_standard_filter` — plus **Workflow · Document Naming Rule · "
      "Notification · Print Format · Dashboard Chart · Number Card · Workspace · Web Form · "
      "Assignment Rule · Auto Repeat · Webhook · List View Settings · DocType Link · "
      "Custom Field · Property Setter**.")
    a("")
    a("**Both directions are failures.** Two hundred custom lines where a record does it, and "
      "a flimsy record where the product needs real code. `probe.py` prints how much of this "
      "app's code is real versus what the generator emitted — the references sit at 76% / 78% "
      "real controllers and 83% / 87% real form scripts.")
    a("")
    a("Run `python3 probe.py <app_path>` and copy the answers this app has **already** given. "
      "Matching an existing convention is the failure mode this whole kit exists around — the "
      "output of an app built by imitation is uniform, and uniform with a private system that "
      "exists nowhere else.")
    a("")
    a("| decision | this app already does | mine |")
    a("|---|---|---|")
    for d in ("naming: `naming_series` field or fixed `autoname` string",
              "base class: `Document` or a shared controller",
              "client: flat handlers or a class hierarchy",
              "`track_changes` on masters",
              "`extend_doctype_class` or `override_doctype_class`"):
        a(f"| {d} | | |")
    a("")

    # ---------------------------------------------------------------- 8 three audiences
    a("## 8 · Done means three different people are served")
    a("")
    a("Every one of these has been shipped broken while the other two were fine. Answer each "
      "line or write `n/a` with a reason.")
    a("")
    a("**The end user — the screen**")
    a("")
    a("- [ ] Link fields are filtered to what can actually be chosen (`set_query`, or "
      "`link_filters` where it is static)")
    a("- [ ] values that come from a linked document are fetched, not retyped (`fetch_from`)")
    a("- [ ] **a mistake is refused at the moment it is made — not only at save, and never "
      "silently.** Both references throw client-side (erpnext 116, hrms 19); an app surveyed "
      "with 165 client files threw 0 times and used only events that fire when the form "
      "appears")
    a("- [ ] loading / empty / error states exist, with a way back")
    a("- [ ] it is reachable — a workspace shortcut, a nav entry, a list view someone opens")
    a("- [ ] the list view shows the state a user actually scans for (`_list.js` — erpnext "
      "writes 77, hrms 30; the framework generates none)")
    a("")
    a("**The configurator — the desk**")
    a("")
    a("- [ ] every settings field validates at save and names the exact row that is wrong")
    a("- [ ] pickers offer only what the system can actually honour")
    a("- [ ] **configuration the system cannot honour is rejected, not quietly dropped**")
    a("- [ ] every hardwired policy has a decision surface — a field on a settings single "
      "with a default that is safe when never set — or a one-line note saying why not")
    a("")
    a("**The next developer**")
    a("")
    a("- [ ] the module docstring says *why* it exists and what contract it mirrors")
    a("- [ ] no bare `except` that swallows an error — log it or throw it (F16: two defects "
      "surfaced only because an operation was allowed to fail loudly)")
    a("- [ ] constants shared between server and renderer live in one place")
    a("- [ ] every non-child doctype has a controller and a form script doing real work, **or "
      "one line saying why not** — usually: the declarative layer already covers it")
    a("")

    # ---------------------------------------------------------------- 9 gate
    a("## 9 · The gate this scope becomes")
    a("")
    a("Nothing above is done until each line below has a command beside it that was run.")
    a("")
    a("```sh")
    a(f"python3 probe.py --gate {app_path or '<app_path>'}   # framework contracts, exit 1 on breach")
    a("```")
    a("")
    a("- [ ] every sentence in §1 is an assertion that runs against a live site")
    a("- [ ] §2 diff run, and every uncarried field has a row in the table")
    a("- [ ] every §3 reversal answered, `n/a` included")
    a("- [ ] every §4 dimension answered")
    a("- [ ] every §5 derived figure recomputes, and cancelling the source restores it")
    a("- [ ] §6 run as the least-privileged user **and** as an admin, output pasted")
    a("- [ ] §7 rung named for every deliverable, with what the rung below cannot do")
    a("- [ ] §8 all three audiences answered")
    a("- [ ] every validation added has a negative test that proves it throws")
    a("- [ ] the document executed once end to end, and the **downstream** document read back")
    a("- [ ] `probe.py --gate` exits 0")
    a("")
    a("Tag each assertion you wrote `(a) mine · (b) framework source · (c) the user's stated "
      "requirement · (d) an external spec`. **All `(a)` means get one non-`(a)` before running "
      "it** — six gates, a linter and a full end-to-end test were once green, all `(a)`, and "
      "missed 8 of 16 things the shop had to do.")
    a("")
    a("A green gate means the files were made through the framework and submittables can be "
      "amended. It is not a claim that this works. Only the last two boxes are.")
    return "\n".join(L) + "\n"


def build_app(app, bench, site, version, refs):
    """The new-app runbook. Ordering matters here in a way it does not anywhere else:
    four of these steps cannot be done later without a migration."""
    L = []
    a = L.append
    b = bench or "<bench>"
    s = site or "<site>"
    a(f"# New app — {app}")
    a("")
    a(f"Generated {date.today().isoformat()} by `frame.py --new-app`. "
      f"Detected bench `{b}`, site `{s}`, frappe `{version or 'unknown'}`.")
    a("")
    a("**Steps 2 and 4 cannot be redone later without a migration.** Everything else can be "
      "fixed in place. That is the whole reason this file is ordered.")
    a("")
    a("---")
    a("")
    a("## 0 · Before the app exists")
    a("")
    a("```sh")
    a("python3 probe.py --wide          # bench, site, version, developer_mode, reference apps")
    a("```")
    a("")
    a("**`developer_mode` must be on before you create a single doctype.** With it off, "
      "doctypes you create live only in the database and no file is ever written — and nothing "
      "warns you.")
    a("")
    a("```sh")
    a(f"grep developer_mode {b}/sites/common_site_config.json {b}/sites/{s}/site_config.json")
    a(f"bench --site {s} set-config developer_mode 1")
    a("```")
    a("")
    a("## 1 · Create the app and install it")
    a("")
    a("```sh")
    a(f"cd {b}")
    a(f"bench new-app {app}")
    a(f"bench --site {s} install-app {app}")
    a("```")
    a("")
    a("What that actually scaffolds, read from `frappe/utils/boilerplate.py`:")
    a("")
    a("```")
    a(f"{app}/{app}/modules.txt          <- contains the APP TITLE, verbatim")
    a(f"{app}/{app}/<scrubbed title>/    <- a default module folder, with __init__.py")
    a(f"{app}/{app}/hooks.py  patches.txt  config/  public/{{css,js}}  templates/  www/  patches/")
    a("```")
    a("")
    a("> **Decide now: keep the default module, or declare your own.** `modules.txt` must list "
      "every module name **spelled exactly as the DocType's `module` field**, or the doctype is "
      "not found on migrate. If you declare your own and leave the default listed, you ship an "
      "empty module directory forever. This is untidiness, not breakage — but decide it once.")
    a("")
    a("## 2 · The decisions that cannot be retrofitted")
    a("")
    a("Write these into the app's own `AGENTS.md` / `CLAUDE.md` before the first doctype. Both "
      "references are mature and **disagree** on every one, so there is nothing to inherit — "
      "an app that mixes both sides of any of them is worse than one that picks the \"wrong\" "
      "side consistently.")
    a("")
    a("| decision | options | mine | why |")
    a("|---|---|---|---|")
    a("| **naming a transaction** | `naming_series` Select field (erpnext 46/81) · fixed "
      "`autoname` string (hrms 38/53) | | **retrofitting `naming_series` later means a "
      "migration** |")
    a("| **naming a master** | `field:<natural key>` — 51%/53% of masters in both | | a master "
      "with a serial number usually is not a master |")
    a("| **base class** | `Document` · a shared controller | | hrms: 147 × `Document`. Create a "
      "shared base only when 2+ documents *already* share machinery |")
    a("| **client architecture** | flat `frappe.ui.form.on` · ES6 class hierarchy | | flat "
      "until a second and third document need the same behaviour |")
    a("| **`track_changes` on masters** | on · off | | on for anything whose past values "
      "someone will dispute |")
    a("| **roles** | `<Domain> User` + `<Domain> Manager` + `System Manager` | | median 3 "
      "permission rows per doctype in both references. Do not invent a role per doctype |")
    a("| **one document or two** | one doctype with a type flag · two doctypes on a shared "
      "base | | separate whenever users **name** them differently, the **authority** differs, "
      "or identity must hold **from every door**. Merging or splitting later is a data "
      "migration either way |")
    a("| **settings** | one settings single per *module*, not per feature | | erpnext 31 "
      "singles / 11 modules, hrms 6 / 2 |")
    a("")
    a("## 3 · What must be true when this app is done — before any doctype")
    a("")
    a("Sentences in the language of the person who will use it. No framework nouns. 5–20 of "
      "them. Then make each executable against the live site.")
    a("")
    a("```")
    a("A <role> must be able to ______________________________________")
    a("A <role> must be able to ______________________________________")
    a("A <role> must NOT be able to __________________________________")
    a("When ____________ is undone, ________________________________")
    a("```")
    a("")
    a("An app that is internally consistent and externally wrong passes every other check in "
      "this kit. It cannot pass these. **[Unproven as prevention: written after a build they "
      "converted eight known gaps into failing assertions, which is conversion, not detection. "
      "Written first they have never been tried. Ten minutes, no codebase knowledge needed.]**")
    a("")
    a("## 4 · Route every doctype before creating any of them")
    a("")
    a("```")
    a(KIND_ROUTER.rstrip())
    a("```")
    a("")
    a("| doctype | kind | naming | submittable | notes |")
    a("|---|---|---|---|---|")
    a("|  |  |  |  |  |")
    a("")
    a("**[R] Expected proportions**, so a badly-shaped inventory shows up now rather than in "
      "month three:")
    a("")
    a("```")
    a("                  erpnext        hrms")
    a("child table       248 (47%)     54 (34%)   <- the LARGEST category in both")
    a("master            154 (29%)     45 (28%)")
    a("transaction        80 (15%)     53 (33%)   <- domain-dependent, both normal")
    a("single/settings    31  (6%)      6  (4%)")
    a("tree master        14  (3%)      1  (1%)   <- rare and deliberate")
    a("```")
    a("")
    a("An app with almost no child tables has flattened structures that should be tables. For "
      "each transaction, run `python3 frame.py \"<Doctype>\" --kind transaction` **before "
      "building it** — that is where the reversals and the reference diff live.")
    a("")
    a("## 5 · Create them through the framework")
    a("")
    a("**There is no `bench new-doctype` in this frappe** — the only doctype command is "
      "`reload-doctype`. Two ways exist, and hand-writing files is not one of them: the desk "
      "UI with developer mode on, or the script runner below.")
    a("")
    a("```sh")
    a(f"cd {b}/sites && ../env/bin/python - <<'PY'")
    a("import frappe")
    a(f'frappe.init(site="{s}", sites_path="."); frappe.connect()')
    a('frappe.set_user("Administrator")')
    a("")
    a("# 1. VERIFY ONE generated identifier before the batch (F2). A capitalize() loop once")
    a('#    produced `class Uom` for doctype `UOM`; bench migrate read the ImportError as a')
    a("#    deleted doctype and dropped the DocType row.")
    a('name = "UOM"')
    a('assert name.replace(" ", "").replace("-", "") == "UOM"')
    a("")
    a("# 2. then create. The framework emits json, py, __init__ — and js + test_ only when")
    a("#    istable is false. Never _list.js.")
    a("frappe.get_doc({")
    a('    "doctype": "DocType", "module": "<Module>", "name": "<Doctype Name>",')
    a('    "is_submittable": 0, "autoname": "<per step 2>",')
    a('    "fields": [')
    a('        # amended_from FIRST on anything submittable — the framework will not add it')
    a('        {"fieldname": "amended_from", "fieldtype": "Link", "options": "<this doctype>",')
    a('         "label": "Amended From", "hidden": 1, "read_only": 1, "no_copy": 1,')
    a('         "print_hide": 1, "ignore_user_permissions": 1},')
    a('    ],')
    a('    "permissions": [')
    a('        # every flag, INCLUDING the zeros. Nine default to 1; omitting delete grants it.')
    a('        {"role": "<Domain> User", "read": 1, "write": 1, "create": 1, "delete": 0,')
    a('         "submit": 1, "cancel": 0, "amend": 0,')
    a('         "report": 1, "export": 0, "share": 0, "print": 1, "email": 1},')
    a('    ],')
    a("}).insert()")
    a("")
    a("frappe.db.commit()      # without this it all rolls back AND the script still prints")
    a("frappe.destroy()        # every success message it contains")
    a("PY")
    a("```")
    a("")
    a("To add a field later: edit the **DocType document** and save. Never the JSON.")
    a("")
    a("## 6 · Declarative layer before any client code")
    a("")
    a("Put visibility, requiredness, read-only, defaults, static filters, sign constraints and "
      "immutability in the DocType JSON — `depends_on`, `mandatory_depends_on`, "
      "`read_only_depends_on`, `fetch_from`, `default`, `link_filters`, `non_negative`, "
      "`set_only_once`. Declarative beats imperative ~5:1 in both references.")
    a("")
    a("Client code is for three things only: a Link filter that reads a sibling field "
      "(`set_query`), a button that creates another document (`add_custom_button`), and a "
      "value that must be computed rather than copied. For anything else write the sentence "
      "*\"the declarative mechanism for this is ___, and it is insufficient because ___\"* — "
      "and if you cannot, use the mechanism.")
    a("")
    a("## 7 · Derived state, then the desk surface")
    a("")
    a("- Split it: a person decides → **Workflow record**, no python. Other documents decide "
      "→ **recompute, never adjust**, filtered to `docstatus: 1`, cache field and status in "
      "one function, bound to every event that can change it.")
    a("- Then the surface the references ship and a new app forgets: `_list.js` "
      "(erpnext 77, hrms 30 — the framework generates none), `_dashboard.py` connections "
      "(68 / 27), a Workspace, Number Cards (41 / 32), Dashboard Charts (43 / 33).")
    a("- **Workspaces, print formats, custom fields and notifications are database rows until "
      "you export them.** Doctypes export themselves; nothing else does.")
    a("")
    a("```python")
    a("from frappe.modules.export_file import export_to_files")
    a('export_to_files(record_list=[["Workspace", "<name>"]], record_module="<Module>")')
    a("```")
    a("")
    a(f"```sh")
    a(f"ls -la {b}/apps/{app}/{app}/<module>/workspace/<name>/   # read the DURABLE side")
    a("```")
    a("")
    a("## 8 · Before anyone else touches it")
    a("")
    a("```sh")
    a(f"cd {b}/sites && ../env/bin/python - <<'PY'")
    a("import frappe")
    a(f'frappe.init(site="{s}", sites_path="."); frappe.connect()')
    a('frappe.set_user("<clerk@example.com>")     # create this user if it does not exist')
    a('for dt in ["<DocType>", ...]:')
    a('    for p in ("read","write","create","submit","delete","cancel","amend"):')
    a('        print(dt, p, frappe.has_permission(dt, ptype=p))')
    a("frappe.destroy()")
    a("PY")
    a("```")
    a("")
    a("Reading the permission JSON does not work — `before_export` strips the zeros, so a "
      "denial and an omission are byte-identical on disk. One session run as a clerk rather "
      "than Administrator surfaced four permission defects immediately; it is the cheapest "
      "check in the whole record.")
    a("")
    a("## 9 · The gate")
    a("")
    a("```sh")
    a(f"python3 probe.py {b}/apps/{app}/{app}          # the full picture")
    a(f"python3 probe.py --gate {b}/apps/{app}/{app}   # exit 1 on a framework breach")
    a(f"bench --site {s} migrate 2>&1 | tee /tmp/migrate.log")
    a("grep -iE 'orphan|error|traceback|missing' /tmp/migrate.log   # the output, not the exit code")
    a("```")
    a("")
    a("- [ ] `developer_mode` was on before the first doctype")
    a("- [ ] step 2 decisions written down in the app, before the first doctype")
    a("- [ ] every §3 sentence is an assertion that runs")
    a("- [ ] one generated identifier verified before any batch")
    a("- [ ] every permission flag written, including the zeros")
    a("- [ ] `amended_from` on every user-submittable doctype")
    a("- [ ] every rung-1 record exported to files and confirmed with `ls`")
    a("- [ ] run once as the least-privileged user")
    a("- [ ] one transaction executed end to end, and the **downstream** document read back")
    a("- [ ] `probe.py --gate` exits 0 and `migrate` output read, not its exit code")
    a("")
    a("A green gate means the files were made through the framework and submittables can be "
      "amended. It is not a claim that the app works — only the last two boxes are.")
    if refs:
        a("")
        a(f"Reference implementations found on this disk: "
          f"{', '.join(sorted({r['app'] for r in refs}))}. Run "
          f"`python3 frame.py \"<Doctype>\"` per transaction to get the field diff resolved "
          f"against them.")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", help='what you are about to build, e.g. "Delivery Note"')
    ap.add_argument("--kind", choices=["transaction", "master", "child table",
                                       "single", "tree master"],
                    help="if you already know; otherwise §7 routes it")
    ap.add_argument("--ref", help="reference doctype name to diff against (else best match)")
    ap.add_argument("--app", help="path to the app package you are building in")
    ap.add_argument("--references", action="store_true",
                    help="list reference doctypes reachable on this disk and exit")
    ap.add_argument("--new-app", metavar="APP_NAME",
                    help="a whole new app: emit the ordered runbook instead of a doctype scope")
    ap.add_argument("--site", help="site name, when the bench has several")
    ap.add_argument("-o", "--out", help="output path, or - for stdout")
    args = ap.parse_args()

    bench = find_bench_upward(args.app or os.getcwd())
    benches = scan_for_benches()
    if bench and bench not in benches:
        benches.append(bench)

    if args.references:
        refs = find_reference_doctypes(benches)
        if not refs:
            sys.exit("no erpnext / hrms / frappe doctypes found on this disk")
        by_app = {}
        for r in refs:
            by_app.setdefault(r["app"], []).append(r)
        for app, rs in sorted(by_app.items()):
            sub = [r for r in rs if r["submittable"]]
            print(f"{app:10} {len(rs):4} doctypes  ({len(sub)} submittable)  {rs[0]['app_root']}")
        print("\nrun:  python3 frame.py \"<what you are building>\" [--ref \"<Reference Doctype>\"]")
        return

    if args.new_app:
        from probe import bench_sites, frappe_version
        site = args.site
        if bench and not site:
            sites, _ = bench_sites(bench)
            dev = [x["site"] for x in sites if x["developer_mode"]]
            site = (dev or [x["site"] for x in sites] or [None])[0]
        text = build_app(args.new_app, bench, site,
                         frappe_version(bench) if bench else None,
                         find_reference_doctypes(benches))
        out = args.out or f"SCOPE-app-{slug(args.new_app)}.md"
        if out == "-":
            sys.stdout.write(text)
            return
        if os.path.exists(out):
            sys.exit(f"{out} already exists.")
        with open(out, "w") as fh:
            fh.write(text)
        print(f"wrote {out}")
        print("  steps 2 and 4 cannot be redone later without a migration. Do them in order.")
        return

    if not args.target:
        ap.error("give me what you are about to build, --new-app <name>, or --references")

    app_path = None
    if args.app:
        app_path = os.path.abspath(args.app)
        if os.path.isdir(os.path.join(app_path, os.path.basename(app_path))):
            app_path = os.path.join(app_path, os.path.basename(app_path))
    elif os.path.isfile(os.path.join(os.getcwd(), "hooks.py")):
        app_path = os.getcwd()

    refs = find_reference_doctypes(benches)
    if args.ref:
        exact = [r for r in refs if r["name"].lower() == args.ref.lower()]
        ranked = exact or rank_references(refs, args.ref, args.kind)
    else:
        ranked = rank_references(refs, args.target, args.kind)

    text = build(args.target, args.kind, ranked, app_path, bench)

    out = args.out or f"SCOPE-{slug(args.target)}.md"
    if out == "-":
        sys.stdout.write(text)
        return
    if os.path.exists(out):
        sys.exit(f"{out} already exists — it is a scope you have already filled in. "
                 f"Pass -o <other path> if you really want a second one.")
    with open(out, "w") as fh:
        fh.write(text)
    print(f"wrote {out}")
    print(f"  reference chosen: {ranked[0]['name']} ({ranked[0]['app']})" if ranked
          else "  no reference implementation found on this disk — see §2")
    print("  fill in §1 before writing any code. Everything after it is gated on it.")


if __name__ == "__main__":
    main()
