# Oracle labelled agent steps (BFCL multi turn)

Judge inputs for single agent steps on BFCL v3 multi turn, with a label that says whether the step takes the agent off track. Built for training a step judge. Only train and val scenarios are here; the 100 test scenarios are held out on purpose, so keep them out of any training set.

## Files

| File | Rows | What it is |
|---|---|---|
| live_steps_labelled.jsonl | 3824 | Steps Qwen3 8B AWQ really took (S1, no judge), with `oracle_flag`. Use this one. |
| live_steps.jsonl | 3862 | Same steps without labels (38 have no label: their episode had no decoded call log, or the turn lay past its end). |
| oracle_labels.jsonl | 3824 | The labels alone: `id`, `run`, `k` (index of the step within that episode in live_steps.jsonl), `kind`, `oracle`. |
| gold_steps.jsonl | 3635 | Known good steps: every reference call of the train and val scenarios replayed through the same harness. All are negatives (on track). |
| split.json | | Scenario ids per split: train 74, val 15, test 100, dropped 11 (unsound reference). |

Live steps: 3204 train and 620 val. Gold steps: 3045 train and 590 val.

## Row format

One JSON object per line, one step per row.

- `id`, `version` (base, miss_param, miss_func, long_context), `scenario`, `run`, `turn`: which episode and which user turn.
- `requests`: user requests so far, latest last.
- `gold_turn`: the reference calls for this turn. Do not feed it to a judge; it is there for analysis only.
- `plan`: the planner's plan for the turn.
- `recent`, `n_recent`: earlier calls of this turn with their outputs, and how many calls ran before this step.
- `step`: the step being judged. `kind` is `call` (with `name`, `args`, `text`) or `msg` (closing message, `text`). `ev` lists where each argument value came from.
- `verdict`: what the recording judge said at run time. It passed everything, so ignore it.
- `oracle_flag` (live_steps_labelled.jsonl only): 1 means off track, 0 means fine.

## How the label is made

The oracle replays the agent's executed calls to rebuild the environment state, then replays the reference calls for the turn to get the target state (oracle.py, `offline_label`).

- A call is flagged when the target state was still reachable before it and is no longer reachable after it.
- A closing message is flagged when it claims success while the state does not match the target.
- A call made when the target was already unreachable is not flagged, so each failure is blamed on the step that caused it.

Counts: calls 109 flagged of 2390, closing messages 111 flagged of 1434. That is 5.8 percent positives overall, so weight the classes.

## Caveats

Most episode failures on BFCL are omissions: the agent stops before doing a needed call. A step label cannot see an omission until the closing message, which is why the closing message labels matter most. On the 120 val tasks a done check driven by this oracle was the only correction that beat no judge beyond noise (final/final_results.md).
