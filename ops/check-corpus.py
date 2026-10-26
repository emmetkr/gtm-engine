#!/usr/bin/env python3
"""Structural checks over the corpus. Advisory: always exits 0.

Every defect a system like this has is one of three shapes:
  1. A fact living in more than one place, and the copies disagreeing.
  2. A pointer to a file that moved or was archived.
  3. A figure restated somewhere it should only be cited.
None needs judgment to detect, so check them mechanically.

Run: python3 ops/check-corpus.py [--only pointers|prices]
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "ops/checks.json").read_text())
SKIP = {".git", "archive", "node_modules", "sessions", ".vercel"}
MONEY = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?\s?(?:k|K|m|M)?\b")
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
            if MONEY.search(line) and not price_ok(r, line):
                out.append(f"{r}:{n}: figure outside commercial.md — cite it instead: {line.strip()[:100]}")
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
                if "<" in t or "/" not in t:
                    continue
                cands = [ROOT / t, p.parent / t, skills / t]
                if not any(c.exists() for c in cands):
                    out.append(f"{rel(p)}:{n}: pointer goes nowhere: {t}")
    return out


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    checks = {"prices": check_prices, "pointers": check_pointers}
    total = 0
    for name, fn in checks.items():
        if only and name != only:
            continue
        found = fn()
        total += len(found)
        print(f"== {name}: {len(found)}")
        for f in found:
            print("  " + f)
    print(f"\n{total} finding(s). Advisory.")


if __name__ == "__main__":
    main()
