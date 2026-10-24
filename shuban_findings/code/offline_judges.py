# Offline judge runner for recorded BFCL agent episodes
import argparse, ast, json, os, sys, time, glob
import numpy as np

# Ensure Hugging Face cache stays on the storage disk
if "HF_HOME" not in os.environ:
    os.environ["HF_HOME"] = "/home/orbi8r/storage/.agentwork/tmp/lma-hf"

# Add local directories and kev repository path
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

KEV_PATH = os.environ.get("KEV_DIR", "/home/orbi8r/storage/.agentwork/tmp/kev")
if os.path.isdir(KEV_PATH) and KEV_PATH not in sys.path:
    sys.path.insert(0, KEV_PATH)

import prompts as P
import run
from judges_small import Q1, Q2_CALL, Q2_MSG


def parse_call_args(call_str):
    # Parse tool call string into an arguments dictionary
    try:
        tree = ast.parse(call_str, mode="eval")
        call = tree.body
        args = {}
        for i, a in enumerate(call.args):
            try:
                val = ast.literal_eval(a)
                if isinstance(val, dict):
                    args.update(val)
                else:
                    args[f"arg_{i}"] = val
            except Exception:
                pass
        for kw in call.keywords:
            try:
                args[kw.arg] = ast.literal_eval(kw.value)
            except Exception:
                pass
        return args
    except Exception:
        return {}


def get_arg_keys_vals(args):
    # Extract flattened non trivial values to match evidence generation
    items = []
    for k, v in (args or {}).items():
        for val in P.flat_values(v):
            s = P.norm(val)
            if not s or s in {".", "..", "/", "~"}:
                continue
            items.append((k, str(val)[:60]))
    return items


def rebuild_evidence(call_str, recorded_ev):
    # Align parsed call argument values with recorded evidence locations
    args = parse_call_args(call_str)
    items = get_arg_keys_vals(args)
    ev_rec = recorded_ev or []
    evidence = [(k, v, w) for (k, v), w in zip(items, ev_rec)]
    if len(items) > len(ev_rec):
        evidence += [(k, v, "nowhere") for k, v in items[len(ev_rec):]]
    elif len(ev_rec) > len(items):
        evidence += [("arg", "", w) for w in ev_rec[len(items):]]
    return evidence


class KevJudge:
    # Typed decision judge using Kev 0.8B
    def __init__(self, device):
        import torch
        from kev.checkpoint import Checkpoint, LoadOptions
        self.device = device
        self.ck = Checkpoint("jaredpalmer/kev-0.8b")
        dtype = torch.float16 if str(device).startswith("cuda") else torch.float32
        opts = LoadOptions(dtype=dtype, merge=True)
        self.tok, self.model = self.ck.load(device, opts)

    def judge(self, state, step_kind):
        # Query Kev with Q1 and Q2 typed questions
        from kev.api import Choice, SystemOneRequest, to_answers, to_record
        q1_spec = Q1
        q2_spec = Q2_CALL if step_kind == "call" else Q2_MSG
        req = SystemOneRequest(
            state=state,
            questions={
                "q1": Choice(type="choice", instructions=q1_spec["instructions"], criteria=q1_spec["criteria"]),
                "q2": Choice(type="choice", instructions=q2_spec["instructions"], criteria=q2_spec["criteria"]),
            }
        )
        rec, meta = to_record(req)
        enc = self.model.encode(self.tok, rec)
        probs = self.model.probs(enc)
        ans = to_answers([[float(x) for x in p] for p in probs], meta)

        q1_choice = ans["q1"]["choice"]
        q1_probs = ans["q1"]["probabilities"]
        q1_prob = q1_probs.get(q1_choice, 0.0)
        p_off_track = q1_probs.get("off_track", 0.0)

        q2_choice = ans["q2"]["choice"]
        q2_probs = ans["q2"]["probabilities"]
        q2_prob = q2_probs.get(q2_choice, 0.0)
        p_hallucinated = 1.0 - q2_probs.get("none", 0.0)

        flagged = bool(q1_choice == "off_track" or q2_choice != "none")
        flag_prob = round(float(max(p_off_track, p_hallucinated)), 4)
        return {
            "q1": q1_choice,
            "q1_prob": round(float(q1_prob), 4),
            "q2": q2_choice,
            "q2_prob": round(float(q2_prob), 4),
            "flagged": flagged,
            "flag_prob": flag_prob,
        }


