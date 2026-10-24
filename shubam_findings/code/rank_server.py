# Small HTTP scorer for the rank<N> mode: POST /score {"items": [messages, ...]} -> {"scores": [...]}.
# usage: python rank_server.py MODEL [PORT] [DEVICE]
import sys, threading
import torch
from fastapi import FastAPI
import uvicorn
import rankers

name = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 8010
device = sys.argv[3] if len(sys.argv) > 3 else "cuda:0"
m = rankers.Skywork(name, device=device, dtype=torch.float16 if device.startswith("cuda") else torch.float32)
app = FastAPI()
lock = threading.Lock()


@app.post("/score")
def score(req: dict):
    with lock:
        return {"scores": [m.score(msgs) for msgs in req["items"]]}


@app.get("/health")
def health():
    return {"ok": True}


uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
