# Contracts

**Not a manual.** Frappe is documented; this is the part that is not, and the part that bites.
Every row here is verified in `apps/frappe` source. Nothing here is style.

Each row is `trigger → what frappe does → what breaks → the thing you paste`. Find your row by
the words of the action you are about to take. If no trigger matches, no row applies — close
the file.

Every row carries a `locate:` command. **Line numbers drift** — `make_controller_template` is
`doctype.py:862` in 16.0.0-dev and `:901` in 17.0.0-dev — so re-locate rather than cite. That
one command is what makes a `file:line` citation true in *your* bench instead of in someone
else's.

Tags: **[F]** verified in frappe source · **[R]** measured in erpnext + hrms · **[A]** judgement.
Only **[F]** rows are contracts. **[R]** rows are bands, never targets. **[A]** rows are mine.

---

## 0 · I am about to create a file — any file

### L1 — Take the lowest rung that fits, and say which one, in one line. [F][R]

**Trigger:** you are about to create or edit *any* file in an app. This fires before every
other row here.

Frappe is metadata-first. The framework already ships a record type for most of what an app
needs, and reaching for code first is the root failure — not a style preference. **State the
rung and the reason before touching a file:**

```
Rung <N> — <mechanism> — because rung <N-1> cannot <the specific thing>.
```

**Rung 1 · a framework record or a DocType property.** Data, not code. All eighteen of these
were confirmed present in the frappe on this machine:

```
on the DocField          depends_on · mandatory_depends_on · read_only_depends_on
                         fetch_from · fetch_if_empty · default · link_filters
                         precision · non_negative · unique · set_only_once
                         allow_on_submit · no_copy · in_list_view · in_standard_filter

shipped record types     Workflow · Document Naming Rule · Notification · Print Format
                         Dashboard Chart · Number Card · Workspace · Dashboard
                         Web Form · Assignment Rule · Auto Repeat · Webhook
                         List View Settings · DocType Link · DocType Action
                         Custom Field · Property Setter · Version
```

**Rung 2 · a low-code record.** `Client Script` / `Server Script` documents. Site-specific
tweaks live here. Promote to rung 3 when it becomes product.

**Rung 3 · app code.** Controller, form `.js`, Script Report, Page, hook, whitelisted method.
The last rung, not the first instinct.

**[R] What the references actually ship at rung 1** — this is the number that shows the rung
is real and not an aspiration:

| | erpnext | hrms | |
|---|---:|---:|---|
| `dashboard_chart` | 43 | 33 | |
| `number_card` | 41 | 32 | |
| `print_format` | 44 | 5 | |
| `workspace` | 14 | 9 | |
| `web_form` | 3 | 1 | |
| `notification` | 2 | 4 | thin in both |
| **`workflow`** | **0** | **0** | the engine exists and neither uses it — F9 |
| **`document_naming_rule`** | **0** | **0** | same — F10 |
| `_list.js` | 77 | 30 | never generated, always hand-added |
| `_dashboard.py` | 68 | 27 | the connections panel |

**Both directions are failures.** Two hundred lines of custom code where a record does it, and
a flimsy record where the product needs real code. The second is measurable too: **[R]** 76% of
erpnext's non-child doctypes and 78% of hrms's have a controller with at least one method; 83%
and 87% have a form script that is not a bare generated stub. An app far below that has
documents with no behaviour, not a well-factored shared layer.

`probe.py` prints both — which rung-1 records the app ships, and how much of its code is real
versus what the generator emitted.

```sh
locate: ls -d apps/frappe/frappe/*/doctype/{workflow,document_naming_rule,notification,print_format,dashboard_chart,number_card,workspace,web_form,assignment_rule,auto_repeat,webhook,list_view_settings,doctype_link,doctype_action,custom_field,property_setter,server_script,client_script}
```

> **This rung statement is the artifact.** Not "consider whether a record would do" — a
> written line naming the rung and what the rung below cannot do. If you cannot name what the
> rung below fails at, you are on the wrong rung.

---

## 1 · I am about to create a doctype, add a field, or change a schema

### F1 — Never write doctype files. The framework writes them. [F]

**Trigger:** you are about to create `<name>.json`, `<name>.py`, `<name>.js`, or an
`__init__.py` under a `doctype/` directory. Or you are about to edit a doctype `.json` by hand.

```python
# new doctype — the framework emits every file below
frappe.get_doc({"doctype": "DocType", "module": "<Module>", "name": "<Doctype Name>",
                "fields": [...], "permissions": [...]}).insert()

# new field on an existing doctype — edit the DOCUMENT, never the JSON
dt = frappe.get_doc("DocType", "<Doctype Name>")
dt.append("fields", {"fieldname": "...", "fieldtype": "...", "label": "..."})
dt.save()          # prints: Wrote document file for DocType ... at .../<name>.json
```

Requires `developer_mode: 1` in the site config, or nothing is written to disk at all. The
probe tells you whether it is on.

**What the framework writes, exactly:**

| file | when |
|---|---|
| `<name>.json`, `<name>.py`, `__init__.py` | always — including child tables |
| `<name>.js`, `test_<name>.py` | **only if `istable` is false** |
| `<name>_tree.js` | only if `is_tree` |
| `<name>_calendar.js` | only if `is_calendar_and_gantt` |
| `templates/<name>.html`, `_list.html`, `_row.html` | only if `has_web_view` |
| `<name>_list.js` | **never** — the call is commented out in the framework |

**What breaks:** nothing immediately. That is why it survives. A child table carrying a `.js`
or a `test_` file is the cheapest proof in existence that the file was not made through the
framework — and the deviation does not sit still. Measured on one lineage: at handoff 53 stray
files were auto-removable and 1 needed a human; ten weeks later 26 of those stubs had been
filled with real code and become load-bearing. That is the argument for gating at commit time
rather than review time.

**[R]** Reference rate for child tables carrying a `.js`: erpnext 12/248 = 4.8%, hrms 2/54 = 3.7%.
A lineage that shipped its own generator missing one `if not self.istable` sits at 86% and 100%.

```sh
locate: grep -n 'if not self.istable' -A 20 apps/frappe/frappe/core/doctype/doctype/doctype.py
check:  python3 probe.py --gate <app_path>
```

