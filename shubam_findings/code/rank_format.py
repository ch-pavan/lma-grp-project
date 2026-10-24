# Prompt format shared by the rankers (GPU side) and the rank<N> mode in actions.py (no torch needed).
import json


def call_text(name, args):
    return "<tool_call>\n" + json.dumps({"name": name, "arguments": args}, ensure_ascii=False) + "\n</tool_call>"


def state_messages(requests, recent, docs, response):
    """Compact conversation for a ranker: tool docs, the user requests, the last calls, then the candidate step."""
    sysm = "# Tools\n" + "\n".join(json.dumps({"name": d["name"], "description": d.get("description", ""),
                                                "parameters": d.get("parameters", {})}, ensure_ascii=False) for d in docs)
    msgs = [{"role": "system", "content": sysm}, {"role": "user", "content": "\n".join(requests[-4:])}]
    for c, o in recent[-3:]:
        msgs.append({"role": "assistant", "content": "<tool_call>\n" + str(c) + "\n</tool_call>"})
        msgs.append({"role": "tool", "content": str(o)[:1500]})
    msgs.append({"role": "assistant", "content": response})
    return msgs
