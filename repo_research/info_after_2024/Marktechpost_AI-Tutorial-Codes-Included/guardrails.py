import mlflow, asyncio
from pydantic import BaseModel
from agents import (
    Agent, Runner,
    GuardrailFunctionOutput, InputGuardrailTripwireTriggered,
    input_guardrail, RunContextWrapper)

from dotenv import load_dotenv
load_dotenv()

mlflow.openai.autolog()
mlflow.set_tracking_uri("./mlruns")
mlflow.set_experiment("Agent‑Guardrails")

class MedicalSymptons(BaseModel):
    medical_symptoms: bool
    reasoning: str


guardrail_agent = Agent(
    name="Guardrail check",
    instructions="Check if the user is asking you for medical symptons.",
    output_type=MedicalSymptons,
)


@input_guardrail
async def medical_guardrail(
    ctx: RunContextWrapper[None], agent: Agent, input
) -> GuardrailFunctionOutput:
    result = await Runner.run(guardrail_agent, input, context=ctx.context)

    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=result.final_output.medical_symptoms,
    )


agent = Agent(
    name="Customer support agent",
    instructions="You are a customer support agent. You help customers with their questions.",
    input_guardrails=[medical_guardrail],
)


async def main():
    try:
        await Runner.run(agent, "Should I take aspirin if I'm having a headache?")
        print("Guardrail didn't trip - this is unexpected")

    except InputGuardrailTripwireTriggered:
        print("Medical guardrail tripped")


if __name__ == "__main__":
    asyncio.run(main())