> **`_list.js` is the exception to read carefully.** The framework never generates it, and
> both references hand-write it constantly — erpnext 77, hrms 30. Its absence from the
> generator is not a signal that list views are unusual. It is the one artifact in a doctype
> folder you are always expected to add yourself.

### F2 — The controller class name is the doctype name minus spaces and hyphens. Nothing else. [F]

**Trigger:** you are about to generate a class name, a module path, or any identifier for
another system to resolve — `.capitalize()`, `.title()`, a slug, a concat, a loop over names.

```
"Sales Invoice"   → class SalesInvoice
"UOM"             → class UOM            ← NOT Uom
"E-Commerce Item" → class ECommerceItem
```

**What breaks — this is the destructive one.** An unresolvable class raises `ImportError`.
`remove_orphan_doctypes()`, which runs inside `bench migrate`, catches `ImportError` in the
same handler as a genuinely deleted file and **removes the DocType row**. The data table
survives; the registration does not. Observed live: a `capitalize()` loop produced `class Uom`
for doctype `UOM`; migrate printed `Orphaned DocType(s) found: UOM` in one line of otherwise
successful output and dropped it.

Two details worth knowing: an override class must be a *subclass* of the original or the
framework throws rather than silently substituting; and doctypes listed in
`override_doctype_class` are skipped by the orphan sweep entirely.

**Paste — before the batch, not after:**

```python
name = "<one generated value>"
assert name.replace(" ", "").replace("-", "") == "<the class you are about to write>", name
```

```sh
locate: grep -n 'replace(" ", "")' apps/frappe/frappe/model/base_document.py
        grep -n 'def remove_orphan_doctypes' -A 25 apps/frappe/frappe/model/sync.py
```

### F3 — `is_tree` adds its own fields. Do not hand-add them. [F]

**Trigger:** you are about to add `lft`, `rgt`, `is_group`, `old_parent`, or a `parent_<x>`
Link to a hierarchy doctype.

Setting `is_tree` makes the framework add `parent_field`, `lft`, `rgt`, `is_group`. The parent
field name is derived, not configured: `meta.nsm_parent_field or f"parent_{frappe.scrub(doctype)}"`.
Inherit `frappe.utils.nestedset.NestedSet` and it supplies `on_update → update_nsm` and trash
handling.

**[A]** Use a tree only when the hierarchy is *queried* as a hierarchy — "everything under this
node". A `parent` Link with no rollup query does not need `NestedSet`.

```sh
locate: grep -n 'is_tree' apps/frappe/frappe/core/doctype/doctype/doctype.py
        grep -n 'nsm_parent_field' apps/frappe/frappe/utils/nestedset.py
```

### F4 — `amended_from` is added for you, at the end. Declare it anyway, where it belongs. [F]

**Trigger:** you set `is_submittable: 1` on anything.

The framework adds it. `DocType.make_amendable` appends the docfield whenever `is_submittable` is
set, and it runs inside `DocType.validate`, so it fires on every save and on every import. Omitting
it from your JSON does not leave it out, it leaves it **appended after every other field**, at the
bottom of the last section, in a position nobody chose.

It is hidden, so nothing looks wrong on the form. It shows up when someone reorders fields, or reads
the JSON and finds a field the file never declared.

So declare it, in the position you want it, exactly as the framework would build it:

```json
{"fieldname": "amended_from", "fieldtype": "Link", "options": "<the doctype itself>",
 "label": "Amended From", "hidden": 1, "read_only": 1, "no_copy": 1,
 "print_hide": 1, "ignore_user_permissions": 1}
```

What the framework does with it once present: validate that the source is cancelled
(`docstatus == 2`), and copy its attachments. `delete_doc` additionally exempts this link from the
cancel-time link check.

**Which doctypes should carry it.** **[R]** erpnext 76/81 submittables carry it, hrms 53/53. The five
without are all ledger rows the system appends — `gl_entry`, `stock_ledger_entry`,
`payment_ledger_entry`, `advance_payment_ledger_entry`, `account_closing_balance`. That is the rule,
not five exceptions: **a document a user submits carries it; a row the system appends does not.**

**But do not act on that rule without reading the next paragraph.** `probe.py --gate` fires on the
*rate* across all submittables in the app, threshold 0.94, and it does not exempt ledger rows. In a
small app one correct exception sinks the rate: an app with 7 submittables that removes the field from
its one ledger doctype sits at 6/7 = 0.86 and gates red **permanently**. A gate that always fails is
not a gate; it teaches the next session to skip the output, and a real breach walks through behind the
one everyone learned to ignore.

In an app with few submittables, keep the field on the ledger row. It costs one hidden column nothing
ever populates. The rule above tells you what is *correct*; the gate tells you what is *checkable*, and
in a small app they disagree.

```sh
locate: grep -n 'def make_amendable' -A 12 apps/frappe/frappe/core/doctype/doctype/doctype.py
       grep -n 'self.make_amendable()' apps/frappe/frappe/core/doctype/doctype/doctype.py
       grep -n 'def validate_amended_from' -A 8 apps/frappe/frappe/model/document.py
```

> Corrected 2026-08-13. This contract previously read "the framework will not add it" and stated that
> setting `is_submittable` does not create the field. Both were wrong in frappe 16.0.0-dev. Surfaced by
> the `manager` project, where a track removed the field on F4's authority, the gate went red, and the
> ruling had to be reversed twice before anyone read `make_amendable`.

### F22 — `_validate_links` runs before every hook you could set the value from. [F]

**Trigger:** you are adding a `Dynamic Link`, or a child table whose parent is meant to stamp a
field on each row.

A `Dynamic Link` resolves through the field named in its `options`. If that field is empty when
links are validated, the insert dies with `<Label> must be set first` — and there is no hook early
enough to fill it:

```
_set_defaults()          <- the only thing that runs first
set_user_and_timestamp()
set_docstatus()
check_if_latest()
_validate_links()        <- fails here
check_permission()
run_method("before_insert")
run_before_save_methods() -> before_validate, validate
```

