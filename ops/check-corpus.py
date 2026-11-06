#!/usr/bin/env python3
"""Structural checks over the corpus. Advisory: always exits 0.

Every defect a system like this has is one of three shapes:
  1. A fact living in more than one place, and the copies disagreeing.
  2. A pointer to a file that moved or was archived.
  3. A figure restated somewhere it should only be cited.
None needs judgment to detect, so check them mechanically.

Run: python3 ops/check-corpus.py [--only pointers|prices|placeholders]

A line holding a dollar figure that is not something you charge (a customer's revenue, a funding
round) can carry the marker <!-- not-a-price -->. "$5M in revenue" style figures are skipped.

--only placeholders is the setup check: it fails on an untouched clone and passes once the
canon is filled. It is not part of the default run.
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "ops/checks.json").read_text())
SKIP = {".git", "archive", "node_modules", "sessions", ".vercel"}
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k|K|m|M|b|B)?\b")
# A magnitude describing a customer, not a price: "$500M-$5B in assets", "$1.2B assets".
NOT_PRICE = re.compile(r"\$[\d.,]+\s?[KMBkmb]?(?:\s?(?:-|–|to)\s?\$?[\d.,]+\s?[KMBkmb]?)?\s+(?:in\s+|of\s+)?"
                       r"(?:assets|revenue|arr|aum|funding|valuation|sales)\b", re.I)
POINTER = re.compile(r"`([\w./-]+\.(?:md|py|json|sh|yml|js))`")


def files():
    for p in ROOT.rglob("*"):
        if p.is_file() and not SKIP & set(p.relative_to(ROOT).parts) and p.suffix in {".md", ".html", ".json", ".py"}:
            yield p


def rel(p):
    return p.relative_to(ROOT).as_posix()


def price_ok(r, line):
    if r.startswith("clients/"):
        return r.endswith("custom-offer.md") or "[contracted]" in line
    return any(r == k or r.startswith(k) for k in CFG["price_ok"])


def check_prices():
    out = []
    for p in files():
        r = rel(p)
        if r.startswith("ops/"):
            continue
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            if "not-a-price" in line or (r.endswith("company-context/SKILL.md") and line.startswith("| Size")):
                continue
            if MONEY.search(NOT_PRICE.sub("", line)) and not price_ok(r, line):
                out.append(f"{r}:{n}: figure outside commercial.md. Cite it instead, or mark the line "
                           f"<!-- not-a-price --> if it is not something you charge: {line.strip()[:100]}")
    return out


def check_pointers():
    out = []
    skills = ROOT / ".claude/skills"
    for p in files():
        if p.suffix != ".md":
            continue
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            for m in POINTER.finditer(line):
                t = m.group(1)
                if "<" in t or "/" not in t or "CHANGE-ME" in t:
                    continue
                cands = [ROOT / t, p.parent / t, skills / t]
                if not any(c.exists() for c in cands):
                    out.append(f"{rel(p)}:{n}: pointer goes nowhere: {t}")
    return out


def check_placeholders():
    """Setup step 1 is done only when the template text is gone."""
    def read(p):
        f = ROOT / p
        return f.read_text(errors="ignore") if f.exists() else ""
    out = []
    if re.search(r"^This repo is COMPANY's", read("CLAUDE.md"), re.M):
        out.append("CLAUDE.md: company name is still the placeholder")
    commercial = read(CFG["commercial"])
    if "YYYY-MM-DD" in commercial:
        out.append(f"{CFG['commercial']}: 'Last ruled' is not filled")
    if re.search(r"^\| Tier [12] \|", commercial, re.M):
        out.append(f"{CFG['commercial']}: §1 still has the template tiers")
    for n, line in enumerate(read(".claude/skills/company-context/SKILL.md").splitlines(), 1):
        if re.fullmatch(r"\| (Company type|Size \(employees / revenue\)|Geography) \| *\|", line.strip()):
            out.append(f"company-context:{n}: ICP row is empty: {line.strip()}")
    rules = read("docs/non-negotiables.md").split("## 1.", 1)
    if len(rules) > 1 and "RULED by NAME" in rules[1]:
        out.append("docs/non-negotiables.md: rulings still say NAME; put who ruled and when")
    if re.search(r"^\| \| \| live / beta / planned", read(".claude/skills/product-context/SKILL.md"), re.M):
        out.append("product-context: Products table is still the template row")
    if "<The objection in their words>" in read(".claude/skills/sales-playbook/references/objections.md"):
        out.append("objections.md: no objection filled")
    return out


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    checks = {"prices": check_prices, "pointers": check_pointers, "placeholders": check_placeholders}
    total = 0
    for name, fn in checks.items():
        if (only and name != only) or (not only and name == "placeholders"):
            continue
        found = fn()
        total += len(found)
        print(f"== {name}: {len(found)}")
        for f in found:
            print("  " + f)
    print(f"\n{total} finding(s). Advisory.")


if __name__ == "__main__":
    main()
