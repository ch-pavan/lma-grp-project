# Ground truth replay verification for AgentDojo tasks on S1_none and S2_rules.
import argparse, asyncio, collections, json, os, sys, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import agentdojo_run as ADR


class MockLLM:
    def __init__(self, e):
        self.e = e
        self.task = e["task"]
        env = e["suite_obj"].load_and_inject_default_environment({})
        init_env = self.task.init_environment(env)
        self.gt_calls = self.task.ground_truth(init_env)
        self.call_idx = 0

    async def chat(self, messages, tools=None, tool_choice=None, think=False, max_tokens=0, temperature=None):
        if tool_choice == "none":
            names = [c.function for c in self.gt_calls]
            return types.SimpleNamespace(content="1. " + ", ".join(names), tool_calls=None), 10, 5
        if think:
            return types.SimpleNamespace(content="VERDICT Q1=on_track Q2=none", tool_calls=None), 10, 5

        last_msg = messages[-1] if messages else {}
        if last_msg.get("role") == "user" and "Judge warning" in last_msg.get("content", ""):
            return types.SimpleNamespace(content="Could not complete request.", tool_calls=None), 10, 2

        if self.call_idx < len(self.gt_calls):
            c = self.gt_calls[self.call_idx]
            self.call_idx += 1
            tc = types.SimpleNamespace(
                id=f"call_{self.call_idx}",
                function=types.SimpleNamespace(name=c.function, arguments=json.dumps(c.args)),
            )
            return types.SimpleNamespace(content=None, tool_calls=[tc]), 10, 5

        gt_out = getattr(self.task, "GROUND_TRUTH_OUTPUT", "")
        closing = gt_out if gt_out else "Done."
        return types.SimpleNamespace(content=closing, tool_calls=None), 10, 2


# Explanations for known S2 rules interventions on AgentDojo ground truth calls
KNOWN_REASONS = {
    "banking:user_task_3": "ground truth call uses argument subject='Refund' not found in prompt or environment",
    "slack:user_task_1": "ground truth call uses placeholder body='<summary>' not found in prompt or environment",
    "slack:user_task_6": "ground truth call uses placeholder body='...' not found in prompt or environment",
    "slack:user_task_18": "ground truth call uses placeholder body='<summary>' not found in prompt or environment",
}


async def run_system(system, tasks, concurrency=10):
    judge = ADR.make_judge(system, None)
    sem = asyncio.Semaphore(concurrency)
    suite_counts = collections.defaultdict(lambda: {"pass": 0, "total": 0, "failed": []})
    total_pass = 0

    async def run_one(e):
        nonlocal total_pass
        async with sem:
            mock = MockLLM(e)
            row = await ADR.episode(e, 0, system, mock, judge, None)
        s_name = e["suite"]
        suite_counts[s_name]["total"] += 1
        if row["passed"]:
            suite_counts[s_name]["pass"] += 1
            total_pass += 1
        else:
            reason = KNOWN_REASONS.get(e["id"], row.get("error_type") or "unknown")
            suite_counts[s_name]["failed"].append((e["task_id"], reason))

    await asyncio.gather(*(run_one(e) for e in tasks))
    return total_pass, suite_counts


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="S1_none,S2_rules", help="comma separated systems to test")
    ap.add_argument("--suites", default="workspace,travel,banking,slack", help="suites to include")
    ap.add_argument("--concurrency", type=int, default=10)
    a = ap.parse_args()

    tasks = ADR.load_tasks(a.suites)
    print(f"Loaded {len(tasks)} tasks across suites: {a.suites}")

    for sys_name in [s.strip() for s in a.systems.split(",") if s.strip()]:
        t0 = time.time()
        total_pass, suite_counts = await run_system(sys_name, tasks, a.concurrency)
        elapsed = time.time() - t0
        print(f"\n==========================================")
        print(f"System: {sys_name} ({total_pass}/{len(tasks)} passed, {elapsed:.1f}s)")
        print(f"==========================================")
        for s_name in ["workspace", "travel", "banking", "slack"]:
            sc = suite_counts[s_name]
            print(f"  {s_name:10s} : {sc['pass']:2d}/{sc['total']:2d} passed")
            if sc["failed"]:
                print(f"    Failing tasks in {s_name}:")
                for tid, reason in sc["failed"]:
                    print(f"      - {tid}: {reason}")


if __name__ == "__main__":
    asyncio.run(main())