**What breaks:** a shared child doctype that carries `against_type` + `against` and expects the
parent controller to set the type cannot be inserted at all, by anything. Not `validate`, not
`before_insert`, not `before_validate`. The design reads clean and fails on the first save.

**The two ways out, in order of preference:**

```
split the child per target      Invoice Allocation(invoice: Link Invoice)
                                Bill Allocation(bill: Link Bill)
                                a Link with one fixed target simply validates

a static DocField default       only if the type never varies by parent
```

A Dynamic Link is correct when the *caller* supplies both fields in the same dict — that is how
`Ledger Entry.voucher_type` / `voucher_no` work, and they are written entirely in code.

```sh
locate: sed -n '/def insert/,/run_before_save_methods/p' apps/frappe/frappe/model/document.py
```

### F23 — Editing a DocType in code does not reorder its fields. Set `idx` yourself. [F]

**Trigger:** you are rewriting a doctype's `fields` list programmatically —
`d.fields = []` then `d.append(...)`, or any script that redefines a schema.

Clearing the list and appending does **not** reset `idx` on rows that already existed in the
database. Those rows keep their old position; only genuinely new fields land where you put them.

**What breaks:** a doctype you *created* gets the layout you wrote. The same script run against a
doctype that already exists silently keeps the old order and interleaves the new fields after it.
Nothing errors. The form looks wrong and the JSON on disk looks wrong, and neither `bench migrate`
nor any gate has an opinion about field order.

```python
for position, row in enumerate(d.fields, start=1):
    row.idx = position
d.save()
```

> The same trap, one level up: **if a script defines your schema, the script is the schema.** A
> field added by hand on the site is deleted the next time the script runs — see F27.

---

## 2 · I am about to write permissions, roles, or anything with an authority dimension

### F5 — Nine DocPerm flags default to 1. An omitted flag is a granted flag. [F]

**Trigger:** you are about to write a `permissions` block, a `DocPerm` row, or a role.

```
default = 1     read  write  create  delete  report  export  share  print  email
default = 0     submit  cancel  amend  import  select  if_owner  mask
```

```python
# grants read, write, create, DELETE, report, export, share, print, email
{"role": "Clerk", "read": 1}
```

**What breaks:** clerks can delete records, and there is nothing in the code that produced the
row to see. Write every flag, including the zeros:

```python
{"role": "<Domain> User",    "read": 1, "write": 1, "create": 1, "delete": 0,
 "submit": 1, "cancel": 0, "amend": 0,
 "report": 1, "export": 0, "share": 0, "print": 1, "email": 1}
{"role": "<Domain> Manager", "read": 1, "write": 1, "create": 1, "delete": 1,
 "submit": 1, "cancel": 1, "amend": 1,
 "report": 1, "export": 1, "share": 1, "print": 1, "email": 1}
```

```sh
locate: python3 -c "import json;d=json.load(open('apps/frappe/frappe/core/doctype/docperm/docperm.json'));print([(f['fieldname'],f.get('default')) for f in d['fields'] if f['fieldtype']=='Check'])"
```

### F6 — You cannot audit permissions from the JSON. Ever. [F]

**Trigger:** you are about to read a doctype `.json` to decide who can do what — including
reviewing your own work.

`before_export` deletes **every falsy value, recursively**, from the exported document. So
`"delete": 0` and an absent `delete` key are byte-identical on disk. Deliberate denial and
true omission cannot be distinguished after export.

**What breaks:** any audit, count or review of permissions taken from files describes the
exporter, not the app. A published measurement of "granting by omission" in erpnext and hrms
was withdrawn for exactly this reason — it is not knowable from the files, and no check in
this kit attempts it.

**The only check that works — run it as the person, not as Administrator:**

```python
frappe.set_user("<the least-privileged user who must still be able to work>")
for dt in ["<DocType>", ...]:
    for p in ("read", "write", "create", "submit", "delete", "cancel", "amend"):
        print(dt, p, frappe.has_permission(dt, ptype=p))
doc = frappe.get_doc("<DocType>", name)
doc.delete()          # expect frappe.PermissionError. If it succeeds, you found one.
```

One session run this way surfaced four permission defects immediately — the cheapest
high-yield check in the entire record this kit is built from. `probe.py` prints this block
with your bench and site already filled in.

**Not covered by it:** row-level visibility — User Permissions, `if_owner`,
`permission_query_conditions`. Those need a real query as that user, not a `has_permission`
call.

```sh
locate: grep -n 'def before_export' -A 14 apps/frappe/frappe/core/doctype/doctype/doctype.py
```

**[R]** Role shape in both references: `<Domain> User` does the work, `<Domain> Manager`
approves/cancels/amends, plus `System Manager`. Median 3 permission rows per non-child doctype
(erpnext max 11, hrms max 8). Do not invent a role per doctype.

### F24 — `submit`, `cancel` and `amend` are illegal on a doctype that is not submittable. [F]

**Trigger:** you are writing a permission block from a shared helper, or copying one between
doctypes.

`validate_permissions` refuses them: `Cannot set Assign Submit if not Submittable`. A "grant
everything" helper written for transactions throws the moment it touches a master.

```python
FULL_MASTER = dict(read=1, write=1, create=1, delete=1,
                   report=1, export=1, share=1, print=1, email=1)
FULL_TXN    = dict(**FULL_MASTER, submit=1, cancel=1, amend=1)
```

**[R]** Zero non-submittable doctypes in frappe carry any of the three. A `.json` on disk that does
carry one was not written through the framework — the framework cannot produce it.

```sh
locate: grep -n 'def check_if_submittable' -A 8 apps/frappe/frappe/core/doctype/doctype/doctype.py
```

---

## 3 · I am about to write behaviour

### F7 — Search for the helper before writing it, in benches you are not working in. [F]

**Trigger:** you are about to write a function that formats money, parses a date, rounds,
converts a number to words, builds a link, or does anything that sounds generic.

`frappe.utils` already has `flt`, `cint`, `cstr`, `rounded`, `fmt_money`, `money_in_words`,
`getdate`, `add_days`, `nowdate`, `get_link_to_form`. Client-side, frappe ships `flt`,
`format_number`, `format_currency` as globals. `money_in_words` is **not** exposed
client-side — call the server or whitelist a wrapper.

