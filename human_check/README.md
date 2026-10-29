# Human check of the LLM labels: instructions

## Why we are doing this

Every result in the project is scored against labels written by two LLMs, DeepSeek and GLM. We showed the two LLMs mostly agree **with each other** (kappa 0.73 on tool calls, 0.61 on turn ends). That does not show they are **right**. The proposal requires people to check them:

> a stratified sample of steps, half flagged and half not, is labelled by two of us with a third deciding disagreements … the bar is kappa 0.7 both between the annotators and against our consensus. The first 100 steps are checked early as a pilot. Below 0.6 the guide is rewritten and the steps relabelled; between 0.6 and 0.8 we label more steps until the result is clear; above 0.8 we stop at 200.

This folder is that check: the **100-step pilot**, on val steps the LLMs already labelled. Its result decides whether we can train Laya on the LLM labels and trust them as the grading key. Until it passes, we don't build on them.

## Roles

| Role | Who | Job | Time |
|---|---|---|---|
| Labeller 1 | _(name)_ | Label all 100 steps | about 2 to 3 hours |
| Labeller 2 | _(name)_ | Label all 100 steps, separately | about 2 to 3 hours |
| Referee | _(name)_, not one of the labellers | Decide the steps where the two labellers differ | about 30 to 60 min |
| Organiser | Pavan | Runs the scoring script, reports the result | minutes |

## What's in this folder

| File | What it is |
|---|---|
| `README.md` | These instructions |
| `GUIDE.md` | The labelling rules: the same rules the LLMs followed, written for people. **Read it fully before starting.** |
| `pilot/items.md` | The 100 steps to label (H001 to H100). Opens nicely on GitHub or in a Markdown preview. |
| `pilot/sheet_template.csv` | The answer sheet to copy |
| `pilot/key.json`, `pilot/sample.json` | Which step each ID is, for the scoring script. **Labellers and referee: do not open.** |
| `build_sample.py`, `score.py` | Scripts that build the sample and score it. Only the organiser runs these. |

## Rules (these keep the check valid)

1. **Work alone.** Don't discuss steps with the other labeller until both of you are done.
2. **Stay blind.** Don't open `pilot/key.json`, the LLM label files (`runs/data/**/annot_*`), the other labeller's sheet, or anything in `analysis/` about these steps.
3. **Follow `GUIDE.md` as written**, even where you'd personally decide differently. We're checking whether the LLMs applied this guide correctly. When the guide says "when unsure, on_track", do that.
4. **Answer every step.** If a step is genuinely unclear, give your best answer and explain in `note`.
5. **Don't push your sheet until both labellers have said "done"** in the group chat, so neither can see the other's answers.

## Labellers: step by step

1. Get the latest repo:
   ```
   git pull
   ```
2. Read `human_check/GUIDE.md` fully. It takes about 10 minutes and has examples for every answer.
3. Copy the answer sheet and name it after yourself (lowercase, no spaces):
   ```
   cp human_check/pilot/sheet_template.csv human_check/pilot/labels_<yourname>.csv
   ```
4. Open `human_check/pilot/items.md` (on GitHub, or in VS Code with Markdown preview) next to your sheet.
5. For each step H001 to H100, fill your sheet:
   - **`call` rows:** fill `q1` (`on_track` or `off_track`) and `q2` (`none` or `made_up_value`). Leave `answer` empty.
   - **`turn` rows:** fill `answer` (`done`, `missing_action`, `should_ask_user` or `unsupported_claim`). Leave `q1` and `q2` empty.
   - `note` is optional: a few words on why, or what made it hard.

   Type the values exactly as written, in lowercase with underscores. The script rejects anything else and tells you which row.
6. Editing the sheet: Excel, Google Sheets, Numbers or any text editor all work. **Keep the column names, and save as CSV** (not .xlsx).
7. You can stop and continue later. Save as you go. Taking breaks every 25 steps or so helps keep judgement consistent.
8. When finished, say "done" in the group chat. Once **both** labellers have, commit and push only your sheet:
   ```
   git pull
   git add human_check/pilot/labels_<yourname>.csv
   git commit -m "Human check pilot: labels from <yourname>"
   git push
   ```

## Organiser: step by step

1. After both sheets are pushed:
   ```
   git pull
   python3 human_check/score.py human_check/pilot
   ```
   The script checks both sheets. If a value is wrong or a step is missing, it names the row; ask that labeller to fix it.
2. If the sheets are fine, it prints human-vs-human agreement and writes `human_check/pilot/decisions.csv`, which lists every step where the labellers differ. Push it and tell the referee.

   No extra packages are needed, only Python 3. The LLM labels are read straight from `runs/data/...jsonl.gz`.

## Referee: step by step

1. `git pull`, then open `human_check/pilot/decisions.csv` and `human_check/pilot/items.md`.
2. Each row is a step the two labellers answered differently. Their answers are in the last two columns. Read the step in `items.md`, apply `GUIDE.md`, and fill `q1` and `q2` (calls) or `answer` (turns) with the correct answer. You can pick either labeller's answer or a third one. Use `note` for anything tricky.
3. Save as CSV, then commit and push `decisions.csv`.

## Organiser: final result

```
git pull
python3 human_check/score.py human_check/pilot
```

This writes `human_check/pilot/results.md` (all agreement tables plus the decision) and `consensus.csv` (the agreed human answer for each step). Commit both and share `results.md` in the chat.

## How to read the result

The script builds the **human consensus**: the labellers' answer where they agree, the referee's where they don't. It compares that consensus with DeepSeek and with GLM. The deciding number is the **headline kappa** (every step, "problem" vs "fine"), using the lower of the two LLMs.

| Lower kappa | What it means | What we do (proposal rule) |
|---|---|---|
| 0.8 or more | The LLM labels match people well | Passes. Finish with 100 more steps from the test runs, then use the LLM labels. |
| 0.7 to 0.8 | Passes the bar, but not clearly | Label more steps until the result is clear |
| 0.6 to 0.7 | Under the bar | Label more steps; look at where people and LLMs differ |
| Below 0.6 | The LLM labels can't be trusted as they are | Rewrite the guide from the human decisions, relabel with the LLMs, check again |

**Why there are two kappa columns:** half the sample is steps the LLMs flagged, as the proposal asks. That packs in the hard cases, including most steps where DeepSeek and GLM disagree with each other, so kappa on the raw sample is pessimistic. The **reweighted** columns scale each group back to its real share of all 1,768 val steps, the same way the proposal reweights test F1. The decision uses the reweighted number; both are reported. For reference, DeepSeek and GLM agree with each other at about 0.66 on this reweighted mix, which roughly caps how well a single human answer can match both.

## Later: the second 100 steps

The proposal's full check is 200 steps. The second 100 come from the test runs once those exist and are labelled. The organiser builds them with:
```
python3 human_check/build_sample.py <test run dir> human_check/test --exclude human_check/pilot
```
Then the same process applies in `human_check/test/`.

**Never rebuild `pilot/`** once labelling has started: the IDs would change.
