# Packs

Domain cartridges for [cadre](https://github.com/alooldevs/cadre)'s runtime — one repo, one pack
per directory. The core stays domain-agnostic; the material lives here.

A pack is a directory with a `detect.sh` (fast; silent when the project isn't its domain;
orienting when it is) plus whatever the domain needs: probes, contracts, generators, reference
material. Cadre's session-wiring runs every installed pack's `detect.sh` at session start.
Full anatomy: `claude/packs/README.md` in the cadre repo.

## Install

```sh
git clone git@github.com:alooldevs/packs.git ~/Documents/tools/packs   # or anywhere
cd ~/Documents/tools/packs && ./install.sh
```

Lays every pack into `~/.claude/packs/` (`./install.sh frappe` for just one). Or, with cadre
installed, just run `cadre install` (interactive choose/skip) and `cadre sync` after edits —
the repo is the source of truth, the installed copy is disposable.

## Packs

| pack | domain | what it carries |
|---|---|---|
| `frappe` | Frappe framework benches & apps | `probe.py` (orientation + gate), `CONTRACTS.md` (trigger-indexed framework contracts), `frame.py` (design-time scope generator) |
