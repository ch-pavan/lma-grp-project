# Where the project stands, and which benchmarks fit the goal (25 Oct 2026)

Goal, in one line: a small agent system that runs fast and cheap and still finishes tasks reliably. Laya is the cheap check inside it: a 0.4B classifier, one forward pass per step, in place of a 9B judge that thinks for about 1,500 to 2,400 tokens per step.

Numbers on our runs come from `2026-10-24_qwen35_9b_baseline.md`. Outside numbers carry their snapshot date; rows marked (aggregator) come from third party sites and were not checked against the official board.

## 1. Our status

### Working

| What | Laya | 9B SLM judge | Note |
|---|---|---|---|
| Bad steps, offline, 1,277 val calls (step labels) | F1 0.59, AUROC 0.91 | F1 0.24 | Laya flags half as often and is right more than twice as often |
| Turn done check, offline, 495 val turn ends | F1 0.53 | F1 0.41 | Level with DeepSeek (0.50) and GLM (0.52) as annotators |
| Off track vs v2 annotator labels, calls | +7 to +9 F1 over the 9B | | CI touches 0 |
| Off track vs v2 annotator labels, closing messages | +12 to +18 F1 over the 9B | | CI above 0 on DeepSeek labels |
| Judge cost | about 0 | about 10k tokens per task, about 2x time per task | |

### Not working yet

1. **Primary hypothesis not met on val:** −1.0 to +2.0 F1 against the +9 bar. The primary averages off track (Laya wins) with false claim (a tie near F1 0.05 to 0.10).
2. **False claim cannot be measured on val:** only 6 to 15 of 495 closing messages are false claims. Laya also has no false claim head; its done head only says done or not done.
3. **The fair 9B prompt narrowed the gap:** with the harness judge prompt the 9B's call F1 rose from 0.28 to 0.34, and Laya's lead on calls fell from +14.5 to +8.2.
4. **No live system beats no judge:** Laya −0.8, 9B judge +0.8, oracle +4.2, all with CIs that include 0. Two identical no judge runs disagree on 28 of 120 tasks. With the 9B agent the room for any checker is small; on Shuban's 4B the oracle gave +9.2.

### Next

1. A typed closing message head: false claim, missing action, done.
2. Test labels sized for about 300 false claims.
3. Live runs on the 4B agent, where a checker has more to fix.
4. Better corrections, since a flag alone rarely fixes the step: about 27% of failed val tasks stopped after an error whose message held the fix.

## 2. BFCL multi-turn: how to read the score

- **What it is:** 800 tasks (base, miss_param, miss_func, long_context, 200 each), 8 simulated apps, about 4 user turns and 6 reference calls per task, graded on one reference end state.
- **Quality:** Epoch AI rates BFCL v4 "Flawed": 24 of 50 sampled tasks (48%) had defects that can change the score, 8 of 15 in multi-turn.
- **The ask turn is not scored** ("Asking Earns Nothing", arXiv 2610.04429, 3 Oct 2026): in miss_param and miss_func the official scorer skips the turn where the model should ask, so the score rewards acting. Scored on 223 matched act/ask pairs:

| Model | Act or ask decision accuracy | Official score, same items |
|---|---|---|
| GPT-5.4 | 80.7% | 32.7% (34.0% on all 800) |
| Gemma 4 31B | 78.5% | 50.7% |
| Qwen3.8-Max | 78.3% | 47.1% |
| **Qwen3.5-9B (our agent)** | **77.4%** | **52.5%** |
| Qwen3.6-27B | 77.1% | 58.7% |
| Gemma 4 E4B | 67.7% | 22.9% |

- **The official leaderboard is stale:** last data update 12 Apr 2026. Its top multi-turn rows are xLAM-2-70B 77.4%, xLAM-2-8B 70.0% (trained for this style of task), Claude Opus 4.5 68.4%; Qwen3-8B is 41.8%.

**Takeaway:** 80% on BFCL multi-turn is not a meaningful target. Our 9B is within about 3 points of GPT-5.4 on the act or ask decision. We should report that decision accuracy next to the official score, using their paired scorer for Laya's ask question.

## 3. Other benchmarks, state as of Oct 2026

### Close to solved

| Benchmark | Top | Source date |
|---|---|---|
| AppWorld test normal | Claude Opus 4.6 91.1 TGC / 89.3 SGC; **Qwen3-14B 86.9 / 80.4** | official, Mar and Feb 2026 |
| τ²-bench telecom / retail | about 99% / 92% (aggregator) | 2026 |
| τ²-bench airline | Claude Fable 5 80.2% | OpenRouter, 24 Oct 2026 |
| AndroidWorld, OSWorld-Verified | above 90% (aggregator) | 2026 |

