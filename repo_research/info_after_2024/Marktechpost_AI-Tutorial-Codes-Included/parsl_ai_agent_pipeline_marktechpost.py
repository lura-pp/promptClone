
!pip install -q parsl transformers accelerate

import math, json, time, random
from typing import List, Dict, Any
import parsl
from parsl.config import Config
from parsl.executors import ThreadPoolExecutor
from parsl import python_app

parsl.load(Config(executors=[ThreadPoolExecutor(label="local", max_threads=8)]))

@python_app
def calc_fibonacci(n: int) -> Dict[str, Any]:
    def fib(k):
        a, b = 0, 1
        for _ in range(k): a, b = b, a + b
        return a
    t0 = time.time(); val = fib(n); dt = time.time() - t0
    return {"task": "fibonacci", "n": n, "value": val, "secs": round(dt, 4)}

@python_app
def count_primes(limit: int) -> Dict[str, Any]:
    sieve = [True]*(limit+1); sieve[0:2] = [False, False]
    for i in range(2, int(limit**0.5)+1):
        if sieve[i]:
            step = i
            sieve[i*i:limit+1:step] = [False]*(((limit - i*i)//step)+1)
    primes = sum(sieve)
    return {"task": "count_primes", "limit": limit, "count": primes}

@python_app
def extract_keywords(text: str, k: int = 8) -> Dict[str, Any]:
    import re, collections
    words = [w.lower() for w in re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", text)]
    stop = set("the a an and or to of is are was were be been in on for with as by from at this that it its if then else not no".split())
    cand = [w for w in words if w not in stop and len(w) > 3]
    freq = collections.Counter(cand)
    scored = sorted(freq.items(), key=lambda x: (x[1], len(x[0])), reverse=True)[:k]
    return {"task":"keywords","keywords":[w for w,_ in scored]}

@python_app
def simulate_tool(name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    time.sleep(0.3 + random.random()*0.5)
    return {"task": name, "payload": payload, "status": "ok", "timestamp": time.time()}

def tiny_llm_summary(bullets: List[str]) -> str:
    from transformers import pipeline
    gen = pipeline("text-generation", model="sshleifer/tiny-gpt2")
    prompt = "Summarize these agent results clearly:\n- " + "\n- ".join(bullets) + "\nConclusion:"
    out = gen(prompt, max_length=160, do_sample=False)[0]["generated_text"]
    return out.split("Conclusion:", 1)[-1].strip()

def plan(user_goal: str) -> List[Dict[str, Any]]:
    intents = []
    if "fibonacci" in user_goal.lower():
        intents.append({"tool":"calc_fibonacci", "args":{"n":35}})
    if "primes" in user_goal.lower():
        intents.append({"tool":"count_primes", "args":{"limit":100_000}})
    intents += [
        {"tool":"simulate_tool", "args":{"name":"vector_db_search","payload":{"q":user_goal}}},
        {"tool":"simulate_tool", "args":{"name":"metrics_fetch","payload":{"kpi":"latency_ms"}}},
        {"tool":"extract_keywords", "args":{"text":user_goal}}
    ]
    return intents

def run_agent(user_goal: str) -> Dict[str, Any]:
    tasks = plan(user_goal)
    futures = []
    for t in tasks:
        if t["tool"]=="calc_fibonacci": futures.append(calc_fibonacci(**t["args"]))
        elif t["tool"]=="count_primes": futures.append(count_primes(**t["args"]))
        elif t["tool"]=="extract_keywords": futures.append(extract_keywords(**t["args"]))
        elif t["tool"]=="simulate_tool": futures.append(simulate_tool(**t["args"]))
    raw = [f.result() for f in futures]

    bullets = []
    for r in raw:
        if r["task"]=="fibonacci":
            bullets.append(f"Fibonacci({r['n']}) = {r['value']} computed in {r['secs']}s.")
        elif r["task"]=="count_primes":
            bullets.append(f"{r['count']} primes found ≤ {r['limit']}.")
        elif r["task"]=="keywords":
            bullets.append("Top keywords: " + ", ".join(r["keywords"]))
        else:
            bullets.append(f"Tool {r['task']} responded with status={r['status']}.")

    narrative = tiny_llm_summary(bullets)
    return {"goal": user_goal, "bullets": bullets, "summary": narrative, "raw": raw}

if __name__ == "__main__":
    goal = ("Analyze fibonacci(35) performance, count primes under 100k, "
            "and prepare a concise executive summary highlighting insights for planning.")
    result = run_agent(goal)
    print("\n=== Agent Bullets ===")
    for b in result["bullets"]: print("•", b)
    print("\n=== LLM Summary ===\n", result["summary"])
    print("\n=== Raw JSON ===\n", json.dumps(result["raw"], indent=2)[:800], "...")