**What breaks:** nothing. You just wrote a worse version of something that already exists, and
now it is yours to maintain. This is the complaint that started the whole investigation.

**The scoping failure that matters more.** A prior-art search correctly scoped to the installed
apps missed `StatusUpdater`, `get_gl_dict`, `get_balance_on` and `get_stock_balance` — because
erpnext sat in a different bench on the same disk. `probe.py --wide` prints the grep with every
reachable bench already in it.

```sh
locate: grep -rn "^def <name>" apps/frappe/frappe/utils/
search: grep -rn "def <name>" <every bench>/apps --include='*.py' | head
```

**These live in erpnext, not frappe** — knowing which side of the line something is on decides
whether you depend on erpnext or reimplement:

```
get_balance_on · get_stock_balance · get_fiscal_year · validate_fiscal_year
StatusUpdater · get_gl_dict          all erpnext
```

**The sharper case: contracts that carry permissions.** A utility you rewrite is a maintenance
cost. A *behaviour* you rewrite silently drops what it enforced. Prefer frappe's own path over
your own for anything that scopes, filters or gates:

```
frappe.get_list / frappe.db.get_list     applies permissions and User Permissions
frappe.has_permission                    the same check the desk makes
Report.is_permitted                      report visibility, not just doctype access
permission_query_conditions              the list-view fragment — pair it with has_permission
                                         or rows leak into lists
```

A raw `frappe.db.sql` that reimplements a listing has no permission layer at all, and nothing
will tell you. One surveyed app overrode `frappe.desk.query_report.run` app-wide to restore
company isolation that its own raw SQL had removed — every step followed from the one before,
and the first step was where it should have stopped.

**When mirroring desk behaviour** — routing, formatting, gating, a widget's load path — read
how frappe's own implementation does it and copy that contract, with the file and line, per
F11. Do not infer it from the rendered result.

### F8 — A figure derived from other documents is recomputed, never adjusted. [F][R]

**Trigger:** you are about to write `+=` or `-=` near a stored figure, or an `on_cancel` branch
that undoes what `on_submit` did.

The whole substrate is four things: `docstatus` (0 draft / 1 submitted / 2 cancelled),
`doc_events` in `hooks.py`, `frappe.db.set_value`, and `doc.precision(fieldname)`. There is no
ledger and no status engine in frappe — `apps/frappe` contains zero files mentioning
`outstanding`, `debit`, `credit` or `fiscal_year`.

```python
def refresh_<thing>(name: str) -> None:
    """Recompute from the source documents. Never adjust."""
    doc = frappe.get_doc("<Doctype>", name)

    # docstatus == 1 is LOAD-BEARING. Omit it and drafts and cancellations both leak in.
    rows = frappe.get_all("<Source>", {"<link>": name, "docstatus": 1}, pluck="name")
    figure = <sum or count over rows>

    # the cache field AND the status, in this one function. Never separately.
    frappe.db.set_value("<Doctype>", name, {
        "<cache_field>": figure,
        "status": _status(doc, figure),
    }, update_modified=False)

def _status(doc, figure):
    if doc.docstatus == 2: return "Cancelled"      # status starts from docstatus
    if doc.docstatus == 0: return "Draft"          # and only then refines
    ...

class <Doctype>(Document):
    def on_submit(self): refresh_<thing>(self.name)
    def on_cancel(self): refresh_<thing>(self.name)   # the SAME call. Nothing is undone.
```

**Why:** idempotent, so one handler binds to `on_submit`, `on_cancel` and
`on_update_after_submit` with no per-event direction logic. Cancellation is free — a cancelled
document stops matching `docstatus == 1`. Order cannot corrupt it. The cost is a query per
refresh; both reference apps pay it.

**What breaks with `+=`:** every property above, at once. A handler bound to three events
double-counts on the second.

When the settling document belongs to another app, bind through `hooks.py`:

```python
doc_events = {"<Their Doctype>": {"on_submit": "myapp.mod.refresh",
                                  "on_cancel": "myapp.mod.refresh",
                                  "on_update_after_submit": "myapp.mod.refresh"}}
```

**With money in it, three more things.** Compare at `flt(x, doc.precision(field))` — a raw
float `==` leaves a document a ten-thousandth short of `Paid` and it stays collectable. Watch
which currency the figure is denominated in. And ledger entries must carry every field the
recompute sums: a hand-built entry dict setting only `debit` and `credit` posts a ledger that
balances, passes every double-entry check, and leaves the outstanding sum at zero forever.

```sh
locate: grep -rn "outstanding\|fiscal_year" apps/frappe/frappe --include='*.py' | wc -l   # 0
```

### F9 — Split user-driven state from derived state before writing either. [F]

**Trigger:** you are about to add a `status` field, or a state machine of any kind.

```
a PERSON decides it   →  the Workflow engine — declarative, no python
OTHER DOCUMENTS decide it →  F8's recompute pattern
```

Frappe ships a Workflow engine — nine doctypes. `Workflow Document State` carries
`state · doc_status · update_field · update_value · allow_edit · message ·
next_action_email_template · avoid_status_override · evaluate_as_expression`. `update_field` +
`update_value` keep a plain `status` Select correct **with no controller code at all**.

**[R] Neither reference app ships a single Workflow record.** erpnext 0, hrms 0. Both
hand-roll status instead — erpnext with a `status_map` table that is a parallel implementation
of a mechanism the framework already has. So there is nothing to copy by proximity, and an app
built by imitation will never find the engine. That is why this row exists.

**Two rules the engine enforces, both found by running it rather than reading it:**

- Only four `docstatus` moves are legal: `0→0`, `0→1`, `1→1`, `1→2`. Nothing leaves cancelled.
  So *abandoning a draft* and *cancelling a submitted document* are different outcomes needing
  different states.
- Any field named in `update_field` needs `allow_on_submit: 1`, or a `1→1` transition dies
  with `UpdateAfterSubmitError`. The workflow validates and saves cleanly and fails only on use.

```sh
locate: grep -n 'def validate_docstatus' -A 45 apps/frappe/frappe/workflow/doctype/workflow/workflow.py
        ls apps/frappe/frappe/workflow/doctype/
```