### Still hard, even for frontier models

| Benchmark | What it tests | Top |
|---|---|---|
| AppWorld test challenge | unseen apps and harder tasks | Claude Opus 4.7 85.6 / 77.0; Qwen3-14B 67.6 / 50.4 (official) |
| τ³-bench banking | policy-bound multi-turn service | Grok 4.6 50.7, Claude Fable 5.1 47.2, GPT-6 Astra 41.4 (aggregator, 14 Oct) |
| MCPMark | real tools over MCP | 52.6% pass@1, 33.9% pass^4 (paper); a "Verified" variant reports up to 94.5%, method not checked |
| iOSWorld (Jun 2026) | 26 iOS apps sharing one user's data, 133 tasks, through the screen | Opus 4.6 51.9% (multi-app 37%); Qwen3.5-35B-A3B 10.5% |
| Claw-Anything (May 2026) | always-on assistant over months of activity | GPT-5.5 34.5% |
| OSWorld 2.0 (Jun 2026) | long real computer tasks | about 20% |
| MCP-Persona (ICML 2026) | MCP tools on personal accounts (Reddit, Lark, Slack); code public | no numbers in the abstract |

**Pattern:** single-app and service tasks are nearly solved, sometimes by small models with a good harness (Qwen3-14B on AppWorld normal). Multi-app, long-horizon and personal-context tasks sit at 20 to 50% for every model. A small, fast agent that does those well is an open problem for everyone, not only for small models.

## 4. What it means for us

- **Two levers, both needed for a fast, reliable small agent.** (1) A smarter agent: training it on multi-turn trajectories, as xLAM-2-8B (70% against 42% for Qwen3-8B on BFCL) and probably the Qwen3-14B AppWorld entry did. We do not do this. (2) A cheap check that stops harmful steps, catches false "done" and asks when unsure. That is Laya, our contribution.
- **Targets:** on BFCL multi-turn, 60 to 70% is frontier level and 80% is not meaningful. On AppWorld normal, about 80% is realistic for a small model with a harness. For real use, aim for no silent failures and no unrequested irreversible actions before pass rate. Today 8% of the 9B's irreversible calls are off track, and about 18% of failed val tasks end in a false "done".

## 5. Proposed benchmark plan (for the team to decide)

1. **Keep BFCL** (built, in the proposal) and add the paired act/ask decision score next to the official one.
2. **Add AppWorld, mainly test challenge:** verified leaderboard, small model and frontier reference points, and checks for side damage to other data, which matches Laya's "do no harm" role.
3. **Optional:** MCP-Persona for personal tools over MCP.
4. **Leave out** screen-based benchmarks (iOSWorld, OSWorld 2.0): our agent calls tools through text. ToolSandbox (2024) is superseded.
5. **Report pass^k** (success on every one of k runs) and judge tokens and seconds per task, since speed and cost are the point.

## Sources

- [BFCL leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html), [changelog](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/CHANGELOG.md)
- [Epoch AI review of BFCL v4](https://epoch.ai/benchmarks/berkeley-function-calling-leaderboard/review)
- [Asking Earns Nothing, arXiv 2610.04429](https://arxiv.org/html/2610.04429v1)
- [Calibration is the Bottleneck, arXiv 2609.00949](https://arxiv.org/pdf/2609.00949)
- [AppWorld leaderboard](https://appworld.dev/appworld/leaderboard), [submissions repo](https://github.com/StonyBrookNLP/appworld-leaderboard)
- [OpenRouter τ²-Bench Airline](https://openrouter.ai/benchmarks/tau2-bench-airline), [BenchLM AA τ³ Banking](https://benchlm.ai/benchmarks/aatau3banking), [llm-stats τ² Telecom](https://llm-stats.com/benchmarks/tau2-telecom), [taubench.com](http://taubench.com/leaderboard/)
- [MCPMark](https://mlanthology.org/iclr/2026/wu2026iclr-mcpmark/), [MCPMark GitHub](https://github.com/eval-sys/mcpmark)
- [iOSWorld](https://arxiv.org/html/2606.09764v1), [Claw-Anything](https://arxiv.org/abs/2605.26086), [MCP-Persona](https://arxiv.org/abs/2606.02470), [ASTRA-bench](https://arxiv.org/abs/2603.01357), [OSWorld 2.0](https://arxiv.org/pdf/2606.29537), [MobileWorld](https://arxiv.org/pdf/2512.19432)
- [AI agent benchmarks 2026 (aggregator)](https://decodethefuture.org/en/ai-agent-benchmarks-2026/)
