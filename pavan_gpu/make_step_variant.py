#!/usr/bin/env python3
"""Plan item 3.7: a copy of the step-check data in which a call counts as bad WITHOUT the oracle "breaks_task" rule.

The current step head (job 49656) counts a call as bad when breaks_task OR unneeded_irreversible OR (made_up_value on an
irreversible call). breaks_task is the replay oracle's off-track label, which agrees poorly with the LLM annotators
(kappa 0.04 to 0.15) and fails the proposal's 80% rule. This variant keeps the other two rules only, so we can see how
much the step head depends on it.

CPU only, seconds. Reads train/dev/val.jsonl (or .jsonl.gz) of the current step data, writes the same rows with a new
"label" (the old one is kept as "label_with_breaks_task").

    python pavan_gpu/make_step_variant.py IN_DIR OUT_DIR
    e.g. python pavan_gpu/make_step_variant.py $H/data/laya_step $H/data/laya_step_nobt
"""
import gzip
import json
import os
import sys

# Same set as IRREVERSIBLE in shuban_findings/code/run.py (checked below when that file is importable).
IRREVERSIBLE = set("rm rmdir echo mv cp send_message delete_message post_tweet retweet comment mention create_ticket "
                   "close_ticket resolve_ticket edit_ticket place_order cancel_order withdraw_funds fund_account "
                   "book_flight cancel_booking purchase_insurance register_credit_card fillFuelTank".split())


def check_list():
    here = os.path.dirname(os.path.abspath(__file__))
    for code in (os.environ.get("STAY_CODE", ""), os.path.join(here, "..", "shuban_findings", "code"), os.path.join(here, "..", "code")):
        if code and os.path.exists(os.path.join(code, "run.py")):
            sys.path.insert(0, code)
            try:
                import run
            except Exception as e:  # the harness may need packages this machine lacks; the copied list is then used
                print(f"note: could not import run.py ({e}); using the copied list")
                return
            if set(run.IRREVERSIBLE) != IRREVERSIBLE:
                sys.exit("IRREVERSIBLE differs from run.py: update this script")
            print("irreversible list matches run.py")
            return


def read(path):
    if not os.path.exists(path) and os.path.exists(path + ".gz"):
        path += ".gz"
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        return [json.loads(l) for l in f if l.strip()]


def name(text):
    return text.split("Proposed tool call: ", 1)[1].split("(", 1)[0]


def main():
    src, dst = sys.argv[1:3]
    check_list()
    os.makedirs(dst, exist_ok=True)
    for split in ("train", "dev", "val"):
        rows = read(os.path.join(src, f"{split}.jsonl"))
        bad_old = bad_new = 0
        with open(os.path.join(dst, f"{split}.jsonl"), "w") as f:
            for r in rows:
                irr = name(r["text"]) in IRREVERSIBLE
                bad = bool(r["unneeded_irreversible"] or (r["made_up_value"] and irr))
                bad_old += 1 - r["label"]
                bad_new += bad
                f.write(json.dumps({**r, "label_with_breaks_task": r["label"], "label": int(not bad)}) + "\n")
        print(f"{split}: {len(rows)} calls, bad {bad_old} with breaks_task -> {bad_new} without")


if __name__ == "__main__":
    main()
