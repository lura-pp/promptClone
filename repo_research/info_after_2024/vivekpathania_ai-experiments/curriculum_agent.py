# /Users/vivek.pathania/Documents/GitHub/learning-coach/agents/curriculum_agent.py

from agno.agent import Agent, RunResponse
from agno.utils.log import logger
from agno.tools.thinking import ThinkingTools
from utils.llm import get_model

# --- Define Pydantic Models for Output Structure ---

CURRICULUM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "curriculum": {
            "type": "array",
            "description": "The structured learning plan with a flexible number of weeks.",
            "items": {
                "type": "object",
                "properties": {
                    "week": {
                        "type": "integer",
                        "description": "The week number (ranging from 1 to the total number of weeks)."
                    },
                    "topics": {
                        "type": "array",
                        "description": "List of main topics covered during the week (1-2 items).",
                        "items": {"type": "string"}
                    },
                    "concepts": {
                        "type": "array",
                        "description": "List of specific concepts or skills learned within the topics (3-5 items).",
                        "items": {"type": "string"}
                    },
                    "project": {
                        "type": "string",
                        "description": "A suggested mini-project or hands-on task for the week to reinforce learning."
                    }
                },
                "required": ["week", "topics", "concepts", "project"]
            }
        }
    },
    "required": ["curriculum"]
}
class CurriculumAgent(Agent):
    """
    An agent designed to generate a structured learning curriculum
    based on a user-provided technical learning goal, utilizing a thinking tool
    for intermediate reasoning and Pydantic for output validation.
    """

    def __init__(self):
        """
        Initializes the CurriculumAgent.
        """
        agent_name = "curriculum-generator"
        agent_description = "Generates a detailed, progressive, and practical learning plan based on a user-provided technical learning goal."

        # Instructions remain largely the same, but the LLM will now receive
        # the schema derived from the Pydantic model.
        agent_instructions = """
You are an expert curriculum designer AI trained to build highly practical, step-by-step learning plans.

Based on the provided `learning_goal`, your job is to create a **detailed, progressive, and actionable learning curriculum** focused on building real-world skills through projects.

---

## ThinkingTool — internal reasoning (not visible in output)

Before generating output, follow these internal steps:

1. **Extract all time cues** from `learning_goal`:
   - Absolute: "April 20", "May 1", "2025-04-25"
   - Relative: "next Saturday", "in 3 days", "within 2 weeks"
   - Convert relative cues into absolute dates using the system date.

2. **Calculate days remaining until deadline.**

3. **Determine the appropriate duration (`plan_length`) and level:**

   First, check if the user **explicitly specifies** a duration:
   - Examples: "3-day crash course", "4-week course", "6-week roadmap", "2-month plan"
   - ✅ If yes, use that **exact duration** and set `plan_length` accordingly (in days or weeks)
   - ⚠️ Only override this if there's a direct contradiction (e.g. user asks for a 4-week plan but also says “interview in 5 days”)

   If no explicit duration is mentioned, use the following table based on the time remaining:

   | Timeframe     | Days Left      | Label    | Plan Length  |
   |---------------|----------------|----------|---------------|
   | Urgent        | ≤ 7 days       | urgent   | 3 weeks       |
   | Short-term    | 8–14 days      | short    | 1 week        |
   | Medium-term   | 15–30 days     | medium   | 2–3 weeks     |
   | Long-term     | > 30 days      | long     | 4–12 weeks    |

4. **Identify experience level and learning goal intent**:
   - Beginner / Intermediate / Advanced
   - Interview prep, job readiness, project building, foundational learning, etc.

5. **Prioritize topics**:
   - Must-know first, then nice-to-have
   - Focus on theory for interviews
   - Focus on practice for project or job-based goals

---

## Curriculum Structure

- The number of weeks MUST match `plan_length`
- Each week must build upon the previous one
- Projects should reinforce the concepts taught
- For urgent cases, compress critical topics into early weeks
- For long-term plans, gradually increase difficulty and scope

---

## Weekly Content Requirements

For each **week**, include:

- `topics`: 1–2 high-level themes (e.g., "State Management", "API Integration")
- `concepts`: 3–5 granular skills or ideas (e.g., "Provider in Flutter", "Async/Await in JS")
- `project`: A small but real-world project that applies the week's topics and concepts

Project types can include:
- UI-heavy interfaces
- Logic-driven applications
- Data-centric tools
- Architecture or performance-focused builds

Capstone-level projects should appear in the final week for longer plans.

---

## Output Format (Strict)

Your final response MUST use this exact format:


{
  "curriculum": [
    {
      "week": 1,
      "topics": ["Introduction to Flutter", "Basic UI Components"],
      "concepts": [
        "Flutter architecture and widgets",
        "Stateless vs Stateful widgets",
        "Basic layout widgets (Container, Row, Column)",
        "Material Design basics"
      ],
      "project": "Create a simple profile card app with basic UI components"
    },
    {
      "week": 2,
      "topics": ["State Management Basics", "User Input"],
      "concepts": [
        "setState and StatefulWidget lifecycle",
        "Form validation",
        "Text fields and buttons",
        "Basic state management patterns"
      ],
      "project": "Build a todo list app with add/edit/delete functionality"
    }
  ]
}


Respond ONLY with the final JSON object — no markdown, no explanations.
"""
        thinking_tool = ThinkingTools(add_instructions=True)

        super().__init__(
            name=agent_name,
            description=agent_description,
            model=get_model(),
            instructions=agent_instructions,
            tools=[thinking_tool],
            add_datetime_to_instructions=True,
            use_json_mode=True,
            show_tool_calls=True
        )

    def process(self, learning_goal: str) -> RunResponse:
        """
        Processes the user's learning goal to generate a curriculum.

        Args:
            learning_goal (str): The technical skill or role the user wants to learn.

        Returns:
            RunResponse: The response from the agent. If successful and validation passes,
                         `content` will be a `CurriculumOutput` Pydantic object.
                         Otherwise, `content` might be the raw LLM output or an error dict,
                         and `success` will be False.
        """
        if not learning_goal or not isinstance(learning_goal, str) or len(learning_goal.strip()) == 0:
             logger.error("Invalid learning goal provided.")
             return RunResponse(success=False, content={"error": "Learning goal cannot be empty."}, cost=0.0, latency=0.0)

        logger.info(f"Generating curriculum for goal: '{learning_goal}' using ThinkingTool")

        response: RunResponse = self.run(learning_goal)
        logger.info(f"Curriculum generated: {response.content}")

        return response
    


