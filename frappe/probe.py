#!/usr/bin/env python3
"""probe — what is true in THIS bench, right now.

Run it first, every session, before editing anything. Nothing else in this kit
hardcodes a path, a site or a version: it all refers to what this prints.

    python3 probe.py                      # detect from cwd, report
    python3 probe.py <app_path|bench>     # point it somewhere
    python3 probe.py --gate <app_path>    # framework contracts only, exit 1 on breach
    python3 probe.py --json <app_path>
    python3 probe.py --wide               # also scan the disk for other benches

stdlib only. Never imports frappe, so it runs outside a bench, in CI, anywhere.

WHY EACH MEASUREMENT IS HERE  (provenance tags, so you can weigh a failure)
  [F] verified in frappe source on this machine — a contract, gates
  [R] measured in erpnext + hrms — a reference band, never gates
  [A] the author's judgement — informational only, never gates

The [F] rows are re-locatable in whatever frappe version you have: every one
prints its own `locate:` command. Line numbers drift between versions
(make_controller_template is doctype.py:862 in 16.0.0-dev and :901 in 17.0.0-dev);
the mechanisms do not.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter
from glob import glob

# --------------------------------------------------------------------------- [F] contracts
# Each: (id, what frappe does, how to re-locate it in any version)
CONTRACTS = [
    ("F1", "child tables get no .js and no test_ file; every doctype dir gets __init__.py",
     "grep -n 'if not self.istable' -A4 apps/frappe/frappe/core/doctype/doctype/doctype.py"),
    ("F2", "controller class name == doctype name minus spaces and hyphens; a mismatch is "
           "an ImportError, which bench migrate reads as a deleted doctype and drops the row",
     "grep -n 'replace(\" \", \"\")' apps/frappe/frappe/model/base_document.py ; "
     "grep -n 'def remove_orphan_doctypes' -A20 apps/frappe/frappe/model/sync.py"),
    ("F3", "nine DocPerm flags default to 1 — an omitted flag is a granted flag",
     "python3 -c \"import json;d=json.load(open('apps/frappe/frappe/core/doctype/docperm/"
     "docperm.json'));print([(f['fieldname'],f.get('default')) for f in d['fields'] "
     "if f['fieldtype']=='Check'])\""),
    ("F4", "before_export strips every falsy value recursively — \"delete\": 0 and an absent "
           "delete key are byte-identical on disk, so permissions cannot be audited from JSON",
     "grep -n 'def before_export' -A14 apps/frappe/frappe/core/doctype/doctype/doctype.py"),
    ("F24", "submit / cancel / amend are illegal on a doctype that is not submittable — "
            "validate_permissions throws, so a file carrying one was not written through "
            "the framework",
     "grep -n 'def check_if_submittable' -A8 apps/frappe/frappe/core/doctype/doctype/"
     "doctype.py"),
    ("F25", "a Column Break renders its label as a heading; one labelled from its own "
            "fieldname is a generator stamping label from fieldname (0 of 229 in frappe). "
            "Section breaks are not checked — 34 of 345 in frappe read the same way and "
            "are legitimate",
     "python3 -c \"import json,glob;print(sum(1 for p in glob.glob('apps/frappe/frappe/"
     "**/doctype/*/*.json',recursive=True) for f in (json.load(open(p)).get('fields') or []) "
     "if f.get('fieldtype')=='Column Break' and f.get('label'))\""),
    ("F5", "make_amendable APPENDS amended_from whenever is_submittable is set, from inside "
           "DocType.validate, so omitting it lands it last rather than leaving it out; amendment "
           "requires the source to be docstatus 2",
     "grep -n 'def make_amendable' -A12 apps/frappe/frappe/core/doctype/doctype/doctype.py"),
]

# --------------------------------------------------------------------------- [R] reference bands
# Every band below was RE-MEASURED by this file's own definitions against erpnext and hrms
# (frappe 17.0.0-dev), not copied from prose. A band copied from someone else's definition
# is not comparable with what this script computes. Where a published figure differs it is
# noted beside the band.
BAND = {
    "child_js": (0.0, 0.048, "erpnext 12/248 = 4.8%, hrms 2/54 = 3.7%"),
    "child_test": (0.0, 0.052, "erpnext 13/248 = 5.2%, hrms 2/54 = 3.7%"),
    "amended_from": (0.94, 1.0, "erpnext 76/81, hrms 53/53 — the 5 without are ledger rows"),
    "depends_on_density": (0.098, 0.127, "erpnext 12.7% of fields, hrms 9.8%"),
    "fetch_from_density": (0.035, 0.112, "erpnext 3.5%, hrms 11.2%"),
    "default_density": (0.109, 0.131, "erpnext 13.1%, hrms 10.9%"),
    "py_ratio": (4.16, 7.51, "erpnext 4.16:1, hrms 7.51:1 — same definition, printed below"),
    "perm_rows_median": (3, 3, "erpnext median 3 (max 11), hrms median 3 (max 8)"),
    "real_controllers": (0.76, 0.78, "erpnext 212/279 = 76%, hrms 82/105 = 78% of non-child "
                                     "doctypes have a controller with at least one method"),
    "real_form_js": (0.83, 0.87, "erpnext 232/279 = 83%, hrms 91/105 = 87% of non-child "
                                 "doctypes have a form script that is not a bare stub"),
}

# Framework record types — rung 1 of the ladder. Every one is a document you create rather
# than code you write. Counts are files on disk in the two references.
RUNG1 = {
    "workflow":             (0, 0, "0 in both — the engine exists and neither reference uses it"),
    "document_naming_rule": (0, 0, "0 in both — same"),
    "notification":         (2, 4, "thin prior art in both"),
    "print_format":         (44, 5, ""),
    "dashboard_chart":      (43, 33, ""),
    "number_card":          (41, 32, ""),
    "workspace":            (14, 9, ""),
    "web_form":             (3, 1, ""),
    "_list.js":             (77, 30, "the framework never generates it; both hand-write it"),
    "_dashboard.py":        (68, 27, "the connections panel — a document with none hides its "
                                     "own consequences"),
}

# Client lifecycle events, split by what they can do. This is the split that separates a
# client layer that can DISPLAY from one that can INTERVENE.
EV_DISPLAY = {"refresh", "setup", "onload", "onload_post_render"}
EV_INTERVENE = {"validate", "before_save", "after_save", "before_submit", "on_submit",
                "on_cancel", "before_cancel"}

# gates: only [F] contracts, and only where BOTH reference apps sit inside the bound.
GATE_CHILD_JS = 0.10      # 2x the highest reference value (erpnext 4.8%)
GATE_CHILD_TEST = 0.10    # 2x the highest reference value (erpnext 5.2%)
GATE_AMENDED_FROM = 0.90  # erpnext 0.94 is the floor of the two references
# __init__.py gates at an absolute zero: counted by DocType JSON, erpnext is 0/527 and
# hrms 0/159. (A published figure of "erpnext 2" counts two leftover directories under
# stock/doctype/ — sales_bom and sales_bom_item — which hold no DocType JSON at all.)

LEDGER_HINTS = ("ledger_entry", "gl_entry", "closing_balance", "_ledger", "sle")
REFERENCE_APPS = ("erpnext", "hrms", "frappe")


# --------------------------------------------------------------------------- fs helpers
def jload(path):
    try:
        with open(path) as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def nlines(path):
    try:
        with open(path, errors="replace") as fh:
            return len(fh.read().splitlines())
    except OSError:
        return 0


def is_bench(p):
    return os.path.isdir(os.path.join(p, "apps")) and os.path.isdir(os.path.join(p, "sites"))


def find_bench_upward(start):
    p = os.path.abspath(start)
    while True:
        if is_bench(p):
            return p
        parent = os.path.dirname(p)
        if parent == p:
            return None
        p = parent


def scan_for_benches(depth=4):
    roots = [os.path.expanduser("~"), os.path.expanduser("~/Desktop"),
             os.path.expanduser("~/Documents"), "/opt", "/workspace", "/home"]
    found = []
    seen = set()
    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip("/").count(os.sep)
        for dirpath, dirnames, _ in os.walk(root):
            if dirpath.count(os.sep) - base_depth >= depth:
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(".") and d not in
                           ("node_modules", "__pycache__", "env", "Library", "site-packages")]
            if is_bench(dirpath) and os.path.isdir(os.path.join(dirpath, "apps", "frappe")):
                rp = os.path.realpath(dirpath)
                if rp not in seen:
                    seen.add(rp)
                    found.append(dirpath)
                dirnames[:] = []
    return sorted(found)


def frappe_version(bench):
    init = os.path.join(bench, "apps", "frappe", "frappe", "__init__.py")
    try:
        with open(init, errors="replace") as fh:
            m = re.search(r'^__version__\s*=\s*["\']([^"\']+)', fh.read(), re.M)
            return m.group(1) if m else None
    except OSError:
        return None


def bench_apps(bench):
    out = []
    for p in sorted(glob(os.path.join(bench, "apps", "*"))):
        name = os.path.basename(p)
        if os.path.isfile(os.path.join(p, name, "hooks.py")):
            out.append(name)
    return out


def bench_sites(bench):
    sites = []
    common = jload(os.path.join(bench, "sites", "common_site_config.json")) or {}
    for p in sorted(glob(os.path.join(bench, "sites", "*"))):
        cfg_path = os.path.join(p, "site_config.json")
        if not os.path.isfile(cfg_path):
            continue
        cfg = jload(cfg_path) or {}
        dev = cfg.get("developer_mode", common.get("developer_mode", 0))
        sites.append({"site": os.path.basename(p), "developer_mode": int(bool(dev))})
    return sites, common


def app_package(bench, app):
    return os.path.join(bench, "apps", app, app)


# --------------------------------------------------------------------------- app measurement
def doctypes(app_path):
    for p in glob(os.path.join(app_path, "**", "doctype", "*", "*.json"), recursive=True):
        if "__pycache__" in p:
            continue
        d = jload(p)
        if d and d.get("doctype") == "DocType":
            yield p, d


def scan_form_contracts(dts):
    """F24 / F25 — two things a .json can say that the framework cannot produce.

    Auto-labelled Column Breaks: 0 of 229 in frappe carry a label equal to their own
    fieldname, so the pattern is a generator stamping label from fieldname. Section
    breaks are deliberately NOT checked — 34 of 345 in frappe legitimately read the
    same way ("details" -> "Details"), and a rule against that flags the framework.

    submit / cancel / amend on a non-submittable doctype: validate_permissions throws
    on save, so a file carrying one was not written through the framework.
    """
    junk_breaks, illegal_perms = [], []
    sections = Counter()
    for path, d in dts:
        name = d.get("name") or os.path.basename(path)[:-5]
        if not d.get("istable"):
            cols = 1
            for f in d.get("fields") or []:
                if f.get("fieldtype") == "Section Break":
                    sections[cols] += 1
                    cols = 1
                elif f.get("fieldtype") == "Column Break":
                    cols += 1
            sections[cols] += 1
        for f in d.get("fields") or []:
            if f.get("fieldtype") != "Column Break":
                continue
            label = (f.get("label") or "").strip()
            fieldname = f.get("fieldname") or ""
            if label and label == fieldname.replace("_", " ").title():
                junk_breaks.append(f"{name}.{fieldname}={label!r}")
        if d.get("is_submittable"):
            continue
        for perm in d.get("permissions") or []:
            for flag in ("submit", "cancel", "amend"):
                if perm.get(flag):
                    illegal_perms.append(f"{name}: {perm.get('role')} has {flag}")
    return {"junk_breaks": junk_breaks, "illegal_perms": illegal_perms,
            "sections": dict(sections)}


def measure_app(app_path):
    dts = list(doctypes(app_path))
    r = {"app_path": app_path, "doctypes": len(dts)}
    if not dts:
        r["empty"] = True
        return r

    kinds = Counter()
    bad_js, bad_test, no_init, children = [], [], [], 0
    class_mismatch, class_checked = [], 0
    subs, missing_amended = [], []
    fields_total = 0
    dens = Counter()
    autoname = Counter()
    perm_rows, roles = [], Counter()

    for p, d in dts:
        folder, base = os.path.dirname(p), os.path.basename(p)[:-5]
        name = d.get("name") or base

        if d.get("istable"):
            kinds["child table"] += 1
        elif d.get("issingle"):
            kinds["single / settings"] += 1
        elif d.get("is_submittable"):
            kinds["transaction"] += 1
        elif d.get("is_tree"):
            kinds["tree master"] += 1
        else:
            kinds["master"] += 1

        # --- [F1] generator contract
        if not os.path.exists(os.path.join(folder, "__init__.py")):
            no_init.append(name)
        if d.get("istable"):
            children += 1
            if os.path.exists(os.path.join(folder, base + ".js")):
                bad_js.append(name)
            if os.path.exists(os.path.join(folder, "test_" + base + ".py")):
                bad_test.append(name)

        # --- [F2] class name
        py = os.path.join(folder, base + ".py")
        if os.path.exists(py):
            expected = name.replace(" ", "").replace("-", "")
            class_checked += 1
            try:
                with open(py, errors="replace") as fh:
                    src = fh.read()
            except OSError:
                src = ""
            if not re.search(rf"^class {re.escape(expected)}\b", src, re.M):
                found = re.findall(r"^class (\w+)", src, re.M)
                class_mismatch.append(f"{name}: expected 'class {expected}', found {found or 'none'}")

        # --- [F5] amended_from
        fieldnames = {f.get("fieldname") for f in d.get("fields", [])}
        if d.get("is_submittable"):
            subs.append(name)
            if "amended_from" not in fieldnames:
                looks_ledger = any(h in base for h in LEDGER_HINTS)
                missing_amended.append(name + (" (ledger row? may be correct)" if looks_ledger else ""))

        # --- [R] declarative density
        for f in d.get("fields", []):
            fields_total += 1
            for k in ("depends_on", "mandatory_depends_on", "read_only_depends_on",
                      "fetch_from", "default", "link_filters", "non_negative", "set_only_once"):
                if f.get(k):
                    dens[k] += 1

        # --- conventions already chosen
        an = d.get("autoname") or ""
        if d.get("istable"):
            pass
        elif an.startswith("field:"):
            autoname["field: (natural key)"] += 1
        elif an.startswith("naming_series"):
            autoname["naming_series field"] += 1
        elif an.startswith("format:"):
            autoname["format: string"] += 1
        elif an in ("hash", ""):
            autoname["none -> hash"] += 1
        else:
            autoname["fixed autoname string"] += 1

        if not d.get("istable"):
            perms = d.get("permissions", [])
            perm_rows.append(len(perms))
            for perm in perms:
                if perm.get("role"):
                    roles[perm["role"]] += 1

    # --- base classes actually used (exception classes excluded — they are not controllers)
    bases = Counter()
    for p, d in dts:
        py = os.path.join(os.path.dirname(p), os.path.basename(p)[:-5] + ".py")
        try:
            with open(py, errors="replace") as fh:
                for m in re.finditer(r"^class (\w+)\(([^)]*)\)", fh.read(), re.M):
                    if m.group(1).endswith(("Error", "Exception")):
                        continue
                    bases[m.group(2).strip().split(".")[-1] or "object"] += 1
        except OSError:
            pass

    # --- desk artifacts, app-wide (the framework never generates _list.js; both references
    #     hand-write it: erpnext 77, hrms 30)
    list_js = len(glob(os.path.join(app_path, "**", "*_list.js"), recursive=True))
    tree_js = len(glob(os.path.join(app_path, "**", "*_tree.js"), recursive=True))
    dash_py = len(glob(os.path.join(app_path, "**", "*_dashboard.py"), recursive=True))

    # --- per-doctype vs shared python.  ONE definition, printed with the number, because a
    #     different definition moves it a long way (hrms: 7.51 here, 5.40 if the package root
    #     is counted as shared).
    shared_pats = ("controllers/*.py", "utils/*.py", "utils.py", "*/utils.py",
                   "overrides/*.py", "mixins/*.py", "*/services/*.py")
    per = sum(nlines(f) for f in glob(os.path.join(app_path, "**", "doctype", "*", "*.py"),
                                      recursive=True)
              if not os.path.basename(f).startswith(("test_", "__init__")))
    shared, shared_def = 0, "controllers/ utils/ overrides/ mixins/ */services/"
    for pat in shared_pats:
        for f in glob(os.path.join(app_path, pat)):
            if os.path.isfile(f) and os.path.basename(f) not in ("__init__.py", "hooks.py"):
                shared += nlines(f)
    if shared == 0:                       # a small app may keep its shared module at the root
        shared_def += " + package root *.py (fallback: nothing matched above)"
        for f in glob(os.path.join(app_path, "*.py")):
            if os.path.basename(f) not in ("__init__.py", "hooks.py"):
                shared += nlines(f)

    # --- reports
    rep = Counter()
    for rp in glob(os.path.join(app_path, "**", "report", "*", "*.json"), recursive=True):
        rd = jload(rp)
        if rd and rd.get("doctype") == "Report":
            rep[rd.get("report_type") or "?"] += 1

    # --- client layer vocabulary, and whether it can intervene or only display
    events = Counter()
    throws = files_display = files_intervene = 0
    for js in glob(os.path.join(app_path, "**", "doctype", "*", "*.js"), recursive=True):
        try:
            with open(js, errors="replace") as fh:
                src = fh.read()
        except OSError:
            continue
        throws += src.count("frappe.throw")
        seen_ev = {m.group(1) for m in
                   re.finditer(r"^\s*(" + "|".join(sorted(EV_DISPLAY | EV_INTERVENE)) + r")\s*[:(]",
                               src, re.M)}
        for e in seen_ev:
            events[e] += 1
        if seen_ev & EV_DISPLAY:
            files_display += 1
        if seen_ev & EV_INTERVENE:
            files_intervene += 1

    # --- is the code real, or is it what the generator emitted?
    real_py = stub_py = real_js = stub_js = no_js = 0
    for p, d in dts:
        if d.get("istable"):
            continue
        folder, base = os.path.dirname(p), os.path.basename(p)[:-5]
        py, js = os.path.join(folder, base + ".py"), os.path.join(folder, base + ".js")
        if os.path.exists(py):
            body = re.sub(r'"""[\s\S]*?"""', "", open(py, errors="replace").read())
            if re.search(r"^[\t ]+def ", body, re.M):
                real_py += 1
            else:
                stub_py += 1
        if os.path.exists(js):
            body = re.sub(r"//.*", "", open(js, errors="replace").read())
            body = re.sub(r"frappe\.ui\.form\.on\(\s*[\"'][^\"']+[\"']\s*,\s*\{\s*\}\s*\)\s*;?",
                          "", body)
            (real_js := real_js + 1) if body.strip() else (stub_js := stub_js + 1)
        else:
            no_js += 1

    # --- rung 1: framework records this app actually ships
    rung1 = {}
    for kind in RUNG1:
        if kind.startswith("_"):
            rung1[kind] = len(glob(os.path.join(app_path, "**", "*" + kind), recursive=True))
        else:
            n = 0
            for dirpath, dirnames, _ in os.walk(app_path):
                if os.path.basename(dirpath) == kind and "doctype" not in dirpath.split(os.sep):
                    n += len(glob(os.path.join(dirpath, "**", "*.json"), recursive=True))
            rung1[kind] = n

    # --- hooks.py surface, read as text (importing it would need frappe)
    hooks = []
    hp = os.path.join(app_path, "hooks.py")
    if os.path.isfile(hp):
        src = open(hp, errors="replace").read()
        hooks = sorted({m.group(1) for m in re.finditer(r"^(\w+)\s*=", src, re.M)}
                       - {"app_name", "app_title", "app_publisher", "app_description",
                          "app_email", "app_license", "app_icon", "app_color", "app_version",
                          "source_link", "app_logo_url", "add_to_apps_screen"})

    nsub = max(len(subs), 1)
    nchild = max(children, 1)
    r.update({
        "kinds": dict(kinds),
        "generator": {
            "child_tables": children,
            "child_tables_with_js": bad_js,
            "child_tables_with_test": bad_test,
            "child_js_rate": round(len(bad_js) / nchild, 4),
            "child_test_rate": round(len(bad_test) / nchild, 4),
            "dirs_without_init": no_init,
        },
        "class_names": {"checked": class_checked, "mismatches": class_mismatch},
        "amended_from": {"submittable": len(subs), "missing": missing_amended,
                         "rate": round((len(subs) - len(missing_amended)) / nsub, 3)},
        "declarative": {"fields": fields_total,
                        **{k: round(v / max(fields_total, 1), 4) for k, v in dens.items()},
                        "_counts": dict(dens)},
        "autoname": dict(autoname),
        "permissions": {"median_rows": statistics.median(perm_rows) if perm_rows else 0,
                        "max_rows": max(perm_rows) if perm_rows else 0,
                        "roles": dict(roles.most_common(12))},
        "base_classes": dict(bases.most_common(10)),
        "python": {"per_doctype": per, "shared": shared, "shared_definition": shared_def,
                   "ratio": round(per / shared, 2) if shared else None},
        "reports": dict(rep),
        "desk": {"_list.js": list_js, "_tree.js": tree_js, "_dashboard.py": dash_py},
        "client": {"events_used": sorted(events), "frappe_throw": throws,
                   "files_display_only": files_display - files_intervene,
                   "files_intervening": files_intervene,
                   "intervening_events": sorted(set(events) & EV_INTERVENE)},
        "reality": {"real_controllers": real_py, "stub_controllers": stub_py,
                    "real_controller_rate": round(real_py / max(real_py + stub_py, 1), 3),
                    "real_form_js": real_js, "stub_form_js": stub_js, "no_form_js": no_js,
                    "real_js_rate": round(real_js / max(real_js + stub_js + no_js, 1), 3)},
        "rung1": rung1,
        "hooks": hooks,
        "form_contracts": scan_form_contracts(dts),
    })
    return r


# --------------------------------------------------------------------------- gate
def gate(m):
    """Only [F] contracts gate. Returns list of (id, message)."""
    if m.get("empty"):
        return []
    breaches = []
    g = m["generator"]
    if g["child_js_rate"] > GATE_CHILD_JS:
        breaches.append(("F1", f"{len(g['child_tables_with_js'])} of {g['child_tables']} child "
                               f"tables carry a .js ({g['child_js_rate']:.1%} > "
                               f"{GATE_CHILD_JS:.0%}). The framework never writes one for a "
                               f"child table, so these files were not created through it: "
                               f"{', '.join(g['child_tables_with_js'][:6])}"))
    if g["child_test_rate"] > GATE_CHILD_TEST:
        breaches.append(("F1", f"{len(g['child_tables_with_test'])} of {g['child_tables']} child "
                               f"tables carry a test_ file ({g['child_test_rate']:.1%} > "
                               f"{GATE_CHILD_TEST:.0%}). Same guard, same conclusion: "
                               f"{', '.join(g['child_tables_with_test'][:6])}"))
    if g["dirs_without_init"]:
        breaches.append(("F1", f"{len(g['dirs_without_init'])} doctype directories have no "
                               f"__init__.py — they are not importable, and an unimportable "
                               f"controller is an ImportError, which is F2: "
                               f"{', '.join(g['dirs_without_init'][:6])}"))
    if m["class_names"]["mismatches"]:
        breaches.append(("F2", "controller class name mismatch — bench migrate will report these "
                               "as orphans and REMOVE the DocType row:\n        "
                               + "\n        ".join(m["class_names"]["mismatches"][:8])))
    fc = m.get("form_contracts") or {}
    if fc.get("illegal_perms"):
        breaches.append(("F24", f"{len(fc['illegal_perms'])} permission rows grant submit, cancel "
                                f"or amend on a doctype that is not submittable. The framework "
                                f"throws on save, so these files were not written through it: "
                                + ", ".join(fc["illegal_perms"][:6])))
    if fc.get("junk_breaks"):
        breaches.append(("F25", f"{len(fc['junk_breaks'])} Column Breaks are labelled from their "
                                f"own fieldname, so the forms carry headings a generator wrote "
                                f"rather than a human (0 of 229 in frappe): "
                                + ", ".join(fc["junk_breaks"][:6])))
    if m["amended_from"]["rate"] < GATE_AMENDED_FROM and m["amended_from"]["submittable"]:
        miss, subs = m["amended_from"]["missing"], m["amended_from"]["submittable"]
        msg = (f"{len(miss)} of {subs} submittable doctypes have no amended_from: "
               f"{', '.join(miss[:6])}")
        # A correct exception still sinks the rate, and in a small app it sinks it for good.
        # Say so here rather than leave someone to rediscover it: a gate that always fails
        # teaches the next session to skip the output, and a real breach walks through behind it.
        if any("ledger row?" in n for n in miss):
            msg += (f"\n        Some of those look like ledger rows the system appends, which F4 says "
                    f"correctly do NOT carry\n        the field. This gate measures a RATE "
                    f"({GATE_AMENDED_FROM:.0%}) and does not exempt them, so with only {subs} "
                    f"submittable(s)\n        one correct exception holds it red permanently. In a "
                    f"small app, keep the field: one hidden column\n        nothing populates costs "
                    f"less than a gate nobody reads. See CONTRACTS.md F4.")
        breaches.append(("F5", msg))
    return breaches


# --------------------------------------------------------------------------- report
def band_note(key, value):
    lo, hi, src = BAND[key]
    if value is None:
        return f"  (reference {src})"
    if value < lo:
        where = "BELOW"
    elif value > hi:
        where = "above"
    else:
        where = "inside"
    return f"  [{where} band] reference {src}"


def report(bench, meta, target_app, m, wide_benches):
    W = 78
    p = print
    p("=" * W)
    p("WHERE YOU ARE")
    p("=" * W)
    if bench:
        p(f"  bench            {bench}")
        p(f"  frappe           {meta['version'] or 'unknown'}")
        p(f"  apps             {', '.join(meta['apps']) or '(none)'}")
        for s in meta["sites"]:
            flag = "developer_mode ON " if s["developer_mode"] else "developer_mode OFF  <-- "
            tail = "" if s["developer_mode"] else "doctype changes will NOT be written to files"
            p(f"  site             {s['site']:<24} {flag}{tail}")
        if not meta["sites"]:
            p("  site             (none found under sites/)")
    else:
        p("  no bench found from this directory. Pass a path, or run with --wide.")

    p("")
    p("=" * W)
    p("REACHABLE ON DISK  — prior art is not limited to what is installed")
    p("=" * W)
    rich, plain = [], []
    for b in wide_benches:
        have = [a for a in bench_apps(b) if a in REFERENCE_APPS]
        (rich if [h for h in have if h != "frappe"] else plain).append(
            (b, have, frappe_version(b)))
    if rich:
        p("  benches holding a reference implementation:")
        for b, have, v in rich:
            p(f"    {v or '?':<12} {', '.join(have):<24} {b}")
    if plain:
        p(f"  + {len(plain)} more bench(es) with frappe only "
          f"({', '.join(sorted({v or '?' for _, _, v in plain}))})")
    if not rich and not plain:
        p("  only this bench was scanned. Run with --wide to search the disk.")
    if rich and bench and not any(b == bench for b, _, _ in rich):
        p("")
        p("  NOTE: the bench you are working in holds no reference implementation. The richest")
        p("        prior art in the ecosystem is in the benches above, and a search correctly")
        p("        scoped to this bench will not see it.")
    roots = [f"{b}/apps" for b, _, _ in rich] or ([f"{bench}/apps"] if bench else [])
    if roots:
        p("")
        p("  Before writing ANY helper, run this. It covers benches you are not working in:")
        p(f"    grep -rn \"def <name>\" {' '.join(roots)} --include='*.py' | head")

    p("")
    p("=" * W)
    p(f"THIS APP   {target_app or '(none selected)'}")
    p("=" * W)
    if not m or m.get("empty"):
        p("  no doctypes found — nothing to measure yet.")
    else:
        g = m["generator"]
        p(f"  doctypes         {m['doctypes']}   " +
          "  ".join(f"{k}={v}" for k, v in sorted(m["kinds"].items())))
        p("")
        p("  --- framework contracts [F] — these gate ---")
        p(f"  F1 child .js     {len(g['child_tables_with_js'])} of {g['child_tables']} child "
          f"tables carry one   ({g['child_js_rate']:.1%})")
        p(band_note("child_js", g["child_js_rate"]))
        p(f"  F1 child test_   {len(g['child_tables_with_test'])} of {g['child_tables']} child "
          f"tables carry one   ({g['child_test_rate']:.1%})")
        p(band_note("child_test", g["child_test_rate"]))
        p(f"  F1 __init__.py   missing in {len(g['dirs_without_init'])} of {m['doctypes']} "
          f"doctype directories   [reference erpnext 0/527, hrms 0/159 — gates at 0]")
        for x in g["dirs_without_init"][:6]:
            p(f"       ! {x}")
        p(f"  F2 class names   {m['class_names']['checked']} checked, "
          f"{len(m['class_names']['mismatches'])} mismatched")
        if m["class_names"]["mismatches"]:
            for x in m["class_names"]["mismatches"][:6]:
                p(f"       ! {x}")
            p("       a mismatch is an ImportError; bench migrate reads that as a deleted")
            p("       doctype and removes the DocType row. Data table survives, registration does not.")
        af = m["amended_from"]
        p(f"  F5 amended_from  {af['submittable'] - len(af['missing'])}/{af['submittable']} "
          f"submittable doctypes carry it")
        if af["missing"]:
            for x in af["missing"][:6]:
                p(f"       ! {x}")
        p(band_note("amended_from", af["rate"] if af["submittable"] else None))
        p("")
        p("  F3/F4 permissions cannot be measured from files. before_export strips falsy values,")
        p("        so \"delete\": 0 and an absent delete key are byte-identical on disk.")
        p("        The only real check is running as the least-privileged user — see PASTE below.")

        p("")
        p("  --- is the code real, or is it what the generator emitted? [R] ---")
        rl = m["reality"]
        p(f"  controllers      {rl['real_controllers']} real, {rl['stub_controllers']} stub "
          f"({rl['real_controller_rate']:.0%} real)")
        p(band_note("real_controllers", rl["real_controller_rate"]))
        p(f"  form scripts     {rl['real_form_js']} real, {rl['stub_form_js']} stub, "
          f"{rl['no_form_js']} absent   ({rl['real_js_rate']:.0%} real)")
        p(band_note("real_form_js", rl["real_js_rate"]))
        p("       a stub is what the framework wrote and nobody touched. Every non-child")
        p("       doctype should have a controller and a form script doing real work, OR one")
        p("       line saying why not — usually: the declarative layer already covers it.")

        cl = m["client"]
        p("")
        p("  --- can the client layer INTERVENE, or only DISPLAY? [R] ---")
        p(f"  events used      {', '.join(cl['events_used']) or '(none)'}")
        p(f"  intervening      {', '.join(cl['intervening_events']) or 'NONE'}"
          f"   ({cl['files_intervening']} file(s))")
        p(f"  frappe.throw     {cl['frappe_throw']} across the client layer")
        if not cl["intervening_events"] or cl["frappe_throw"] == 0:
            p("       ! every event in use fires when a form APPEARS. None of validate,")
            p("         before_save, before_submit, on_submit intervenes, and nothing throws.")
            p("         The user is told about a mistake at save, or not at all.")
            p("         [reference: erpnext 31 intervening files / 116 client throws;")
            p("          hrms 7 / 19. An app surveyed with 165 client files had 0 and 0.]")

        p("")
        p("  --- rung 1: framework records this app ships, vs writing code [R] ---")
        for kind, n in m["rung1"].items():
            e, h, note = RUNG1[kind]
            flag = "  <-- none, and both references use it" if (n == 0 and (e or h)) else ""
            p(f"  {kind:<22} {n:>4}   [erpnext {e}, hrms {h}]{flag}")
            if note and n == 0:
                p(f"       {note}")
        if m["hooks"]:
            p("")
            p(f"  hooks declared   {', '.join(m['hooks'])}")

        p("")
        p("  --- convention this app has ALREADY chosen [A] — match it, do not re-establish ---")
        p(f"  naming           " + ", ".join(f"{k} x{v}" for k, v in
                                             sorted(m["autoname"].items(), key=lambda kv: -kv[1])))
        p(f"  base classes     " + ", ".join(f"{k} x{v}" for k, v in m["base_classes"].items()))
        p(f"  roles            " + (", ".join(f"{k} x{v}" for k, v in m["permissions"]["roles"].items())
                                    or "(none declared)"))
        p(f"  perm rows        median {m['permissions']['median_rows']}, "
          f"max {m['permissions']['max_rows']}"
          f"   [reference {BAND['perm_rows_median'][2]}]")
        p(f"  reports          " + (", ".join(f"{k} x{v}" for k, v in m["reports"].items())
                                    or "(none)")
          + "   [reference Script Report 90% erpnext / 96% hrms]")
        p(f"  client events    " + (", ".join(m["client"]["events_used"]) or "(none)")
          + f"   frappe.throw x{m['client']['frappe_throw']}")
        p(f"  desk artifacts   _list.js {m['desk']['_list.js']}, "
          f"_dashboard.py {m['desk']['_dashboard.py']}, _tree.js {m['desk']['_tree.js']}"
          f"   [reference _list.js: erpnext 77, hrms 30 — the framework never generates it]")

        p("")
        p("  --- proportion [R] — reference bands, never gates ---")
        d = m["declarative"]
        for key, field in (("depends_on_density", "depends_on"),
                           ("fetch_from_density", "fetch_from"),
                           ("default_density", "default")):
            v = d.get(field, 0.0)
            p(f"  {field:<16} {v:.1%} of {d['fields']} fields  (n={d['_counts'].get(field, 0)})")
            p(band_note(key, v))
        zero = [k for k in ("mandatory_depends_on", "read_only_depends_on", "link_filters",
                            "non_negative", "set_only_once") if not d["_counts"].get(k)]
        if zero:
            p(f"  at literal zero   {', '.join(zero)}")
            p("       every one of these is a DocField property. If the app expresses any of them")
            p("       in JavaScript instead, that is the imperative-by-default failure.")
        sec = (m.get("form_contracts") or {}).get("sections") or {}
        if sec:
            total = sum(sec.values())
            shape = "  ".join(f"{n}col {sec[n]}" for n in sorted(sec))
            p(f"  form columns     {total} sections — {shape}")
            two = sec.get(2, 0) / total
            if two > 0.80 and total >= 8:
                p(f"       {two:.0%} of sections are exactly two columns. Frappe's own are 66% one,")
                p("       31% two, 3% three — a uniform answer across every form means nobody chose")
                p("       the shape; a section holding one field does not need a column break. F25.")
            else:
                p("       [reference frappe 66% one column, 31% two, 3% three, a few at four to six]")
        py = m["python"]
        p(f"  python ratio     per-doctype {py['per_doctype']} : shared {py['shared']} "
          f"= {py['ratio']}")
        p(f"       shared = {py['shared_definition']}")
        p(band_note("py_ratio", py["ratio"]))
        if py["ratio"] is not None and py["ratio"] < 2.0:
            p("       a ratio near 1 does not mean good factoring. It means the documents have")
            p("       no behaviour. Share the repetition, then expect the per-document file to grow.")

    p("")
    p("=" * W)
    p("PASTE BLOCKS  — filled in from what was detected above")
    p("=" * W)
    site = None
    for s in meta.get("sites", []):
        site = s["site"]
        if s["developer_mode"]:
            break
    if bench and site:
        p("  run a script against the site  (piping into `bench console` breaks on multi-line):")
        p(f"    cd {bench}/sites && ../env/bin/python - <<'PY'")
        p("    import frappe")
        p(f"    frappe.init(site=\"{site}\", sites_path=\".\"); frappe.connect()")
        p("    frappe.set_user(\"Administrator\")")
        p("    # ... work ...")
        p("    frappe.db.commit()          # without this the work rolls back AND the script")
        p("    frappe.destroy()            # still prints whatever success messages it contains")
        p("    PY")
        p("")
        p("  run as the least-privileged user who must still be able to work:")
        p(f"    cd {bench}/sites && ../env/bin/python - <<'PY'")
        p("    import frappe")
        p(f"    frappe.init(site=\"{site}\", sites_path=\".\"); frappe.connect()")
        p("    frappe.set_user(\"<clerk@example.com>\")")
        p("    for dt in [\"<DocType>\"]:")
        p("        for p_ in (\"read\",\"write\",\"create\",\"submit\",\"delete\",\"cancel\",\"amend\"):")
        p("            print(dt, p_, frappe.has_permission(dt, ptype=p_))")
        p("    frappe.destroy()")
        p("    PY")
        p("    reading permission JSON does not find these. The defect is what the JSON does not say.")
    else:
        p("  (no site detected — pass a bench path to get these filled in)")

    p("")
    p("=" * W)
    p("NOT DETERMINED BY THIS PROBE")
    p("=" * W)
    p("  - whether the app WORKS. Nothing here executes a document.")
    p("  - permission grants. Only a live run as a real user shows them (F4).")
    p("  - row-level visibility: User Permissions, if_owner, permission_query_conditions.")
    p("  - whether anything is on disk that is only in the database — workspaces, print")
    p("    formats, custom fields and property setters need an explicit export_to_files.")
    p("  - anything about maintainability. It was never measured, by anyone, in any of the")
    p("    material this kit was built from.")


# --------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", default=".",
                    help="a bench, an app dir, or an app package. Default: cwd")
    ap.add_argument("--app", help="app name, when the path is a bench with several")
    ap.add_argument("--gate", action="store_true", help="framework contracts only, exit 1 on breach")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--wide", action="store_true", help="scan the disk for other benches")
    args = ap.parse_args()

    path = os.path.abspath(args.path)
    bench = find_bench_upward(path)
    target_app, app_path = None, None

    # the path may be an app package (has hooks.py) or an app dir
    if os.path.isfile(os.path.join(path, "hooks.py")):
        app_path, target_app = path, os.path.basename(path)
    elif os.path.isdir(path) and os.path.isfile(
            os.path.join(path, os.path.basename(path), "hooks.py")):
        target_app = os.path.basename(path)
        app_path = os.path.join(path, target_app)
    elif bench:
        apps = [a for a in bench_apps(bench) if a != "frappe"]
        target_app = args.app or (apps[0] if len(apps) == 1 else None)
        if target_app:
            app_path = app_package(bench, target_app)
        elif apps:
            print(f"several apps in this bench: {', '.join(apps)}\n"
                  f"pass --app <name> (or a path) to measure one.", file=sys.stderr)

    meta = {"version": None, "apps": [], "sites": []}
    if bench:
        meta["version"] = frappe_version(bench)
        meta["apps"] = bench_apps(bench)
        meta["sites"], _ = bench_sites(bench)

    m = measure_app(app_path) if app_path and os.path.isdir(app_path) else None

    if args.gate:
        if not m:
            print("gate: no app to measure", file=sys.stderr)
            sys.exit(2)
        breaches = gate(m)
        for cid, msg in breaches:
            contract = next(c for c in CONTRACTS if c[0] == cid)
            print(f"[BREACH {cid}] {msg}")
            print(f"    frappe: {contract[1]}")
            print(f"    locate: {contract[2]}\n")
        if breaches:
            print(f"{len(breaches)} framework contract breach(es) in {app_path}")
            sys.exit(1)
        print(f"no framework contract breach in {app_path}")
        print("This gate covers the creation path and amendability. It says NOTHING about "
              "whether the app works.")
        sys.exit(0)

    wide = scan_for_benches() if args.wide else ([bench] if bench else [])

    if args.json:
        print(json.dumps({"bench": bench, "meta": meta, "app": target_app, "measurements": m,
                          "reachable_benches": wide}, indent=2, default=str))
        return

    report(bench, meta, target_app, m, wide)


if __name__ == "__main__":
    main()
