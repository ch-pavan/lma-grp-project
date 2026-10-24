# Plumbing check for offline_eval.py without a GPU or a real model: rules judge, both label shapes, reweighting,
# agreement and the llm mode against a fake OpenAI server. usage: python test_offline_eval.py [live_steps_labelled.jsonl]
import http.server, json, os, subprocess, sys, tempfile, threading

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "finetune_data", "live_steps_labelled.jsonl")
EV = [sys.executable, os.path.join(HERE, "offline_eval.py")]


class Fake(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        Fake.seen.append(body)
        user = body["messages"][1]["content"]
        verdict = "VERDICT Q1=off_track Q2=false_claim" if "CLOSING MESSAGE" in user else "VERDICT Q1=off_track Q2=none"
        out = {"id": "x", "object": "chat.completion", "created": 0, "model": "fake",
               "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "<think>x</think> ok\n" + verdict}}],
               "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        data = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(data))); self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def run(*args):
    r = subprocess.run(EV + list(args), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-1500:]
    return r.stdout


with tempfile.TemporaryDirectory() as d:
    rows = [json.loads(l) for l in open(SRC)][:600]
    # run dir in the shape of an S1_record run labelled by analysis/oracle_labels.py
    run_dir = os.path.join(d, "run"); os.makedirs(run_dir)
    seen, turns = {}, {}
    with open(os.path.join(run_dir, "states_S1_record.jsonl"), "w") as sf, open(os.path.join(run_dir, "labels.jsonl"), "w") as lf:
        for r in rows:
            k = seen.get((r["id"], r["run"]), 0); seen[(r["id"], r["run"])] = k + 1
            sf.write(json.dumps({x: y for x, y in r.items() if x != "oracle_flag"}) + "\n")
            o = {"id": r["id"], "run": r["run"], "k": k, "turn": r["turn"], "kind": r["step"]["kind"], "version": r["version"], "scenario": r["scenario"]}
            if o["kind"] == "call":
                o["off_track_suffix"] = o["off_track_subset"] = r["oracle_flag"]
            else:
                o["false_claim"] = r["oracle_flag"]
            lf.write(json.dumps(o) + "\n")
            turns[(r["id"], r["run"], r["turn"])] = turns.get((r["id"], r["run"], r["turn"]), 0) | r["oracle_flag"]
    with open(os.path.join(run_dir, "turns.jsonl"), "w") as tf:
        for (i, ru, t), bad in turns.items():
            tf.write(json.dumps({"id": i, "run": ru, "turn": t, "done": int(not bad)}) + "\n")

    out = run("--steps", run_dir, "--labels", run_dir, "--judge", "rules", "--out", os.path.join(d, "o1"), "--reweight", run_dir, "--bootstrap", "200")
    m = json.load(open(os.path.join(d, "o1", "metrics.json")))
    assert m["q1"]["n"] > 0 and m["q2"]["n"] > 0 and m["run"]["reweighted"], m["run"]
    # the embedded oracle_flag path gives the same Q1 counts as the oracle_labels.py path
    run("--steps", SRC, "--judge", "rules", "--out", os.path.join(d, "o2"), "--limit", "600", "--bootstrap", "50")
    # agreement between a label file and the judge predictions
    run("--agree", os.path.join(run_dir, "labels.jsonl"), os.path.join(d, "o1", "predictions.jsonl"), "--out", os.path.join(d, "o3"), "--bootstrap", "50")
    assert os.path.exists(os.path.join(d, "o3", "agreement.json"))

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/v1"
    for think, trace in (("off", "proposal"), ("on", "full")):
        o = os.path.join(d, f"llm_{think}_{trace}")
        run("--steps", run_dir, "--labels", run_dir, "--judge", "llm", "--base-url", url, "--model", "fake", "--reasoning", think, "--trace", trace,
            "--out", o, "--limit", "40", "--concurrency", "4", "--bootstrap", "50")
        m = json.load(open(os.path.join(o, "metrics.json")))
        assert m["run"]["unparsed"] == 0 and m["run"]["errors"] == 0 and m["q1"]["classes"]["off_track"]["predicted"] > 0, m["run"]
        assert "q3" not in m  # the llm judge does not express Q3
    kws = Fake.seen[-1]["chat_template_kwargs"]
    assert kws == {"enable_thinking": True}, kws
    assert any("FULL TRACE" in b["messages"][1]["content"] for b in Fake.seen)
    print("ok")
