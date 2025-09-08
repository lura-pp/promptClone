from crewai import Agent, Task, Crew, LLM
import os
import sys
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from backend.models import StoryOutput, StoryPage
import json
import asyncio

# Load environment variables
load_dotenv()

class StoryWritingAgent:
    def __init__(self):
        self.model = os.getenv("AGENT_MODEL", "gpt-4")
        self.temperature = float(os.getenv("AGENT_TEMPERATURE", "0.7"))
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

    def __createAgent(self) -> Agent:
        llm = LLM(
            model=self.model,
            temperature=self.temperature,
            api_key=self.api_key
        )
        return Agent(
            role="Children's Story Writer and Illustrator",
            goal="Create engaging, educational, and motivational stories for children aged 6-11 (grades 1-5) with accompanying image prompts",
            backstory="""You are a talented children's story writer and illustrator with years of experience in creating 
            age-appropriate content. You specialize in writing simple, clear stories that children can 
            easily understand and relate to. Your stories always include positive messages, educational 
            elements, and motivational themes that help children learn important life lessons while 
            enjoying the story. You also excel at creating detailed image prompts that capture the essence 
            of each page in a colorful, cartoonish style that appeals to children.""",
            llm=llm,
            verbose=True
        )

    def __createTask(self, agent: Agent, prompt: str, max_pages: Optional[int] = None) -> Task:
        max_pages = max_pages or 3  # Default to 3 pages if not specified
        return Task(
            description=f"""Create a children's story based on the following prompt: {prompt}
            
            The story should:
            1. Be divided into {max_pages} main content pages, plus a cover page and an end page
            2. Use simple, clear language appropriate for grades 1-5
            3. Include educational elements
            4. Have a positive, motivational message
            5. Be engaging and relatable for children
            6. Have a clear beginning, middle, and end
            7. Use age-appropriate vocabulary
            8. Include a clear moral or lesson
            
            The story must include:
            1. A cover page with an engaging title and illustration prompt
            2. {max_pages} main content pages
            3. An end page with the moral of the story and a positive message
            
            For each page, create:
            1. The story content for that page
            2. A detailed image prompt that describes a colorful, cartoonish scene that captures the essence of that page
            
            Format the output as a JSON object matching this structure:
            {{
                "title": "Story Title",
                "pages": [
                    {{
                        "page_number": 0,
                        "content": "Cover page content with title only no author",
                        "image_prompt": "Cover illustration prompt"
                    }},
                    {{
                        "page_number": 1,
                        "content": "Page 1 content...",
                        "image_prompt": "Page 1 image prompt..."
                    }},
                    ...
                    {{
                        "page_number": {max_pages + 1},
                        "content": "End page with moral and positive message",
                        "image_prompt": "End page illustration prompt"
                    }}
                ],
                "moral": "The moral of the story",
                "age_group": "Target age group",
                "word_count": total_word_count
            }}
            """,
            expected_output="A complete children's story with cover page, content pages, and end page in JSON format",
            agent=agent
        )

    def _extract_response_text(self, crew_output) -> str:
        """Extract the text content from a CrewOutput object."""
        if hasattr(crew_output, 'raw_output'):
            return str(crew_output.raw_output)
        elif hasattr(crew_output, 'output'):
            return str(crew_output.output)
        return str(crew_output)

    def write_story(self, prompt: str, max_pages: Optional[int] = None) -> tuple[StoryOutput, dict]:
        """Generate a story based on the user's prompt with optional page limit"""
        # Create agent and task
        agent = self.__createAgent()
        task = self.__createTask(agent, prompt, max_pages)
        
        # Create and run the crew
        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True
        )

        # Get response
        crew_output = crew.kickoff()
        
        # Extract the text content from the CrewOutput
        response_text = self._extract_response_text(crew_output)
        
        # Parse the JSON response into our Pydantic model
        try:
            story_data = json.loads(response_text)
            story_output = StoryOutput(**story_data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse story output: {str(e)}")
        
        # Prepare metadata
        metadata = {
            "model": self.model,
            "temperature": self.temperature,
            "timestamp": datetime.now().isoformat(),
            "page_count": len(story_output.pages)
        }

        return story_output, metadata

async def main():
    """Example usage of the StoryWritingAgent with user input"""
    try:
        # Get user input
        print("Welcome to the Story Generator!")
        prompt = input("\nEnter your story prompt (e.g., 'A story about a magical garden'): ")
        while True:
            try:
                num_pages = int(input("\nEnter the number of main content pages (1-5): "))
                if 1 <= num_pages <= 5:
                    break
                print("Please enter a number between 1 and 5.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Initialize the agent
        story_agent = StoryWritingAgent()
        
        # Generate the story
        print("\nGenerating story...")
        story_output, metadata = story_agent.write_story(prompt, max_pages=num_pages)
        
        # Print the story details
        print("\nStory Title:", story_output.title)
        print("Target Age Group:", story_output.age_group)
        print("Word Count:", story_output.word_count)
        print("Moral:", story_output.moral)
        
        # Print each page
        print("\nStory Pages:")
        for page in story_output.pages:
            print(f"\nPage {page.page_number}:")
            if page.page_number == 0:
                print("(Cover Page)")
            elif page.page_number == len(story_output.pages) - 1:
                print("(End Page)")
            print("Content:", page.content)
            print("Image Prompt:", page.image_prompt)
        
        # Print metadata
        print("\nGeneration Metadata:")
        print(f"Model: {metadata['model']}")
        print(f"Temperature: {metadata['temperature']}")
        print(f"Generated at: {metadata['timestamp']}")
        print(f"Total Pages: {metadata['page_count']} (including cover and end pages)")
        
    except Exception as e:
        print(f"Error generating story: {str(e)}")

if __name__ == "__main__":
    # Run the example
    asyncio.run(main())

