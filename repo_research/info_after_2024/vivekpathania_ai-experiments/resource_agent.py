from agno.agent import Agent, RunResponse
from agno.utils.log import logger
from agno.tools.thinking import ThinkingTools
from utils.llm import get_model
from agno.tools.duckduckgo import DuckDuckGoTools

# --- Define Pydantic Models for Output Structure ---

RESOURCE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "week": {
            "type": "integer",
            "description": "The week number (ranging from 1 to 12)."
        },
        "resources": {
            "type": "array",
            "description": "List of learning resources for the week.",
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the resource."
                    },
                    "url": {
                        "type": "string",
                        "description": "The URL to access the resource."
                    },
                    "type": {
                        "type": "string",
                        "description": "The type of resource (video, article, course, documentation, etc.)."
                    },
                    "cost": {
                        "type": "string",
                        "description": "Whether the resource is free or paid."
                    },
                    "estimated_time": {
                        "type": "string",
                        "description": "Estimated time to complete the resource (optional)."
                    }
                },
                "required": ["title", "url", "type", "cost"]
            }
        }
    },
    "required": ["week", "resources"]
}

class ResourceAgent(Agent):
    """
    An agent designed to find and recommend high-quality learning resources
    based on the weekly topics and concepts provided by the CurriculumAgent.
    """

    def __init__(self):
        """
        Initializes the ResourceAgent.
        """
        agent_name = "resource-finder"
        agent_description = "Finds and recommends high-quality learning resources for each week's topics and concepts."

        agent_instructions = """
You are an expert learning resource curator AI trained to find and recommend high-quality educational materials.

Based on the provided `week_data`, your job is to find and recommend the most relevant, high-quality learning resources that align with the week's topics and concepts.

---

Use the `ThinkingTool` to plan your reasoning before generating output. Your internal steps must include:

- Analyzing the week's topics and concepts to identify key learning objectives
- Considering different learning styles and preferences
- Evaluating resource quality, relevance, and difficulty level
- Ensuring a good mix of resource types (documentation, tutorials, videos, etc.)

---

Then, follow these instructions **strictly** to produce the resource recommendations:

### 1. **Resource Selection Criteria**
- Prioritize high-quality, up-to-date resources
- Include a mix of free and paid resources when appropriate
- Consider different learning styles (visual, textual, interactive)
- Ensure resources match the week's difficulty level

### 2. **Resource Types to Include**
- Official documentation
- Video tutorials
- Interactive tutorials/courses
- Blog posts/articles
- Practice exercises
- Code examples
- Books (when highly relevant)

### 3. **Resource Requirements**
For **each resource**:
- `title`: Clear, descriptive title
- `type`: One of: "documentation", "video", "tutorial", "article", "exercise", "book", "course"
- `cost`: One of: "free", "freemium", "paid"
- `url`: Direct link to the resource
- `estimated_time`: Estimated time to complete (e.g., "2 hours", "30 minutes")
- `description`: Brief description of what the resource covers
- `difficulty`: One of: "beginner", "intermediate", "advanced"
- `format`: One of: "text", "video", "interactive", "audio"

### 4. **Output Format**
Your output MUST match this EXACT structure:


{
  "week": 1,
  "resources": [
    {
      "title": "Flutter Official Documentation - Getting Started",
      "type": "documentation",
      "cost": "free",
      "url": "https://flutter.dev/docs/get-started",
      "estimated_time": "2 hours",
      "description": "Comprehensive guide to setting up Flutter and understanding its core concepts",
      "difficulty": "beginner",
      "format": "text"
    },
    {
      "title": "Flutter Crash Course for Beginners",
      "type": "video",
      "cost": "free",
      "url": "https://youtube.com/watch?v=example",
      "estimated_time": "3 hours",
      "description": "Step-by-step video tutorial covering Flutter basics and first app creation",
      "difficulty": "beginner",
      "format": "video"
    },
    {
      "title": "Flutter UI Basics - Interactive Tutorial",
      "type": "tutorial",
      "cost": "freemium",
      "url": "https://example.com/flutter-ui-basics",
      "estimated_time": "4 hours",
      "description": "Interactive tutorial with hands-on exercises for learning Flutter UI components",
      "difficulty": "beginner",
      "format": "interactive"
    }
  ]
}


IMPORTANT:
- Output ONLY the JSON object with the exact structure like ```json or ``` shown above
- Include 3-5 high-quality resources per week
- Each resource MUST have all fields: title, type, cost, url, estimated_time, description, difficulty, and format
- Do NOT include explanations, commentary, or ThinkingTool reasoning in the output

---

Optional Considerations:
- If a specific topic is challenging, include more resources for that topic
- Include both theoretical and practical resources
- Consider including resources in different languages if relevant

---

**Reminder:** The ThinkingTool is only for internal planning and will not be visible in the final output.

Respond ONLY with the final JSON object — no markdown, no explanations.
"""
        thinking_tool = ThinkingTools(add_instructions=True)
        search_tool = DuckDuckGoTools(search=True,news=False,fixed_max_results=3)

        super().__init__(
            name=agent_name,
            description=agent_description,
            model=get_model(),
            instructions=agent_instructions,
            tools=[thinking_tool,search_tool],
            add_datetime_to_instructions=False,
            use_json_mode=True,
            show_tool_calls=True
        )

    def process(self, week_data: dict) -> RunResponse:
        """
        Processes the weekly topic data to find relevant learning resources.

        Args:
            week_data (dict): A dictionary containing the week number, topics, concepts, and optional project.
                             Expected format:
                             {
                                 "week": 1,
                                 "topics": ["Topic 1", "Topic 2"],
                                 "concepts": ["Concept 1", "Concept 2", "Concept 3"],
                                 "project": "Optional project description"
                             }

        Returns:
            RunResponse: The response from the agent. If successful and validation passes,
                         `content` will be a JSON object with the week number and recommended resources.
                         Otherwise, `content` might be the raw LLM output or an error dict,
                         and `success` will be False.
        """
        if not week_data or not isinstance(week_data, dict):
            logger.error("Invalid week data provided.")
            return RunResponse(success=False, content={"error": "Week data must be a dictionary."}, cost=0.0, latency=0.0)
        
        required_fields = ["week", "topics", "concepts"]
        for field in required_fields:
            if field not in week_data:
                logger.error(f"Missing required field: {field}")
                return RunResponse(success=False, content={"error": f"Missing required field: {field}"}, cost=0.0, latency=0.0)
        
        # Format the input for the LLM
        input_text = f"Week {week_data['week']} Topics: {', '.join(week_data['topics'])}\n"
        input_text += f"Concepts: {', '.join(week_data['concepts'])}\n"
        
        if "project" in week_data and week_data["project"]:
            input_text += f"Project: {week_data['project']}\n"
        
        logger.info(f"Finding resources for week {week_data['week']} ")
        
        response: RunResponse = self.run(input_text)
        logger.info(f"Resource agent response: {response.content}")
        
        return response
