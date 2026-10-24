# One line per system in a pilot folder: pass rate, steps, blocks and forced quits per task.
import glob, json, os, sys
for d in sorted(glob.glob(os.path.join(sys.argv[1], "*"))):
    rs = [json.loads(l) for f in glob.glob(d + "/tasks_*.jsonl") for l in open(f)]
    if rs:
        n = len(rs); p = sum(r["passed"] for r in rs)
        print(f"PILOT {os.path.basename(d)}: {p}/{n} passed ({100 * p / n:.1f}%), steps/task {sum(r['steps'] for r in rs) / n:.1f}, "
              f"blocks/task {sum(r['interventions'] for r in rs) / n:.2f}, forced {sum(r['error_type'] == 'harness:forced_quit' for r in rs)}")
