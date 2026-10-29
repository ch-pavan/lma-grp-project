# Score the human check: labeller vs labeller, then the human consensus vs each LLM annotator, with the proposal's
# decision rule (kappa 0.7 bar; below 0.6 rewrite the guide, 0.6 to 0.8 label more steps, 0.8 or more stop at 200).
#   1st run (two labels_<name>.csv in the folder): checks the sheets, prints human vs human and writes decisions.csv
#     with every step the two labellers answered differently, for the referee to fill.
#   2nd run (decisions.csv filled): builds the consensus and writes results.md and consensus.csv.
# The sample is half flagged by the LLMs (build_sample.py), which packs in the steps where DeepSeek and GLM disagree,
# so kappa on the sample alone is biased low. Every measure is also reweighted to the real mix of steps (the pool size
# of each cell over the steps drawn from it), as the proposal does for test F1; the decision uses the reweighted kappa.
# Standard library only; reads the LLM labels from runs/data (.jsonl or .jsonl.gz).
# usage: python human_check/score.py human_check/pilot
import argparse, csv, glob, gzip, json, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VALUES = {"call": {"q1": {"on_track", "off_track"}, "q2": {"none", "made_up_value"}},
          "turn": {"answer": {"done", "missing_action", "should_ask_user", "unsupported_claim"}}}
LLMS = {"DeepSeek": "annot_v2_deepseek.jsonl", "GLM": "annot_v2_glm.jsonl"}


def read_jsonl(path):
    if not os.path.exists(path) and os.path.exists(path + ".gz"):
        path += ".gz"
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        return {r["uid"]: r for r in (json.loads(l) for l in f if l.strip())}


def read_sheet(path, key, need_all=True):
    rows, bad = {}, []
    for r in csv.DictReader(open(path, newline="", encoding="utf-8-sig")):
        hid = (r.get("id") or "").strip()
        if hid not in key:
            continue
        kind = key[hid]["kind"]
        ans = {c: (r.get(c) or "").strip().lower() for c in VALUES[kind]}
        if any(v not in VALUES[kind][c] for c, v in ans.items()):
            bad.append(f"{hid} ({kind}): {ans}")
            continue
        rows[hid] = ans
    missing = sorted(set(key) - set(rows)) if need_all else []
    return rows, bad, missing


def wstats(pairs, weights):
    """Raw agreement, Cohen's kappa and Gwet's AC1, each pair counted with its weight (all 1 = the plain sample)."""
    tot = sum(weights)
    cats = sorted({x for p in pairs for x in p}, key=str)
    if not pairs or len(cats) < 2:
        return float("nan"), float("nan"), float("nan")
    po = sum(w for (a, b), w in zip(pairs, weights) if a == b) / tot
    ca, cb = defaultdict(float), defaultdict(float)
    for (a, b), w in zip(pairs, weights):
        ca[a] += w / tot
        cb[b] += w / tot
    pe = sum(ca[c] * cb[c] for c in cats)
    pe_g = sum(((ca[c] + cb[c]) / 2) * (1 - (ca[c] + cb[c]) / 2) for c in cats) / (len(cats) - 1)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan"), (po - pe_g) / (1 - pe_g) if pe_g < 1 else float("nan")


def flag(kind, a):
    return int(a["q1"] == "off_track" or a["q2"] != "none") if kind == "call" else int(a["answer"] != "done")


def comparisons(key, A, B):
    """(name, step ids, pairs) for every measure."""
    ids = [h for h in key if h in A and h in B]
    calls = [h for h in ids if key[h]["kind"] == "call"]
    turns = [h for h in ids if key[h]["kind"] == "turn"]
    return [
        ("all steps: problem vs fine (headline)", ids, [(flag(key[h]["kind"], A[h]), flag(key[h]["kind"], B[h])) for h in ids]),
        ("calls: off track vs on track", calls, [(A[h]["q1"], B[h]["q1"]) for h in calls]),
        ("calls: made up value vs none", calls, [(A[h]["q2"] != "none", B[h]["q2"] != "none") for h in calls]),
        ("turn ends: done vs not done", turns, [(A[h]["answer"] == "done", B[h]["answer"] == "done") for h in turns]),
        ("turn ends: four answers", turns, [(A[h]["answer"], B[h]["answer"]) for h in turns]),
        ("turn ends: false claim vs not", turns, [(A[h]["answer"] == "unsupported_claim", B[h]["answer"] == "unsupported_claim")
                                                  for h in turns]),
    ]


def table(title, key, weight, A, B):
    lines = [f"### {title}", "", "| Measure | n | Agree | Kappa (sample) | AC1 (sample) | Agree, reweighted | Kappa, reweighted |",
             "|---|---|---|---|---|---|---|"]
    head = None
    for name, ids, pairs in comparisons(key, A, B):
        po, k, ac1 = wstats(pairs, [1] * len(pairs))
        rpo, rk, _ = wstats(pairs, [weight[h] for h in ids])
        head = rk if head is None else head
        lines.append(f"| {name} | {len(pairs)} | {100 * po:.0f}% | {k:.2f} | {ac1:.2f} | {100 * rpo:.0f}% | {rk:.2f} |")
    return "\n".join(lines) + "\n", head


