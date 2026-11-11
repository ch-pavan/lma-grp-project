# Before resuming an interrupted actions.py run: drop the rows of episodes that never finished. The recorder writes
# states_*.jsonl step by step, so an episode cut by an interruption leaves partial rows; on resume it is run again from
# the start and would append a second copy, which shifts the step index k used by every label file.
# An episode counts as finished only when its tasks_*.jsonl row exists. Keeps the first steps_* row per finished episode.
# usage: python clean_partial.py RUN_DIR
import glob, json, os, sys

d = sys.argv[1]
done = set()
for f in glob.glob(os.path.join(d, "tasks_*.jsonl")):
    for l in open(f):
        if l.strip():
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue  # a line cut by the interruption
            done.add((r["id"], r["run"]))
for pat in ("states_*.jsonl", "steps_*.jsonl"):
    for f in glob.glob(os.path.join(d, pat)):
        kept, dropped, seen = [], 0, set()
        for l in open(f):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                dropped += 1; continue
            key = (r["id"], r["run"])
            if key not in done or (pat.startswith("steps") and key in seen):
                dropped += 1; continue
            seen.add(key); kept.append(l if l.endswith("\n") else l + "\n")
        if dropped:
            tmp = f + ".tmp"
            open(tmp, "w").writelines(kept); os.replace(tmp, f)
        print(f"{os.path.basename(f)}: kept {len(kept)}, dropped {dropped}")
# tasks files: drop a cut last line so json readers do not fail
for f in glob.glob(os.path.join(d, "tasks_*.jsonl")):
    lines = open(f).readlines()
    keep = []
    for l in lines:
        try:
            json.loads(l); keep.append(l if l.endswith("\n") else l + "\n")
        except json.JSONDecodeError:
            pass
    if len(keep) != len(lines):
        open(f, "w").writelines(keep)
    print(f"{os.path.basename(f)}: {len(keep)} finished episodes")