class LettuceJudge:
    # Span level detector for closing messages using LettuceDetect v2
    def __init__(self, device):
        from lettucedetect.models.inference import HallucinationDetector
        self.detector = HallucinationDetector(method="transformer", model_path="KRLabsOrg/lettucedect-v2-mmbert-base")

    def judge(self, turn_calls, message_text, latest_request):
        # Detect unsupported claims in closing message given turn tool outputs
        outs = [str(o)[:300] for c, o in turn_calls]
        if not outs:
            outs = ["(none)"]
        spans = self.detector.predict(context=outs, answer=message_text, question=latest_request, output_format="spans")
        flagged = len(spans) > 0
        max_conf = round(float(max((s.get("confidence", 1.0) for s in spans), default=0.0)), 4) if flagged else 0.0
        return {
            "flagged": flagged,
            "confidence": max_conf,
            "flag_prob": max_conf,
            "spans": spans,
            "q2": "false_claim" if flagged else "none",
        }


def compute_auroc(y_true, y_scores):
    # Calculate ROC AUC score when both positive and negative samples exist
    from sklearn.metrics import roc_auc_score
    if len(set(y_true)) < 2:
        return None
    try:
        return round(float(roc_auc_score(y_true, y_scores)), 4)
    except Exception:
        return None


def find_files(results_dir, system, prefix):
    # Locate jsonl result files supporting both flat and nested folder layouts
    patterns = [
        os.path.join(results_dir, system, f"{prefix}_{system}_*.jsonl"),
        os.path.join(results_dir, f"{prefix}_{system}_*.jsonl"),
    ]
    matches = []
    for p in patterns:
        matches.extend(glob.glob(p))
    return sorted(set(matches))