def llm_answers(run_dir, key):
    out = {}
    for name, fn in LLMS.items():
        R = read_jsonl(os.path.join(run_dir, fn))
        ans = {}
        for h, v in key.items():
            r = R[v["uid"]]
            if v["kind"] == "call":
                q2 = r["q2"] if r["q2"] in ("none", "made_up_value") else "made_up_value"  # false_claim on a call counts as a flag
                ans[h] = {"q1": r["q1"], "q2": q2}
            else:
                ans[h] = {"answer": r["answer"]}
        out[name] = ans
    return out


def verdict(k):
    if k < 0.6:
        return "below 0.6: rewrite the guide and relabel (proposal)"
    if k < 0.8:
        return ("0.6 to 0.8: label more steps until the result is clear (proposal)"
                + ("; passes the 0.7 bar so far" if k >= 0.7 else "; under the 0.7 bar so far"))
    return "0.8 or more: passes; stop at 200 steps (proposal)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--run-dir", help="where the LLM labels are (default: from sample.json)")
    a = ap.parse_args()
    key = json.load(open(os.path.join(a.folder, "key.json")))
    meta = json.load(open(os.path.join(a.folder, "sample.json")))
    run_dir = a.run_dir or os.path.join(ROOT, meta["run_dir"])
    drawn = defaultdict(int)
    for v in key.values():
        drawn[f"{v['kind']}|{int(v['flagged'])}"] += 1
    weight = {h: meta["pools"][f"{v['kind']}|{int(v['flagged'])}"] / drawn[f"{v['kind']}|{int(v['flagged'])}"]
              for h, v in key.items()}

    sheets = sorted(glob.glob(os.path.join(a.folder, "labels_*.csv")))
    if len(sheets) != 2:
        sys.exit(f"need exactly two labels_<name>.csv files in {a.folder}, found {len(sheets)}: {sheets}")
    names = [os.path.basename(p)[7:-4] for p in sheets]
    (A, bad_a, miss_a), (B, bad_b, miss_b) = (read_sheet(p, key) for p in sheets)
    ok = True
    for n, bad, miss in ((names[0], bad_a, miss_a), (names[1], bad_b, miss_b)):
        if bad:
            ok = False
            print(f"{n}: {len(bad)} rows with values not in GUIDE.md, fix them:\n  " + "\n  ".join(bad[:20]))
        if miss:
            ok = False
            print(f"{n}: {len(miss)} steps not answered yet: {', '.join(miss[:20])}{' ...' if len(miss) > 20 else ''}")
    if not ok:
        sys.exit("fix the sheets above and run again")

    report = [f"# Human check results: `{a.folder}`", "",
              f"{len(key)} steps, labellers {names[0]} and {names[1]}. Sample: half flagged by the LLMs; "
              f"'reweighted' columns scale each cell back to its share of all {sum(meta['pools'].values())} steps.", ""]
    t, k_hh = table(f"{names[0]} vs {names[1]} (human vs human)", key, weight, A, B)
    report.append(t)
    print(t)

    diff = [h for h in key if A[h] != B[h]]
    dec_path = os.path.join(a.folder, "decisions.csv")
    if not os.path.exists(dec_path):
        with open(dec_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["id", "kind", "q1", "q2", "answer", "note", names[0], names[1]])
            for h in diff:
                w.writerow([h, key[h]["kind"], "", "", "", "", json.dumps(A[h]), json.dumps(B[h])])
        sys.exit(f"{len(diff)} steps where the labellers differ -> {dec_path}. "
                 "The referee fills q1/q2 or answer for each row, then run this again.")
    D, bad_d, _ = read_sheet(dec_path, key, need_all=False)
    miss_d = [h for h in diff if h not in D]
    if bad_d or miss_d:
        sys.exit(f"decisions.csv: {len(miss_d)} disagreements not decided yet ({', '.join(miss_d[:20])}), "
                 f"{len(bad_d)} rows with values not in GUIDE.md {bad_d[:5]}")
    consensus = {h: (A[h] if A[h] == B[h] else D[h]) for h in key}

    L = llm_answers(run_dir, key)
    heads = {}
    for name, ans in L.items():
        t, heads[name] = table(f"Human consensus vs {name}", key, weight, consensus, ans)
        report.append(t)
        print(t)
    t, k_ll = table("DeepSeek vs GLM on the same steps (for reference)", key, weight, L["DeepSeek"], L["GLM"])
    report.append(t)
    print(t)
    worst = min(heads.values())
    report += ["## Decision", "",
               f"Headline kappa, reweighted (all steps, problem vs fine): human vs human {k_hh:.2f}; consensus vs DeepSeek "
               f"{heads['DeepSeek']:.2f}, vs GLM {heads['GLM']:.2f}; DeepSeek vs GLM {k_ll:.2f}.", "",
               f"Lower of the two consensus-vs-LLM kappas: **{worst:.2f}**, so **{verdict(worst)}**.", "",
               "Per-class rows rest on 25 to 50 steps and are noisy; the headline row decides.", ""]
    open(os.path.join(a.folder, "results.md"), "w").write("\n".join(report))
    with open(os.path.join(a.folder, "consensus.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "uid", "kind", "q1", "q2", "answer"])
        for h in key:
            c = consensus[h]
            w.writerow([h, key[h]["uid"], key[h]["kind"], c.get("q1", ""), c.get("q2", ""), c.get("answer", "")])
    print(f"Decision: lower consensus-vs-LLM kappa (reweighted) {worst:.2f} -> {verdict(worst)}\n"
          f"wrote {os.path.join(a.folder, 'results.md')} and consensus.csv")


if __name__ == "__main__":
    main()
