# Hosted Jev (classifier.dev, free tier, share_data false) as an online step judge. Config is one part of
# laya_table.py's configs.json for the jev features: {"call": part or null, "msg": part or null}.
import asyncio, json, math, time, urllib.error, urllib.request
import laya_variants as LV

URL = "https://classifier.dev/v1/systemone"


def ask(state, qs):
    body = json.dumps({"share_data": False, "state": state, "questions": qs}).encode()
    for attempt in range(5):
        req = urllib.request.Request(URL, data=body, headers={"content-type": "application/json", "X-Classifier-Share-Data": "false",
                                                             "Authorization": "Bearer unused"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())["answers"]
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(min(60, float(e.headers.get("Retry-After") or 5 * (attempt + 1))))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("classifier.dev retries exhausted")


class JevJudge:
    name = "S_jev"

    def __init__(self, cfg):
        self.cfg = cfg
        self.sem = asyncio.Semaphore(4)  # free tier: at most four requests at once per IP
        self.errors = 0

    async def judge(self, ctx, step):
        out = {"q1": "on_track", "q2": "none", "q3": "needed", "jin": 0, "jout": 0}
        part = self.cfg.get(step["kind"])
        if not part:
            return out
        rec = {"requests": ctx["requests"], "plan": ctx["plan"], "recent": ctx["recent"], "step": step}
        pairs = [k[4:].split("|") for k in part["feats"]]  # "jev:fmt|qid"
        z = part["b"]
        try:
            async with self.sem:
                for fmt in sorted({f for f, _ in pairs}):
                    qids = [q for f, q in pairs if f == fmt]
                    ans = await asyncio.to_thread(ask, LV.FORMATS[fmt](rec), {q: LV.QUESTIONS[q][step["kind"]] for q in qids})
                    for q in qids:
                        z += part["w"][part["feats"].index(f"jev:{fmt}|{q}")] * LV.logit(LV.p_flag(ans[q], LV.QUESTIONS[q]["flag"]))
        except Exception:
            self.errors += 1  # a failed call lets the step through, like no judge
            return out
        out["score"] = round(z, 3)
        if z > part["t"]:
            out["q1" if step["kind"] == "call" else "q2"] = "off_track" if step["kind"] == "call" else "false_claim"
        return out
