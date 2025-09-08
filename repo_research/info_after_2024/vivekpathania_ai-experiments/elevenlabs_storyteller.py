import os
import uuid
import sys
import asyncio
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from backend.models import StoryOutput, StoryPage

load_dotenv()

class StoryAudioGenerator:
    def __init__(self, output_dir: Optional[Path] = None, voice_id: str = "pNInz6obpgDQGcFmaJgB"):
        """Initialize the audio generator with an output directory and voice settings."""
        # Load API key
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable not set")
            
        # Initialize client
        self.client = ElevenLabs(api_key=self.api_key)
        
        # Set output directory
        if output_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.output_dir = project_root / "output" / "audio"
        else:
            self.output_dir = output_dir
            
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Voice settings
        self.voice_id = voice_id
        self.voice_settings = VoiceSettings(
            stability=0.5,
            similarity_boost=0.75,
            style=0.5,
            use_speaker_boost=True,
        )
        
    async def _generate_audio_file(self, text: str, filename: str) -> Path:
        """Generate audio file from text and save it."""
        # Generate audio
        response = self.client.text_to_speech.convert(
            voice_id=self.voice_id,
            optimize_streaming_latency="0",
            output_format="mp3_22050_32",
            text=text,
            model_id="eleven_turbo_v2",
            voice_settings=self.voice_settings,
        )
        
        # Save file
        output_path = self.output_dir / filename
        with open(output_path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)
                    
        return output_path
        
    async def generate_story_audio(self, story: StoryOutput) -> List[Path]:
        """Generate audio files for each page of the story."""
        # Create tasks for each page
        tasks = []
        for page in story.pages:
            # Generate filename based on page number and story title
            filename = f"page_{page.page_number}_{story.title.lower().replace(' ', '_')}.mp3"
            
            # Create task for this page
            task = self._generate_audio_file(page.content, filename)
            tasks.append(task)
            
        # Wait for all tasks to complete
        audio_files = await asyncio.gather(*tasks)
        
        # Print results
        for i, audio_path in enumerate(audio_files, 1):
            print(f"Generated audio for page {i}: {audio_path}")
            
        return audio_files
        
    # def set_voice_settings(self, stability: float = None, 
    #                       similarity_boost: float = None, 
    #                       style: float = None, 
    #                       use_speaker_boost: bool = None) -> None:
    #     """Update voice settings."""
    #     if stability is not None:
    #         self.voice_settings.stability = stability
    #     if similarity_boost is not None:
    #         self.voice_settings.similarity_boost = similarity_boost
    #     if style is not None:
    #         self.voice_settings.style = style
    #     if use_speaker_boost is not None:
    #         self.voice_settings.use_speaker_boost = use_speaker_boost

async def main():
    # Example usage
    try:
        # Create a test story
        test_story = StoryOutput(
            title="The Joy of Sharing",
            pages=[
                StoryPage(
                    page_number=1,
                    content="Once upon a time, there was a little girl who loved to share.",
                    image_prompt="A little girl sharing her toys with friends"
                ),
                StoryPage(
                    page_number=2,
                    content="She shared her toys with her friends and they all had a great time.",
                    image_prompt="A little girl sharing her toys with friends"
                )
            ],
            moral="Sharing brings joy to everyone",
            age_group="6-8",
            word_count=10
        )
        
        # Create audio generator
        audio_generator = StoryAudioGenerator()
        
        # Optional: Customize voice settings
        
        
        # Generate audio files
        audio_files = await audio_generator.generate_story_audio(test_story)
        print(f"Generated {len(audio_files)} audio files for the story")
        
    except Exception as e:
        print(f"Error generating audio: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())