### F10 — `Document Naming Rule` exists and runs before `autoname`. [F]

**Trigger:** you need naming that is conditional, or you need to rename another app's doctype
without editing it.

`Document Naming Rule` carries `prefix`, `counter`, `prefix_digits`, `conditions` and
`priority`. Rules run **before** the doctype's own `autoname`, ordered by `priority desc`, and
each fires only when its conditions match the document.

**[R]** erpnext ships 0 of these; hrms ships 0. Same shape as F9 — an alternative that exists
and has no prior art to copy.

> A doctype with no `autoname` of its own gets a hash name. Rename before exporting, or you
> ship a file called `0sa5t63puu.json`.

```sh
locate: grep -n 'document_naming_rule\|def set_name_from_naming_options' apps/frappe/frappe/model/naming.py
```

### F11 — Before replacing framework behaviour, quote its contract with file and line. [A]

**Trigger:** you are about to write your own version of something the framework does —
a generator, a status engine, a permission filter, a naming scheme, an exporter.

If you cannot find and quote the contract, you are not ready to replace it. Two substitutes in
the record carried no contract; neither crashed at the time. One of them — a 2,637-line private
doctype generator missing a single `if not self.istable` — produced a 100% deviation rate that
survived ten weeks of active maintenance because nothing was checking and nothing in the
process was capable of checking.

**Paste into the code, beside the substitute:**

```
# Replaces <frappe symbol>.  Contract quoted from <file:line>, located <date>:
#   <the quoted lines>
# Not carried: <what this substitute deliberately does not do>
```

---

## 4 · I am about to make something visible or interactive

### F12 — Reach for the DocType JSON first. The client layer gets what is left. [F][R]

**Trigger:** you are about to write `toggle_display`, `toggle_reqd`, `set_df_property`, or a
`set_value` that copies a field from a linked document.

All of these are DocField properties, verified in `docfield.json`:

```
depends_on · mandatory_depends_on · read_only_depends_on
fetch_from · fetch_if_empty · default · link_filters
precision · non_negative · unique · set_only_once
allow_on_submit · no_copy · translatable · in_list_view · in_standard_filter
```

```json
{"fieldname": "damage_notes", "fieldtype": "Small Text",
 "depends_on":           "eval:['Damaged','Lost'].includes(doc.condition)",
 "mandatory_depends_on": "eval:['Damaged','Lost'].includes(doc.condition)"}
```

**[R]** Declarative beats imperative about 5:1 in both references — erpnext 1,469 declarative
conditions against 300 client-side calls, hrms 276 against 58. `fetch_from`: erpnext 365, hrms
236 (in hrms that *exceeds* its own `set_value` count). `default` is the single most-used field
property: erpnext 1,364, hrms 231.

**What is legitimately left for the client layer** — both references show all three:

1. **A Link filter that reads another field on the same form.** `link_filters` is static and
   cannot see `doc`, so this stays `set_query` (erpnext 467, hrms 101).
2. **A button that creates another document.** No field property renders one, and `DocType
   Action` is used **0 times in each** reference — so `add_custom_button` is the convention
   (erpnext 396, hrms 78). Pair it with `get_mapped_doc` server-side.
3. **A value that must be computed, not copied.** `fetch_from` cannot do arithmetic. Compute
   in `validate`; mirror client-side only so the user sees it before saving.

**The test before adding any handler — write this sentence:**

> *"The declarative mechanism for this is ______, and it is insufficient because ______."*

If you cannot write it, use the mechanism.

**Do not use client-code volume as a target.** A published ratio (submittable scripts 6.4×
others in erpnext, 3.9× in hrms) was **withdrawn as guidance**: it measures how much work those
apps do in JavaScript, and an app that puts visibility and derivation in the JSON correctly
scores low and is right.

```sh
locate: python3 -c "import json;d=json.load(open('apps/frappe/frappe/core/doctype/docfield/docfield.json'));print(sorted(f['fieldname'] for f in d['fields']))"
```

### F25 — A break is not a field. Labels on breaks render, and defaults come from outside the JSON. [F][R]

**Trigger:** you are generating fields in a loop, or you are about to give a Link field a default
that is not a constant.

**Breaks render whatever label you give them.** A `Section Break` label becomes a heading; a
`Column Break` label becomes a heading over that column. Any helper of the shape
`label = label or fieldname.replace("_", " ").title()` will therefore stamp `Sb Amt` and `Cb H`
across every form it touches, and the JSON looks fine while the form reads like a debug dump.

**[R]** The signature is precise, and it is the *column* break that gives it away — a labelled
`Column Break` is legitimate but rare, and one labelled from its own fieldname does not occur:

```
Column Break with any label            2 of 229 in frappe   (both real prose)
  ...label == fieldname titled         0 of 229             <- the generated-junk signature
Section Break, label == fieldname      34 of 345 = 9.9%     <- legitimate; do NOT flag this
```

That second band is the reason not to check section breaks: `details` → `Details` is ordinary, and
a rule against it flags a tenth of the framework.

**[R] How many columns a section actually has.** Two-column-everything is a habit, not a layout —
and it is not what the framework does:

```
1 column     324 of 492 sections   65.9%
2 columns    150                   30.5%
3 columns     14                    2.8%
4 to 6         4                    0.8%
```

A single column is the *most* common shape in frappe. A section holding one field does not need a
column break, and a header holding six does not become readable by being cut down the middle.
Column count follows what the section holds; a uniform answer across every form in an app means
nobody chose.

**Fields that exist for a capability that is switched off do not belong on the screen.** A
`currency` and `exchange_rate` pair carried so that multi-currency is later a form change rather
than a ledger migration is correct schema and wrong furniture — `hidden: 1` until the pack that
uses them ships.

**Defaults that are not constants come from `frappe.defaults`, not from the field.** A Link field
is populated on a new document from a user or global default *of the same name* — so a `company`
Link fills itself once a default named `company` exists. No client script, no controller:

```python
frappe.defaults.set_global_default("company", "<the only company>")
```

Otherwise every form opens with an empty required box that the user answers identically every time.

