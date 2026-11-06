---
name: setup
description: >
  Guided first-run setup for this GTM engine. Use when the user says "set me up", "get started",
  "walk me through setup", "where do I start", "continue setup", or when CLAUDE.md's First run
  rule fires (the canon still holds placeholders). Walks the user through SETUP.md one step at a
  time as a conversation, does the writing for them, verifies each step's check, and records
  progress in SETUP-PROGRESS.md so a later session resumes where this one stopped.
---

# Setup — walk the user through it

The steps, their order and their checks live in `SETUP.md`. This skill is the method for
walking someone through them. Do not restate the steps here or anywhere else.

## Start

1. Read `SETUP.md` and `SETUP-PROGRESS.md`.
2. If nothing is ticked, say in two or three sentences what they are about to build, that the
   whole thing takes about an hour to a first scored call, and that they can stop at any step
   and pick up later by saying "continue setup". Then start step 0.
3. If some steps are ticked, say which step is next and what it ends with, then start it.

## How to run each step

- **One step at a time, one question at a time.** Never paste the whole of SETUP.md back at
  them. Ask, wait, write, move on.
- **You write, they talk.** The user never opens a file. Turn their answers into the files the
  step names. Show a short summary of what you wrote, not the whole file.
- **Interview before writing.** In step 1, cover all three parts (what they sell, who outbound
  targets, which tools) before writing anything. Ask for examples: a real deal they won, a real
  objection, the price they actually quote. Push back on vague answers ("mid-market companies")
  until they are specific enough to score a call against.
- **Never invent a fact about their company.** If they don't know an answer yet, write it as an
  open row in `NEEDS.md` and keep going. Arithmetic from a rule they stated ("annual is two
  months free" → annual = 10 × monthly) is written, and flagged in `NEEDS.md` for them to confirm.
- **Ask who signs and who champions separately.** "The buyer" is often two people: the one who
  feels the pain and the one who signs. `company-context` has a row for each.
- **Steps you cannot do for them** (connecting a connector, creating a CRM property in the UI,
  adding a GitHub secret, creating a Routine): tell them exactly where to click, one action per
  line, then wait until they say it's done. If they can't do it yet (no paid plan, no access),
  record it in `NEEDS.md` and move on; mark the box `[~]` so the first-run prompt stops asking.
- **Steps you can do for them** (writing files, running the checks, calling a connected CRM to
  read stage IDs): do them, then show the result.
- **Run the check.** Most steps in SETUP.md end with a **Check**. Run it or have them run it.
  A step is done only when its check passes. If it fails, fix the cause before moving on.

## After each step

1. Tick the step in `SETUP-PROGRESS.md` with today's date, and note anything left open.
2. Commit with a message that says which step was completed.
3. Say in one line what now works that didn't before, then offer the next step. If they want to
   stop, tell them to say "continue setup" next time.

## Tools they don't have

`STACK.md` is a comparison, not a mandate. If they use a different CRM, call recorder or
scheduler from the defaults, adapt the step to their tool and record the choice where step 1
says to. If their tool has no Claude connector or API that can do the step, say so plainly,
add it to `NEEDS.md`, mark the box `[~]`, and skip to the next step that doesn't depend on it. With no CRM, step 3
still runs: score calls with `sales-call-scorer` alone (SETUP.md §3).

## Done

When step 3a is done (first call scored by hand), the engine is usable. Steps 4 and 5 automate
it. When every box is ticked, tell them setup is complete and what to say day to day:
"prep me for [company]", "process this call", "how's the pipeline".
