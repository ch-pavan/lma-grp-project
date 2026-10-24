# Pilot gate: every piloted system must have rows and at most half of them harness errors, else the job stops.
import glob, json, os, sys
d, suf = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""
bad = 0
for f in sorted(glob.glob(os.path.join(d, "*", "*", "tasks*.jsonl"))):
    lab = os.path.basename(os.path.dirname(f))
    if not lab.endswith(suf) or (not suf and "__" in lab):
        continue
    rows = [json.loads(l) for l in open(f) if l.strip()]
    err = [r for r in rows if r.get("harness_error")]
    ok = rows and 2 * len(err) <= len(rows)
    bad += not ok
    print(f"{'ok ' if ok else 'BAD'} {f.split('/')[-3]} {lab}: {len(rows)} rows, {sum(bool(r['passed']) for r in rows)} passed, {len(err)} harness errors",
          (str(err[0].get('harness_error'))[:200] if err else ""), flush=True)
sys.exit(1 if bad else 0)