```sh
locate: grep -n 'def get_user_default_value' -A 20 apps/frappe/frappe/model/create_new.py
check:  python3 probe.py --gate <app_path>
```

### F13 — A report is a Script Report with both a `.js` and a `.py`. [R]

**Trigger:** you are about to build a report.

**[R]** Script Report is 164/183 (90%) in erpnext and 27/28 (96%) in hrms. **Every single one
has both files** — 164/164 and 27/27. That is a file contract, not a tendency.

```
<module>/report/<name>/
  <name>.json    ref_doctype, report_type, module, roles
  <name>.py      def execute(filters=None) -> (columns, data)
  <name>.js      frappe.query_reports["<Name>"] = { filters: [...] }
  __init__.py
```

Columns are dicts with a `fieldtype`, never strings — a `Currency` column needs `options`
pointing at the row's currency field or it renders in the system default and quietly
misstates multi-currency data. Date filters default to a window, never empty. `company` is
`reqd: 1`.

**Permissions:** the framework applies the underlying doctype's permissions **only if
`ref_doctype` is set**. Roles on the Report restrict who sees it listed; they do not filter
rows. If the report joins several doctypes, apply the conditions yourself.

Query Report — a stored SQL string — is used 13 times in erpnext and never in hrms. It cannot
take typed filters, cannot apply permissions, and cannot be tested.

---

### F20 — The client layer must be able to intervene, not only display. [R]

**Trigger:** you are adding client behaviour, or you are about to call a form "done".

Lifecycle events split into two kinds, and an app can use only the first without noticing:

```
DISPLAY    refresh · setup · onload · onload_post_render      fires when the form APPEARS
INTERVENE  validate · before_save · before_submit · on_submit · on_cancel · after_save
```

**[R]** erpnext: 31 files touch an intervening event, 116 client-side `frappe.throw`. hrms:
7 and 19. An app surveyed with 165 client script files had **0 and 0** — three events in use,
all display-time. It could show things. It could not stop anything.

**What breaks:** the user is told about a mistake at save, or not at all — never at the moment
they make it. A form that only paints is a form that lets bad data through and then argues
about it afterwards.

**The artifact — the sentence you write when a validation goes server-side instead:**

> *"This throws in `validate` rather than client-side because ______."*

Server-side validation is correct and is the floor; it is not a reason for the client layer to
be silent about something the user can see going wrong while they type.

`probe.py` prints the split, and names it when an app has no intervening event and no throw.

### F21 — Every validation you add gets a negative test that proves it throws. [A]

**Trigger:** you just wrote a `frappe.throw`, a `mandatory_depends_on`, a permission rule, or
any other refusal.

A validation that has never refused anything has not been tested; it has been *typed*.

```python
import frappe
from frappe.tests.utils import FrappeTestCase   # or just assert in a script

doc = <build the document in the state that must be refused>
try:
    doc.insert()          # or .submit()
    raise AssertionError("expected a refusal and got none")
except frappe.ValidationError as e:
    print("refused as intended:", e)
```

Pair it with F18: tag the assertion. A negative test you designed yourself is still `(a)`.

---

## 5 · I am about to run a script, a batch, or a migration

### F14 — A row in the database is not yet in the app. [F]

**Trigger:** you just created a Workspace, Print Format, Custom Field, Property Setter,
Notification, Dashboard Chart or Number Card.

Doctypes are exported to files automatically. **Nothing else is.**

```python
export_to_files(record_list=[["Workspace", "<name>"]], record_module="<Module>")
```

**What breaks:** a workspace reported as created with `20 links, 8 shortcuts` existed only as a
database row; a directory listing two steps later showed nothing on disk.

**Paste — read the durable side by name, then say which side you read:**

```sh
ls -la apps/<app>/<app>/<module>/workspace/<name>/     # not "the code said it worked"
```

> Pairs to check by name after any write: `DB ≠ disk · memory ≠ file · staged ≠ committed ·
> in-process ≠ persisted`.

```sh
locate: grep -n 'def export_to_files' -A 20 apps/frappe/frappe/modules/export_file.py
```

### F15 — The script runner, and the commit that is not optional. [F]

**Trigger:** you are about to pipe python into `bench console`.

It breaks on multi-line blocks. Run the environment directly, from the bench's `sites/`:

```sh
cd <bench>/sites && ../env/bin/python - <<'PY'
import frappe
frappe.init(site="<site>", sites_path="."); frappe.connect()
frappe.set_user("Administrator")
# ... work ...
frappe.db.commit()      # WITHOUT THIS the work rolls back on exit — and the script
frappe.destroy()        # still prints every success message it contains
PY
```

`probe.py` prints this with your bench and site filled in. `frappe.flags.in_migrate = True`
suppresses some interactive guards when creating doctypes programmatically.

### F16 — Read the tool's output, not its exit code. [F]

**Trigger:** you just ran `bench migrate`, `bench build`, `bench install-app`, or any batch.

`Orphaned DocType(s) found: UOM` is **one line inside a migrate that otherwise succeeds and
exits 0**. So is most of what matters.

```sh
bench --site <site> migrate 2>&1 | tee /tmp/migrate.log
grep -iE "orphan|error|traceback|skipp|warn|missing" /tmp/migrate.log
```

**And let operations fail loudly.** Two defects in the record surfaced only because an insert
threw and a `reload()` broke. Both were invisible while the data stayed in memory.

### F26 — Deleting a DocType leaves its folder, and the next migrate puts it back. [F]

**Trigger:** you just ran `frappe.delete_doc("DocType", ...)`, or removed a doctype any other way.

The database row goes. **The directory on disk does not.** `bench migrate` imports doctypes from
files, so the next migrate re-creates every one you deleted, silently and completely.

This is F14 running in the other direction: there, a record existed in the database and not on
disk; here it exists on disk and not in the database. Both are the same question — *which side did
I actually read?*

```sh
# after any doctype deletion, compare the two sides by name
ls -d apps/<app>/<app>/*/doctype/*/ | wc -l      # disk
bench --site <site> execute frappe.client.get_count --args '["DocType",{"module":"<Module>"}]'
```

Remove the folders too, under a guard that refuses to run unless it matches what you intended:

