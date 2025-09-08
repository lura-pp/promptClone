from moviepy import ImageClip, AudioFileClip, CompositeVideoClip, TextClip, concatenate_videoclips

import os
import sys
from pathlib import Path
from typing import List, Optional

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from backend.models import StoryOutput, StoryPage

class StoryVideoCompiler:
    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize the video compiler with an output directory."""
        # If no output directory is provided, use the default project structure
        if output_dir is None:
            project_root = Path(__file__).parent.parent
            self.output_dir = project_root / "output" / "images"
            self.audio_dir = project_root / "output" / "audio"
        else:
            self.output_dir = output_dir / "images"
            self.audio_dir = output_dir / "audio"
            
        # Ensure output directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Default settings
        self.duration_per_page = 3  # seconds
        self.fps = 24
        self.text_font = "Arial Bold"
        self.text_font_size = 30
        self.text_color = 'black'
        self.text_bg_color = '#ffffff90'
        self.text_padding = 30
        self.line_height = 6
        self.margin = (10,10)
        
    def _get_image_path(self, page: StoryPage, story: StoryOutput) -> Path:
        """Get the path to the generated image for a page."""
        image_filename = f"page_{page.page_number}_{story.title.lower().replace(' ', '_')}.png"
        return self.output_dir / image_filename
        
    def _get_audio_path(self, page: StoryPage, story: StoryOutput) -> Path:
        """Get the path to the generated audio for a page."""
        audio_filename = f"page_{page.page_number}_{story.title.lower().replace(' ', '_')}.mp3"
        return self.audio_dir / audio_filename
        
    def _getTextPostiton(self, text_clip,image_clip,t):
        textH=text_clip.h
        return ("center", image_clip.h-(t*(textH/(self.duration_per_page))))
        
    def _create_page_clip(self, page: StoryPage, image_path: Path, audio_path: Path) -> CompositeVideoClip:
        """Create a video clip for a single page with image, text, and audio."""
        # Create image clip
        image_clip = ImageClip(str(image_path))
        
        # Create audio clip
        audio_clip = AudioFileClip(str(audio_path))
        
        # Set duration based on audio length
        self.set_duration(audio_clip.duration+1)
        image_clip = image_clip.with_duration(self.duration_per_page)
        
        # Create text clip with the page content
        

        if page.page_number == 0:
            text_clip = TextClip(
            text=page.content,
            interline=self.line_height,
            margin = self.margin,
            font=self.text_font,
            font_size=self.text_font_size+15,
            color=self.text_color,
            bg_color=self.text_bg_color,
            size=(image_clip.w-self.text_padding, None),
            method='caption') 

            text_clip = text_clip.with_duration(self.duration_per_page)
            text_clip = text_clip.with_position("center")
        else:
            text_clip = TextClip(
            text=page.content,
            font=self.text_font,
            interline=self.line_height,
            margin = self.margin,
            font_size=self.text_font_size,
            color=self.text_color,
            bg_color=self.text_bg_color,
            size=(image_clip.w-self.text_padding, None),
            method='caption'  # Automatically wrap text
            )
            text_clip = text_clip.with_duration(self.duration_per_page)
            text_clip = text_clip.with_position(lambda t: self._getTextPostiton(text_clip,image_clip,t))
            
        
        
        # Create composite clip with audio
        return CompositeVideoClip([image_clip, text_clip]).with_audio(audio_clip)
        
    def compile_story_video(self, story: StoryOutput) -> str:
        """Create a video from a story with images, text, and audio for each page."""
        # Create clips for each page
        page_clips = []
        for page in story.pages:
            # Get the paths to the generated image and audio
            image_path = self._get_image_path(page, story)
            audio_path = self._get_audio_path(page, story)
            
            if not image_path.exists():
                raise FileNotFoundError(f"Image not found for page {page.page_number}: {image_path}")
            if not audio_path.exists():
                raise FileNotFoundError(f"Audio not found for page {page.page_number}: {audio_path}")
            
            # Create clip for this page
            page_clip = self._create_page_clip(page, image_path, audio_path)
            
            
            page_clips.append(page_clip)
        
        # Concatenate all page clips in sequence
        final_clip = concatenate_videoclips(page_clips)
        
        # Save the video
        output_video_path = self.output_dir.parent / f"{story.title.lower().replace(' ', '_')}.mp4"
        final_clip.write_videofile(str(output_video_path), fps=self.fps)
        
        return str(output_video_path)
        
    def set_duration(self, duration: int) -> None:
        """Set the duration for each page in seconds."""
        self.duration_per_page = duration
        
    def set_text_style(self, font: str = None, font_size: int = None, color: str = None) -> None:
        """Set the text styling options."""
        if font:
            self.text_font = font
        if font_size:
            self.text_font_size = font_size
        if color:
            self.text_color = color

if __name__ == "__main__":
    # Example usage
    try:
        # Create a test story (you would normally get this from the story agent)
        test_story = StoryOutput(
            title="The Little Seed of Kindness",
            pages=[
                StoryPage(
                    page_number=0,
                    content="The Little Seed of Kindness",
                    image_prompt="A colorful illustration of a smiling child holding a small seed, with a sunny background and fluffy white clouds. The title 'The Little Seed of Kindness' is written in bold, playful letters."
                ),
                StoryPage(
                   page_number= 1,
                    content="Once upon a time, in a small village, there lived a little girl named Emma. She had a big heart and loved helping others. One day, Emma found a small seed on the ground and decided to plant it in her garden. She watered it every day and talked to it, saying 'I hope you grow into something beautiful!'",
                    image_prompt="A warm illustration of Emma, a little girl with a big smile, planting a seed in her garden. She is surrounded by gardening tools and a watering can, with a sunny sky and a few birds flying overhead."
                ),
                StoryPage(
                    page_number= 2,
                    content="As the days went by, the seed started to grow into a small plant. Emma continued to care for it, and soon it blossomed into a beautiful flower. The flower attracted bees and butterflies, and its sweet fragrance filled the air. Emma was thrilled to see how her small act of kindness had brought so much joy to the world around her.",
                    image_prompt="A vibrant illustration of the small plant growing into a beautiful flower, with Emma smiling and admiring it. Bees and butterflies are flying around the flower, collecting nectar, and the background is filled with colorful flowers and trees."
                ),
                StoryPage(
                    page_number=3,
                    content="Emma realized that just like the seed, our small acts of kindness can grow into something big and beautiful. She learned that kindness is never wasted, and it can make a difference in the lives of those around us. From that day on, Emma spread kindness wherever she went, and soon her whole village was filled with love, compassion, and beauty.",
                    image_prompt="A heartwarming illustration of Emma standing in the middle of her village, surrounded by people and animals, all smiling and happy. The background is filled with colorful flowers, trees, and a bright sunny sky, symbolizing the positive impact of kindness."
        ),
                StoryPage(
                    page_number=4,
                    content="The moral of the story is that kindness is never wasted. Every small act of kindness can grow into something big and beautiful, making a difference in the lives of those around us. Remember, you have the power to spread kindness and make the world a brighter and more loving place!",
                    image_prompt="A beautiful illustration of a child holding a small seed, with a big smile and a sparkle in their eye. The background is filled with colorful flowers, trees, and a sunny sky, with the words 'Kindness is never wasted' written in bold, playful letters."
                )
            ],
            moral="Kindness is never wasted",
            age_group="6-11 years old",
            word_count=396
        )
        
        # Create the video compiler
        compiler = StoryVideoCompiler()
        
       
        compiler.set_text_style(font_size=35, color='black')  # Larger, black text
        
        # Create the video
        video_path = compiler.compile_story_video(test_story)
        print(f"Video created successfully: {video_path}")
        
    except Exception as e:
        print(f"Error creating video: {str(e)}")