import mlflow, asyncio
from agents import Agent, Runner
import os
from dotenv import load_dotenv
load_dotenv()

mlflow.openai.autolog()                           # Auto‑trace every OpenAI call
mlflow.set_tracking_uri("./mlruns")
mlflow.set_experiment("Agent‑Coding‑Cooking")

coding_agent = Agent(name="Coding agent",
                     instructions="You only answer coding questions.")

cooking_agent = Agent(name="Cooking agent",
                      instructions="You only answer cooking questions.")

triage_agent = Agent(
    name="Triage agent",
    instructions="If the request is about code, handoff to coding_agent; "
                 "if about cooking, handoff to cooking_agent.",
    handoffs=[coding_agent, cooking_agent],
)

async def main():
    res = await Runner.run(triage_agent,
                           input="How do I boil pasta al dente?")
    print(res.final_output)

if __name__ == "__main__":
    asyncio.run(main())