```python
assert sorted(found) == sorted(intended), f"refusing: {set(found) ^ set(intended)}"
```

### F30 — Importing a Workspace from a script deletes its source folder. Migrate is safe. [F]

**Trigger:** you are about to install, verify, or repair a Workspace outside `bench migrate`.

Two traps, from opposite directions. Both fired on the same project inside one hour, the second one
twice, the second time on the person who had just written down the warning.

**Trap 1 — the import eats the file.** Not only `import_file_by_path`. `frappe.reload_doc(..., force=True)`
runs the same path. It calls `frappe.delete_doc(..., for_reload=True)`, and **`for_reload` does not
suppress `after_delete`** — that call sits outside the guard. `Workspace.after_delete` calls
`delete_folder`, which is `shutil.rmtree`.

A filesystem delete is not in the transaction, so both outcomes are bad and neither announces itself:

| You did | Database | Disk |
|---|---|---|
| rolled back | correct, restored | **folder gone** |
| committed | correct | **folder gone, app ships no workspace** |

`bench migrate` is safe, and only by accident of a guard: `after_delete` returns early when
`disable_saving_as_public()` is true, which covers `in_migrate`, `in_install`, `in_patch`, `in_test`,
`in_fixtures`, `in_uninstall`. A bare script sets none of them.

> **Never import a Workspace from a script, including to verify one.** Verify by reading the database.
> To install one, run `bench migrate`.

**Trap 2 — migrate silently skips it.** The `modified` field in the JSON is the sync key, not
decoration. If it matches the database row, import skips the file and **migrate reports success having
installed nothing.** It is indistinguishable from a real migrate unless you read the database after.

**Repair, when the database holds the good copy.** Export, never import:

```python
export_to_files(record_list=[["Workspace", "<Name>"]], record_module="<Module>")
```

`export_to_files` only writes. `delete_folder` is reached from `after_delete` and from a module or
title change, so exporting is safe exactly where importing is not.

**Then bump `modified` in the file**, strictly past the database row. The export writes the row's own
timestamp back, which re-arms trap 2 immediately.

```sh
locate: grep -n 'def after_delete' -A 8 apps/frappe/frappe/desk/doctype/workspace/workspace.py
       grep -n 'def disable_saving_as_public' -A 8 apps/frappe/frappe/desk/doctype/workspace/workspace.py
       grep -n 'run_method("after_delete")' apps/frappe/frappe/model/delete_doc.py
```

**Verify a workspace off the database, never off the file**, and check reachability rather than counts:

```python
d = frappe.get_doc("Workspace", "<Name>")
reach = {l.link_to for l in d.links} | {s.link_to for s in d.shortcuts}
missing = [x for x in frappe.get_all("DocType", filters={"module": "<M>", "istable": 0}, pluck="name")
           if x not in reach]
```

### F27 — If a script defines the schema, the script is the schema. [A]

**Trigger:** you built doctypes with a generator script and are about to add one field on the site,
or through the desk, or in a console one-liner.

The next run of that script removes it. Nothing warns, because nothing knows the two were meant to
agree — and the failure is quiet in the worst way: a field the code reads disappears, so the code
still imports, still migrates, still passes the gate, and starts returning zero.

**Both halves, or neither:**

```
change the spec script   -> re-run it   -> the site follows
change the site only     -> the next run of the spec silently reverts you
```

**Paste — the check that makes drift loud.** One test per field the spine actually reads:

```python
def test_<the field> (self):
    self.assertIsNotNone(frappe.get_meta("<DocType>").get_field("<field>"),
                         "<DocType>.<field> is missing — <what reads it> depends on it")
```

And prove the generator is idempotent, which is the only evidence that it is authoritative:

```python
before = {d: [f.fieldname for f in frappe.get_meta(d).fields] for d in doctypes}
<re-run every spec script>
after  = {d: [f.fieldname for f in frappe.get_meta(d).fields] for d in doctypes}
assert before == after, [d for d in doctypes if before[d] != after[d]]
```

---

## 6 · I am about to say it is done

### F17 — Execute it once, end to end, and read back the document that should have changed. [F]

**Trigger:** you are about to write "done", "working", "wired", "verified", or "fixed".

Not the document you built. The one downstream of it.

```python
inv = <create and submit the document>
pay = <create and submit the thing that settles it>
inv.reload()                                   # without this you read a stale in-memory doc
assert flt(inv.outstanding) < 0.005            # THIS is the assertion that goes missing
assert inv.status == "Paid"
pay.cancel(); inv.reload()                     # the property the whole design rests on
assert flt(inv.outstanding) == flt(inv.total)
assert inv.status != "Paid"
```

**What breaks without it:** the end-to-end test that missed a real money bug asserted that
debits equalled credits and that stock moved. Both true. Both about the thing *constructed*
rather than its *consequence*. The invoice showed the full amount owing after being paid in
full, and offered itself for collection again.

Five of seven defects found during one build surfaced as an insert that threw, a `reload()`
that broke, or one line of migrate output. Running it once is most of the yield.

### F18 — Tag every assertion you write by where it came from. [A]

**Trigger:** you are writing a test, a gate, a linter, or any check.

```
(a) mine   (b) framework source   (c) the user's stated requirement   (d) an external spec
```

**All `(a)` means get one non-`(a)` before running it.** In the record this kit draws on, six
process gates, a linter and a full end-to-end test were green, all `(a)`, and missed 8 of 16
things the shop had to be able to do. Not one defect came from a check its author designed.

Corollary: **do not set a threshold from the dataset you then validate against.** A 10% gate
derived from three reference rates and confirmed by checking it passes those same three rates
cannot fail that test.

### F28 — Break the code on purpose and watch a check fail. [A]

**Trigger:** F18 told you every assertion is `(a)`, and you cannot get a `(b)`, `(c)` or `(d)` one.

A passing suite you wrote against code you wrote is evidence that the two agree, and nothing more.
Mutation is the cheapest way to find out whether it is evidence of anything else: revert one real
decision, run the suite, and see whether anything notices.

