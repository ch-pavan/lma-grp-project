# Agreement between the two LLM annotators and the replay oracle: Cohen's kappa, Gwet's AC1 and raw agreement,
# for turn ends (done vs not done, and the four typed answers) and for calls (off track vs on track).
# usage: python analysis/agreement.py ANNOT_A.jsonl ANNOT_B.jsonl
import json, sys
from collections import Counter


def jl(p):
    return {r["uid"]: r for r in (json.loads(l) for l in open(p) if l.strip())}


def stats(pairs):
    """pairs of labels (any hashable). Returns n, raw agreement, Cohen's kappa, Gwet's AC1."""
    pairs = [(a, b) for a, b in pairs if a is not None and b is not None]
    n = len(pairs)
    if not n:
        return 0, float("nan"), float("nan"), float("nan")
    cats = sorted({x for p in pairs for x in p}, key=str)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] / n * cb[c] / n for c in cats)
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    q = len(cats)
    pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
    pe_g = sum(p * (1 - p) for p in pi.values()) / (q - 1) if q > 1 else 0
    ac1 = (po - pe_g) / (1 - pe_g) if pe_g < 1 else float("nan")
    return n, po, kappa, ac1


def row(name, pairs):
    n, po, k, ac1 = stats(pairs)
    print(f"  {name:44s} n={n:5d}  agree {100 * po:5.1f}%  kappa {k:5.2f}  AC1 {ac1:5.2f}")


def main():
    A, B = jl(sys.argv[1]), jl(sys.argv[2])
    na, nb = next(iter(A.values()))["model"], next(iter(B.values()))["model"]
    common = sorted(set(A) & set(B))
    print(f"A = {na} ({len(A)} rows), B = {nb} ({len(B)} rows), both: {len(common)}")

    def done(r):
        return None if r.get("answer") is None else int(r["answer"] == "done")

    def off(r):
        return None if r.get("q1") is None else int(r["q1"] == "off_track")

    turns = [u for u in common if A[u]["kind"] == "turn"]
    calls = [u for u in common if A[u]["kind"] == "call"]
    print("Turn ends, done vs not done")
    row("A vs B", [(done(A[u]), done(B[u])) for u in turns])
    row("A vs oracle", [(done(A[u]), A[u]["oracle"]["done"]) for u in turns])
    row("B vs oracle", [(done(B[u]), B[u]["oracle"]["done"]) for u in turns])
    agreed = [u for u in turns if done(A[u]) is not None and done(A[u]) == done(B[u])]
    row("A and B agree, vs oracle", [(done(A[u]), A[u]["oracle"]["done"]) for u in agreed])
    print("Turn ends, four typed answers")
    row("A vs B", [(A[u].get("answer"), B[u].get("answer")) for u in turns])
    for m, R in ((na, A), (nb, B)):
        c = Counter(R[u].get("answer") for u in turns)
        print(f"  {m:20s} answers: " + ", ".join(f"{k} {v}" for k, v in c.most_common()))
    print(f"  oracle: not done {sum(1 - A[u]['oracle']['done'] for u in turns if A[u]['oracle']['done'] is not None)} of {len(turns)}")
    print("Calls, off track vs on track")
    row("A vs B", [(off(A[u]), off(B[u])) for u in calls])
    row("A vs oracle", [(off(A[u]), A[u]["oracle"]["off_track"]) for u in calls])
    row("B vs oracle", [(off(B[u]), B[u]["oracle"]["off_track"]) for u in calls])
    for m, R in ((na, A), (nb, B)):
        fl = sum(off(R[u]) == 1 for u in calls)
        print(f"  {m:20s} flags {fl} of {len(calls)} calls; oracle flags {sum(R[u]['oracle']['off_track'] or 0 for u in calls)}")
    for m, R in ((na, A), (nb, B)):
        rs = list(R.values())
        print(f"  {m:20s} parse failures {sum((r.get('answer') if r['kind'] == 'turn' else r.get('q1')) is None for r in rs)}, "
              f"tokens in {sum(r['in'] for r in rs)} out {sum(r['out'] for r in rs)} cached {sum(r['cached'] for r in rs)}")


if __name__ == "__main__":
    main()
