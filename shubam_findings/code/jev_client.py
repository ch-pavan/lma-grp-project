# Hosted Jev (classifier.dev POST /v1/systemone, free tier, share_data false) on the same judge states and
# question wordings as the laya sweep. Output rows match laya_sweep.py, feature keys "jev:fmt|qid". Resumable.
# usage: python jev_client.py OUT.jsonl STATES.jsonl [...]   (env: LIMIT_GOLD, QMAX = daily question budget)
import json, os, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
import laya_variants as LV

URL = "https://classifier.dev/v1/systemone"
FMT = "step_first"
QIDS = {"call": ["q_proceed", "q_wrong", "q2_noul"], "msg": ["q2_orig", "q_wrong", "q2_noul"]}
out, srcs = sys.argv[1], sys.argv[2:]
QMAX = int(os.environ.get("QMAX", "15000"))

recs = []
for p in srcs:
    rows = [json.loads(l) for l in open(p)]
    src = os.path.basename(p)
    seen = {}
    for r in rows:
        r["k"] = seen.get((r["id"], r["run"]), 0); seen[(r["id"], r["run"])] = r["k"] + 1
        r["src"] = src
    lim = int(os.environ.get("LIMIT_GOLD", "0"))
    if "gold" in src and lim:
        rows = rows[::max(1, len(rows) // lim)][:lim]
    recs += rows
# gate first (gold, then val scenarios), then train: a quota stop still leaves the gate and val numbers
VAL = {int(x) for x in os.environ.get("VAL", "").split(",") if x}
recs.sort(key=lambda r: (not r["src"].startswith("gold"), r["scenario"] not in VAL))
done = set()
if os.path.exists(out):
    done = {(d["src"], d["id"], d["run"], d["k"]) for d in map(json.loads, open(out))}
recs = [r for r in recs if (r["src"], r["id"], r["run"], r["k"]) not in done]
print(len(recs), "states to do,", len(done), "done", flush=True)


def ask(r):
    kind = r["step"]["kind"]
    qs = {q: LV.QUESTIONS[q][kind] for q in QIDS[kind]}
    body = json.dumps({"share_data": False, "state": LV.FORMATS[FMT](r), "questions": qs}).encode()
    for attempt in range(5):
        req = urllib.request.Request(URL, data=body, headers={"content-type": "application/json", "X-Classifier-Share-Data": "false",
                                                             "Authorization": "Bearer unused"})
        t = time.time()
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                js = json.loads(resp.read())
            ms = (time.time() - t) * 1000
            f = {f"jev:{FMT}|{q}": LV.p_flag(js["answers"][q], LV.QUESTIONS[q]["flag"]) for q in qs}
            return {"f": f, "ms": round(ms), "tok": js.get("usage", {}).get("input_tokens")}, None
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode(errors="replace")
            if e.code == 429:
                time.sleep(min(60, float(e.headers.get("Retry-After") or 5 * (attempt + 1))))
                continue
            return None, f"HTTP {e.code} {msg}"
        except Exception as e:
            time.sleep(3 * (attempt + 1))
            err = f"{type(e).__name__}: {e}"
    return None, "retries exhausted " + locals().get("err", "429")


asked = 0
stop = None
with open(out, "a") as f, ThreadPoolExecutor(4) as ex:  # the free tier runs at most four requests at once per IP
    for s in range(0, len(recs), 40):
        part = recs[s:s + 40]
        if asked + 3 * len(part) > QMAX:
            stop = f"daily question budget {QMAX} reached"
            break
        for r, (res, err) in zip(part, ex.map(ask, part)):
            asked += 3
            if err:
                stop = stop or err
                continue
            keep = {k: r[k] for k in ("src", "id", "run", "k", "version", "scenario", "turn", "gold_turn", "n_recent")}
            keep["step"] = {k: r["step"].get(k) for k in ("kind", "name", "args", "text")}
            f.write(json.dumps({**keep, **res}, default=str) + "\n")
        f.flush()
        if stop and ("HTTP 4" in stop and "429" not in stop):
            break
        print(f"{s + len(part)}/{len(recs)} asked {asked}", flush=True)
print("JEV DONE" if not stop else "JEV STOPPED: " + stop, flush=True)