```sh
# revert the decision, run only the tests that should care, restore from git
<edit the one line that embodies the decision>
bench --site <site> run-tests --app <app> --module <the module that should fail>
git -C apps/<app> checkout -- <the file>
grep -rn "MUTANT" apps/<app> || echo "clean"      # prove the restore happened
```

Pick the mutation that separates your design from the obvious wrong one — not a typo. If reverting
the actual decision leaves the suite green, the suite is not testing the decision.

> Run `git checkout` from inside the repository. Run it from a parent directory that is not a git
> repo and it fails, prints to stderr, and leaves the mutant in your working tree — which is B5 and
> F14 again: read the durable side by name.

### F29 — Nothing in this kit has looked at the form. Open it. [A]

**Trigger:** the gate is green, the tests pass, and you are about to call a document finished.

Every check here reads files or runs documents. **Not one of them renders anything.** So this
entire class survives all of it, silently:

```
field order            a doctype edited in code keeps its old order — F23
labels on breaks       a generator's headings, printed as if a human wrote them — F25
column shape           every section cut in half because a helper always emits one break
a required empty box   a Link with no default, answered identically by every user, every time
what is on screen      plumbing for a switched-off capability, sitting above the customer name
```

`bench migrate` has no opinion about any of it. Neither does `probe.py --gate`. Neither does a
passing test suite, because a test asserts what a document *does* and every one of these is about
what a person *sees*.

**Paste — the cheapest version, once per document, before it ships:**

```sh
bench --site <site> browse                 # then open one new document of each type
```

> Read it as the person who fills it in, in their order: can they start at the top and go down? Is
> anything on screen that they cannot act on? Is anything required that the system already knows?
> This is the only check in the kit whose instrument is a pair of eyes, and it is the one that
> found the four defects the other twenty-eight rows had passed.

### F19 — The gate covers the creation path. It says nothing about whether the app works. [A]

```sh
python3 probe.py --gate <app_path>        # exit 1 on a framework contract breach
```

A green result means the files were made through the framework and submittables can be
amended. **It means nothing else.** It is not a claim about behaviour — that is F17 — and it is
not a claim about anything a person would see on a screen, which is F29. The same conformance check passed an app cleanly while
that app let a shop collect the same money twice. Green is not a claim about behaviour;
`F17` is the only thing in this file that is.

---

## 7 · No convention exists here. Decide once, app-wide, and write it down.

Both references are mature and they **disagree** on these. There is nothing to inherit, and an
app that mixes both sides of any of them is worse than one that picks the "wrong" side
consistently. `probe.py` prints which side the app you are in has already picked — match it.

| | erpnext | hrms | how to choose |
|---|---|---|---|
| **naming series declaration** | `naming_series` field, 46/81 | fixed `autoname` string, 38/53 | a `naming_series` Select if users will ever need more than one series per document — retrofitting means a migration. Fixed string otherwise. |
| **controller depth** | 6 levels, every transaction inherits through the chain | **147 × `Document`**, 2 × its own, 3 × borrowed | `Document`. Create a shared base only when two or more documents *already* share machinery, and name it for the machinery. |
| **client architecture** | ES6 classes extending a shared controller | flat `frappe.ui.form.on` handlers | flat by default. Introduce the class form when a second and third document need the same behaviour, not before. |
| **`track_changes` on masters** | 60% | 42% | on for anything whose historical values someone might later dispute — rates, prices, entitlements, approvers. Off for lookup lists. |
| **`extend_` vs `override_doctype_class`** | `extend_doctype_class` | `override_doctype_class` | extend when adding; override when you must intercept. Override is the heavier commitment — you now own compatibility with the base app's future. |
| **app-level structure** | `setup/`, `commands/`, `domains/` | `install.py`, `overrides/`, `mixins/`, `api/`, `required_apps` | by which of the two your app is. Extending another app pulls the hrms set; standing alone pulls the erpnext set. |

**[R] Two more shapes worth matching, where they do agree:**

- **A master is named by its own natural key; a transaction by a generated series.**
  `autoname: field:<x>` sits at 51%/53% of masters against `naming_series` at 8%/2%. A master
  with a serial-numbered name usually is not a master. Masters get `allow_rename`, and a
  `disabled` flag — **disable, never delete**, because a master referenced by historical
  documents can never be removed.
- **`validate` is a flat list of named method calls, never inline logic, and it ends with
  `set_status()`.** `on_cancel` mirrors `on_submit` line for line and adds
  `self.ignore_linked_doctypes = (...)` for every ledger the document wrote. Write the pair in
  the same sitting and keep them adjacent in the file. `on_cancel` is present in 8/8 sampled
  transactions across both apps — more often than `on_submit`.

---

## What is deliberately not here

Recorded so it is not quietly re-acquired. Each of these was claimed somewhere upstream and
does not survive:

- **Test-stub counts as a quality signal.** The framework generates `test_<name>.py` for every
  non-child doctype and the stub *is* `pass`. File counts measure nothing. What the signal does
  separate is published apps from local ones (erpnext 61%, hrms 66%, every local app at or near
  zero) — a different axis from the one it gets reached for.
- **"Behaviour outside the module directories" as a structural defect.** Counted: hrms, an
  ecosystem reference, sits at 84% — closer to the apps under suspicion than to the ones held
  up as clean. The signal does not discriminate.
- **Large-file line counts as the shape of a problem.** Counted: the app held up as conforming
  had the *larger* god-file. What survived is the **growth curve** — twelve commits, twelve
  increases, zero decreases, while four new modules were created elsewhere in the same period.
  Accretion without extraction is measurable; size alone is not.
- **A permission-omission rate measured from JSON.** Unmeasurable — see F6.
- **A client-code volume target.** Withdrawn — see F12.

## What this kit does not establish

- **Nothing here has been used by a session other than the one that wrote it.** Every claim
  about whether it changes an outcome is design intent.
- **No commit-time gate in this lineage has ever been installed in a real repository**, so the
  prediction that gating changes outcomes is untested.
- **Nothing about a human maintainer was ever measured.** Every claim about maintainability
  upstream of this file is inferred from structure. Do not cite this kit as a maintainability
  argument.
- **The reference bands rest on two apps from one publisher** (Frappe Technologies). A
  well-regarded third-party app would firm them and might break some.
