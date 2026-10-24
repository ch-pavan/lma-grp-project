# Smoke test for a served model: a plain tool call (no thinking) and a thinking judge style answer, with timings.
# usage: python q35_smoke.py <port> <model>
import json, sys, time
from openai import OpenAI

port, model = sys.argv[1], sys.argv[2]
c = OpenAI(base_url=f"http://localhost:{port}/v1", api_key="x", timeout=600)
tool = {"type": "function", "function": {"name": "cd", "description": "Change the current directory.",
        "parameters": {"type": "object", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}}}
ok = True
for think in (False, True):
    t = time.time()
    r = c.chat.completions.create(model=model, messages=[{"role": "user", "content": "Go into the folder named documents."}],
                                  tools=[tool], tool_choice="auto", max_tokens=1024, temperature=0.7, top_p=0.8,
                                  extra_body={"chat_template_kwargs": {"enable_thinking": think}, "top_k": 20})
    m = r.choices[0].message
    tc = [(x.function.name, x.function.arguments) for x in (m.tool_calls or [])]
    print(f"TOOLCALL think={think} {time.time()-t:.1f}s out_tok={r.usage.completion_tokens} calls={tc} content={(m.content or '')[:200]!r}", flush=True)
    ok &= bool(tc) and tc[0][0] == "cd" and "documents" in tc[0][1]
t = time.time()
r = c.chat.completions.create(model=model, max_tokens=1536, temperature=0.6, top_p=0.95, logprobs=True, top_logprobs=5,
                              messages=[{"role": "user", "content": "A user asked to book a flight to Paris. The agent proposes book_flight(destination='Rome'). "
                                         "Answer with one final line exactly like: VERDICT Q1=on_track|off_track Q2=none|made_up_value"}],
                              extra_body={"chat_template_kwargs": {"enable_thinking": True}, "top_k": 20})
m = r.choices[0].message
print(f"JUDGE {time.time()-t:.1f}s out_tok={r.usage.completion_tokens} {r.usage.completion_tokens/(time.time()-t):.0f} tok/s tail={(m.content or '')[-160:]!r}", flush=True)
print("LOGPROBS", bool(r.choices[0].logprobs and r.choices[0].logprobs.content), flush=True)
print("SMOKE", "PASS" if ok else "FAIL", flush=True)
