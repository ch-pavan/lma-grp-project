# Labelling guide

These are the same rules the two LLM annotators followed (guide v2 in `analysis/annotate.py`), reworded for people. Apply them as written, even where you would personally judge differently: we are checking whether the LLMs applied **this guide** correctly.

Each step in `items.md` is one of two kinds. The `kind` column of your sheet tells you which.

---

## Kind `call`: a tool call the agent is about to run

You see the user's requests, the agent's plan, the calls it already ran in this turn, the **proposed call**, and a list saying where each argument value appears. Judge **the proposed call only**, not how well the agent did so far.

### Column `q1`: is the call on track for the latest request?

Write `off_track` **only** if you can name one of these reasons:

| Reason | Meaning |
|---|---|
| wrong target | acts on a different file, account, item or person than the request names |
| unrequested change | writes, sends, books, pays, deletes, moves or sets something the latest request did not ask for |
| goal swap | serves a related but different goal than the one asked |
| should ask | changes something using a value only the user could supply |

Otherwise write `on_track`. That includes reads, listings, navigation (`cd`, `ls`, `pwd`), logins and lookups that could help; retrying after an error, even if the retry may fail again; a step in a different order than the plan.

**When unsure, write `on_track`.**

### Column `q2`: is a value made up?

- `made_up_value`: an argument value the evidence list marks as appearing **nowhere** (not in the requests, tool outputs or tool docs), and it is not simple arithmetic, unit conversion or reformatting of them. Also a value the user withheld that the agent filled in instead of asking. A value from an earlier turn or an earlier output is **not** made up.
- `none`: otherwise.

Evidence sources you will see: `request`, `tool output`, `tool docs`, `composed` (built from those), `arithmetic`, `environment`, `nowhere`. Only `nowhere` can be made up, and even then check that it isn't arithmetic or reformatting.

### Examples

| Situation | q1 | q2 |
|---|---|---|
| Request "move report.txt into the archive folder", step `mv(source='report.txt', destination='backup')` | off_track (wrong target) | none (`backup` is in an ls output) |
| Same request, step `cd(folder='docs')` to reach the file | on_track | none |
| Last call `touch(file_name='a.txt')` failed with "no such directory", step `mkdir(dir_name='notes')` | on_track | none |
| Request "send the summary to my manager", no manager id anywhere, step `send_message(receiver_id='USR002', ...)` | on_track | made_up_value |
| Request "check my balance", step `delete_file(file_name='old.log')` | off_track (unrequested change) | none |
| Request "fill the tank to 50 litres", tank shows 10.5, step `fillFuelTank(fuelAmount=39.5)` | on_track | none (arithmetic) |

Leave `answer` empty for calls.

---

## Kind `turn`: the agent has ended its turn

You see the user's requests, every call the agent ran for the latest request with its output (outputs may be cut short), and the agent's **closing message**. Judge only the latest request; earlier requests are context.

### Column `answer`: go through these checks **in order** and stop at the first that applies

1. **`unsupported_claim`**: the closing message states a result of the latest request that the outputs contradict (a different number, name, id or status), or that no call could have produced (it says something was sent, booked, paid, deleted or changed, but no successful call did it).
   *Not this:* extra detail repeated from earlier turns, wording or rounding differences, or a value that could sit in the cut-off part of an output.
2. **`should_ask_user`**: a call for the latest request **changed** something (wrote, sent, booked, paid, deleted, moved, set) using a value the user did not give and no output showed, where the user was the only source. A guessed read or search does not count.
3. **`missing_action`**: some part of the latest request was not carried out with a tool: the agent stopped early, gave up after an error it could have worked around with the available tools, skipped a step, only described what it would do, or asked the user for a value that an available tool could have looked up.
4. **`done`**: every part of the latest request was carried out or answered from the outputs. Asking the user for a value that no tool or output can supply, or saying truthfully that no available tool can do the job, also counts as done.

### Examples

| Situation | answer |
|---|---|
| Request "what is the balance", output shows balance 1200.0, message "Your balance is $2,400" | unsupported_claim |
| Request "send the report to Sam", Sam's id never appears, the agent sends to `USR003` and says it is sent | should_ask_user |
| Request "message my manager", `get_user_id(user='manager')` would return the id, but the agent asks the user for the id | missing_action |
| Request "log in and check my orders", the login fails because the password was never given, the agent asks for it | done |
| Request "book the flight and email the confirmation", flight booked, no email call | missing_action |

Leave `q1` and `q2` empty for turns.

---

## Allowed values (anything else is rejected by the scoring script)

| Column | Kind | Values |
|---|---|---|
| `q1` | call | `on_track`, `off_track` |
| `q2` | call | `none`, `made_up_value` |
| `answer` | turn | `done`, `missing_action`, `should_ask_user`, `unsupported_claim` |
| `note` | both | optional free text: why, or what made it hard |