def run_offline(results_dir, systems, judges_list, limit_episodes, device, out_dir):
    # Main offline evaluation loop across systems and judges
    os.makedirs(out_dir, exist_ok=True)
    version_cache = {}

    def get_dataset_entry(test_id):
        ver = test_id.removeprefix("multi_turn_").rsplit("_", 1)[0]
        if ver not in version_cache:
            version_cache[ver] = {item["id"]: item for item in run.load_version(ver)}
        return version_cache[ver].get(test_id)

    kev_judge = KevJudge(device) if "kev" in judges_list else None
    lettuce_judge = LettuceJudge(device) if "lettuce" in judges_list else None

    summary = {}

    for sys_name in systems:
        task_files = find_files(results_dir, sys_name, "tasks")
        tasks_map = {}
        for tf in task_files:
            for line in open(tf):
                if not line.strip():
                    continue
                row = json.loads(line)
                tasks_map[(row["id"], row["run"])] = bool(row.get("passed", False))

        step_files = find_files(results_dir, sys_name, "steps")
        if not step_files:
            print(f"Warning: no step files found for system {sys_name}")
            continue

        episodes = []
        for sf in step_files:
            for line in open(sf):
                if line.strip():
                    episodes.append(json.loads(line))
        if limit_episodes > 0:
            # deterministic and balanced: half passed and half failed episodes, ordered by a hash of id and run
            import hashlib
            key = lambda e: hashlib.sha256(f"{e['id']}|{e['run']}".encode()).hexdigest()
            ok = sorted([e for e in episodes if tasks_map.get((e["id"], e["run"]))], key=key)
            bad = sorted([e for e in episodes if not tasks_map.get((e["id"], e["run"]))], key=key)
            half = limit_episodes // 2
            n_ok = min(half, len(ok))
            episodes = ok[:n_ok] + bad[:limit_episodes - n_ok]

        print(f"System {sys_name}: judging {len(episodes)} episodes")

        verdicts_out_path = os.path.join(out_dir, f"verdicts_{sys_name}.jsonl")
        verdicts_file = open(verdicts_out_path, "w")

        sys_metrics = {j: {"steps_judged": 0, "steps_flagged": 0, "task_flags": {}, "task_probs": {}} for j in judges_list}

        for ep in episodes:
            test_id = ep["id"]
            run_id = ep.get("run", 0)
            task_passed = tasks_map.get((test_id, run_id), False)
            entry = get_dataset_entry(test_id)
            if not entry:
                continue

            q_turns = entry.get("question", [])
            requests = []
            turn_plans = {}
            for s in ep.get("steps", []):
                if s.get("kind") == "plan":
                    turn_plans[s.get("turn", 0)] = s.get("text", "")

            recent = []
            turn_calls = []
            current_turn = -1

            for s in ep.get("steps", []):
                kind = s.get("kind")
                if kind not in ("call", "msg"):
                    continue

                turn = s.get("turn", 0)
                if turn != current_turn:
                    while len(requests) <= turn:
                        t_idx = len(requests)
                        t_turn = q_turns[t_idx] if t_idx < len(q_turns) else []
                        u_text = "\n".join(m["content"] for m in t_turn) if t_turn else run.ADDED_FUNC_PROMPT
                        requests.append(u_text)
                    current_turn = turn
                    turn_calls = []

                plan_text = turn_plans.get(turn, "")

                evidence = []
                if kind == "call":
                    evidence = rebuild_evidence(s.get("call", ""), s.get("ev", []))
                    step_spec = {"kind": "call", "text": s.get("call", "")}
                else:
                    step_spec = {"kind": "msg", "text": s.get("text", "")}

                judge_state = P.build_state(requests, plan_text, recent, step_spec, evidence)

                step_record = {
                    "id": test_id,
                    "run": run_id,
                    "system": sys_name,
                    "turn": turn,
                    "kind": kind,
                    "step": s.get("call") if kind == "call" else s.get("text"),
                    "blocked_original": s.get("blocked", False),
                    "task_passed": task_passed,
                }

                if kev_judge:
                    t_start = time.time()
                    k_res = kev_judge.judge(judge_state, kind)
                    k_res["elapsed_s"] = round(time.time() - t_start, 3)
                    step_record["kev"] = k_res

                    m = sys_metrics["kev"]
                    m["steps_judged"] += 1
                    if k_res["flagged"]:
                        m["steps_flagged"] += 1
                    ep_key = (test_id, run_id)
                    m["task_flags"][ep_key] = m["task_flags"].get(ep_key, False) or k_res["flagged"]
                    m["task_probs"][ep_key] = max(m["task_probs"].get(ep_key, 0.0), k_res["flag_prob"])

                if lettuce_judge and kind == "msg":
                    t_start = time.time()
                    l_res = lettuce_judge.judge(turn_calls, s.get("text", ""), requests[-1])
                    l_res["elapsed_s"] = round(time.time() - t_start, 3)
                    step_record["lettuce"] = l_res

                    m = sys_metrics["lettuce"]
                    m["steps_judged"] += 1
                    if l_res["flagged"]:
                        m["steps_flagged"] += 1
                    ep_key = (test_id, run_id)
                    m["task_flags"][ep_key] = m["task_flags"].get(ep_key, False) or l_res["flagged"]
                    m["task_probs"][ep_key] = max(m["task_probs"].get(ep_key, 0.0), l_res["flag_prob"])

                verdicts_file.write(json.dumps(step_record) + "\n")

                if kind == "call" and not s.get("blocked", False):
                    out_str = s.get("out", "")
                    recent.append((s.get("call", ""), out_str))
                    turn_calls.append((s.get("call", ""), out_str))

        verdicts_file.close()

        summary[sys_name] = {}
        for j in judges_list:
            m = sys_metrics[j]
            steps_judged = m["steps_judged"]
            step_flag_rate = round(m["steps_flagged"] / steps_judged, 4) if steps_judged > 0 else 0.0

            passed_tasks_flags = [fl for k, fl in m["task_flags"].items() if tasks_map.get(k, False)]
            failed_tasks_flags = [fl for k, fl in m["task_flags"].items() if not tasks_map.get(k, False)]

            rate_passed = round(sum(passed_tasks_flags) / len(passed_tasks_flags), 4) if passed_tasks_flags else 0.0
            rate_failed = round(sum(failed_tasks_flags) / len(failed_tasks_flags), 4) if failed_tasks_flags else 0.0

            all_tasks = list(m["task_flags"].keys())
            y_true = [0 if tasks_map.get(k, False) else 1 for k in all_tasks]
            y_scores = [m["task_probs"].get(k, 0.0) for k in all_tasks]
            auroc_val = compute_auroc(y_true, y_scores)

            summary[sys_name][j] = {
                "steps_judged": steps_judged,
                "step_flag_rate": step_flag_rate,
                "task_any_flag_rate_passed": rate_passed,
                "task_any_flag_rate_failed": rate_failed,
                "auroc": auroc_val,
            }

    summary_path = os.path.join(out_dir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print("Summary:")
    print(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser(description="Offline judge evaluator for recorded agent steps")
    ap.add_argument("--results", required=True, help="Directory containing system results")
    ap.add_argument("--systems", required=True, help="Comma separated system names")
    ap.add_argument("--judges", default="kev,lettuce", help="Comma separated judges")
    ap.add_argument("--limit-episodes", type=int, default=0, help="Max episodes to judge per system")
    ap.add_argument("--device", default="cuda:0", help="Computation device cuda:0 or cpu")
    ap.add_argument("--out", required=True, help="Output directory")
    args = ap.parse_args()

    systems = [s.strip() for s in args.systems.split(",") if s.strip()]
    judges = [j.strip() for j in args.judges.split(",") if j.strip()]

    run_offline(
        results_dir=args.results,
        systems=systems,
        judges_list=judges,
        limit_episodes=args.limit_episodes,
        device=args.device,
        out_dir=args.out,
    )


if __name__ == "__main__":
    main()
