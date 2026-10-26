# tasks/ — the work queue

One file per task. Anyone may create one; after that the owner is the only writer. Closed tasks
move to `archive/done-tasks/` with a completion line. Template: `_TEMPLATE.md`.

`blocked-on` is load-bearing: a queue that cannot say what it is waiting on reads as stalled
work.
