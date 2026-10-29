# Human check of the LLM labels (proposal, "Test labels"): a stratified sample of steps, half flagged by the LLM
# annotators and half not, rendered for people to label blind. Shows each step exactly as the annotators saw it
# (annotate.py items, guide v2), as readable Markdown instead of JSON.
#   flagged call: DeepSeek or GLM said Q1 off_track or Q2 made_up_value/false_claim
#   flagged turn end: DeepSeek or GLM gave any answer other than done
# Steps either annotator failed to answer are left out. Same seed, same sample.
# usage: python human_check/build_sample.py RUN_DIR OUT_DIR [--per-cell 25] [--seed 0] [--exclude OTHER_OUT_DIR ...]
import argparse, csv, json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "analysis"))
import annotate as A  # noqa: E402

FLAG_Q2 = {"made_up_value", "false_claim"}


def flagged(kind, *rows):
    if kind == "call":
        return any(r["q1"] == "off_track" or r["q2"] in FLAG_Q2 for r in rows)
    return any(r["answer"] != "done" for r in rows)


def answered(kind, r):
    return r is not None and (r.get("q1") if kind == "call" else r.get("answer")) is not None


def render(n, item):
    u = json.loads(item["user"])
    out = []
    if item["kind"] == "call":
        out.append(f"## {n} · Tool call: answer Q1 and Q2\n")
    else:
        out.append(f"## {n} · End of turn: pick one answer\n")
    out.append("**User requests** (earlier ones are context; judge only the latest):\n")
    reqs = u["requests"]
    for i, r in enumerate(reqs, 1):
        tag = " ← latest" if i == len(reqs) else ""
        out.append(f"{i}. {r.strip()}{tag}")
    out.append("")
    if item["kind"] == "call":
        if u.get("plan"):
            out.append("**Turn plan** (written by the agent's planner):\n")
            out.append("```text\n" + u["plan"].strip() + "\n```\n")
        out.append("**Last calls in this turn, oldest first** (outputs may be cut short):\n")
        if u.get("recent"):
            for c, o in u["recent"]:
                out.append(f"- `{c}`\n  → `{str(o)}`")
        else:
            out.append("- (none yet)")
        out.append("")
        st = u["step"]
        out.append("**Proposed step** (not run yet):\n")
        out.append("```python\n" + st["text"] + "\n```\n")
        out.append("**Where each argument value appears:**\n")
        if st.get("ev"):
            for name, val, src in st["ev"]:
                out.append(f"- `{name}` = `{val!r}`: {src}")
        else:
            out.append("- (no arguments)")
    else:
        out.append("**Calls the agent ran for the latest request** (outputs may be cut short):\n")
        if u["calls_for_latest_request"]:
            for c in u["calls_for_latest_request"]:
                out.append(f"- `{c['call']}`\n  → `{str(c['output'])}`")
        else:
            out.append("- (no calls)")
        out.append("\n**Agent's closing message:**\n")
        out.append("\n".join("> " + line for line in u["closing_message"].strip().splitlines() or [""]))
    out.append("\n---\n")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir"); ap.add_argument("out_dir")
    ap.add_argument("--per-cell", type=int, default=25, help="steps per cell: call/turn x flagged/not")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--exclude", nargs="*", default=[], help="earlier sample folders whose steps are not reused")
    a = ap.parse_args()

    ds = {r["uid"]: r for r in A.jl(os.path.join(a.run_dir, "annot_v2_deepseek.jsonl"))}
    gl = {r["uid"]: r for r in A.jl(os.path.join(a.run_dir, "annot_v2_glm.jsonl"))}
    used = set()
    for d in a.exclude:
        used |= {v["uid"] for v in json.load(open(os.path.join(d, "key.json"))).values()}
    cells = {}
    for it in A.items(a.run_dir, "turns,calls", "v2"):
        r1, r2 = ds.get(it["uid"]), gl.get(it["uid"])
        if it["uid"] in used or not (answered(it["kind"], r1) and answered(it["kind"], r2)):
            continue
        cells.setdefault((it["kind"], flagged(it["kind"], r1, r2)), []).append(it)

    rng = random.Random(a.seed)
    picked = []
    for key in sorted(cells):
        pool = sorted(cells[key], key=lambda x: x["uid"])
        if len(pool) < a.per_cell:
            sys.exit(f"cell {key} has only {len(pool)} steps")
        picked += [(key, x) for x in rng.sample(pool, a.per_cell)]
    rng.shuffle(picked)

    os.makedirs(a.out_dir, exist_ok=True)
    key, md = {}, ["# Steps to label\n", "Label every step with `GUIDE.md` open. Write your answers in your own copy of "
                   "`sheet_template.csv`, not here. Do not open `key.json`.\n", "---\n"]
    with open(os.path.join(a.out_dir, "sheet_template.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "kind", "q1", "q2", "answer", "note"])
        for i, ((kind, fl), it) in enumerate(picked, 1):
            hid = f"H{i:03d}"
            key[hid] = {"uid": it["uid"], "kind": kind, "flagged": fl}
            md.append(render(hid, it))
            w.writerow([hid, kind, "", "", "", ""])
    open(os.path.join(a.out_dir, "items.md"), "w").write("\n".join(md))
    json.dump(key, open(os.path.join(a.out_dir, "key.json"), "w"), indent=1)
    # pool size of each cell, so score.py can reweight the half flagged sample back to the real mix of steps
    pools = {f"{k[0]}|{int(k[1])}": len(v) for k, v in cells.items()}
    json.dump({"run_dir": os.path.relpath(a.run_dir, ROOT), "seed": a.seed, "per_cell": a.per_cell, "pools": pools},
              open(os.path.join(a.out_dir, "sample.json"), "w"), indent=1)
    print(f"{len(picked)} steps -> {a.out_dir}: " + ", ".join(f"{k[0]} {'flagged' if k[1] else 'not flagged'} {len(v)} in pool"
                                                     for k, v in sorted(cells.items())))


if __name__ == "__main__":
    main()
