# Agreement between the two LLM annotators (DeepSeek V4.1 Flash, GLM-5.3-Flash, guide v3) on the 7,214 labelled test
# steps: raw agreement and Cohen's kappa for Q1 on tool calls, the typed answer on closing messages, the three scored
# classes (done / off track / false claim) and false claim alone. Standard library only.
# usage (repo root, after merging pavan/test-results): python final_report/scripts/test_agreement.py runs/raw/test9b_labels
import collections, gzip, json, os, sys


def rows(path):
    return {r["uid"]: r for r in (json.loads(l) for l in gzip.open(path, "rt") if l.strip())}


def kappa(pairs):
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = collections.Counter(a for a, _ in pairs), collections.Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / n / n
    return po, (po - pe) / (1 - pe)


def main():
    d = sys.argv[1] if len(sys.argv) > 1 else "runs/raw/test9b_labels"
    a, b = rows(os.path.join(d, "annot_v3_deepseek.jsonl.gz")), rows(os.path.join(d, "annot_v3_glm.jsonl.gz"))
    lab = lambda r: r.get("q1") if r["kind"] == "call" else r.get("answer")
    three = lambda x: "false_claim" if x == "unsupported_claim" else ("done" if x == "done" else "off_track")
    for kind in ("call", "turn"):
        ks = [u for u in a if u in b and a[u]["kind"] == kind and lab(a[u]) and lab(b[u])]
        pairs = [(lab(a[u]), lab(b[u])) for u in ks]
        print(f"{kind}: {len(ks)} steps, agreement {kappa(pairs)[0]:.3f}, kappa {kappa(pairs)[1]:.3f}")
        if kind == "turn":
            print("  three classes: agreement %.3f, kappa %.3f" % kappa([(three(x), three(y)) for x, y in pairs]))
            print("  false claim:   agreement %.3f, kappa %.3f" % kappa([(x == "unsupported_claim", y == "unsupported_claim") for x, y in pairs]))


if __name__ == "__main__":
    main()
