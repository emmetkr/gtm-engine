#!/usr/bin/env python3
"""Gate over the send surfaces: banned terms and retired names reaching a client.

check-corpus.py catches wrong STRUCTURE. This catches wrong CLAIMS on the way out.
Terms live in ops/checks.json -> banned_terms. Advisory: always exits 0.

Run: python3 ops/check-client-copy.py [path ...]
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT / "ops/checks.json").read_text())
TERMS = {k: v for k, v in CFG["banned_terms"].items() if not k.startswith("_")}


def targets():
    args = [pathlib.Path(a) for a in sys.argv[1:]]
    roots = args or [ROOT / p for p in CFG["client_copy_paths"]]
    for r in roots:
        if r.is_file():
            yield r
        elif r.is_dir():
            yield from (p for p in r.rglob("*") if p.suffix in {".md", ".html", ".txt"} and p.name != "README.md")


def main():
    hits = 0
    for p in targets():
        for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
            for term, fix in TERMS.items():
                if re.search(rf"\b{re.escape(term)}\b", line, re.I):
                    hits += 1
                    print(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}:{n}: '{term}' → {fix}")
            if "—" in line:
                hits += 1
                print(f"{p.relative_to(ROOT) if p.is_relative_to(ROOT) else p}:{n}: em dash in client copy")
    print(f"\n{hits} finding(s). Advisory.")


if __name__ == "__main__":
    main()
