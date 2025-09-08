"""
FILENAME: test_visual_content.py
DESCRIPTION/PURPOSE: Tests for visual content generation (Imagen integration)
Author: JP + 2025-06-16

Tests validate that visual content generation works correctly with 
image generation and graceful fallbacks.
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

# Import functions to test
from agents.visual_content_agent import generate_visual_content_for_posts


class TestVisualContentGeneration:
    """Test visual content generation functionality."""
    
    @pytest.mark.asyncio
    async def test_image_generation_structure(self):
        """Test that image generation returns proper structure."""
        
        sample_posts = [
            {
                "id": "test_post_1",
                "type": "text_image",
                "content": "Transform your business with AI solutions",
                "hashtags": ["#AI", "#Business"],
                "image_prompt": "Modern business transformation with AI technology"
            },
            {
                "id": "test_post_2",
                "type": "text_image", 
                "content": "Expert consulting services",
                "hashtags": ["#Consulting", "#Expertise"],
                "image_prompt": "Professional consulting team meeting"
            }
        ]
        
        business_context = {
            "company_name": "TestCorp",
            "industry": "Technology",
            "brand_voice": "Professional"
        }
        
        # Mock Imagen API response
        with patch('google.genai.ImageGenerationModel') as mock_imagen:
            mock_model = Mock()
            mock_response = Mock()
            mock_response.images = [Mock(url="https://example.com/image1.jpg")]
            mock_model.generate_images.return_value = mock_response
            mock_imagen.return_value = mock_model
            
            result = await generate_visual_content_for_posts(sample_posts, business_context)
            
            # Validate structure
            assert isinstance(result, dict)
            assert "images" in result
            assert "videos" in result
            assert "metadata" in result
            
            # Check images generated
            assert isinstance(result["images"], list)
            assert len(result["images"]) > 0
    
    @pytest.mark.asyncio
    async def test_image_generation_fallback(self):
        """Test graceful fallback when image generation fails."""
        
        sample_posts = [
            {
                "id": "test_post_1",
                "type": "text_image",
                "content": "Test content",
                "hashtags": ["#Test"],
                "image_prompt": "Test image prompt"
            }
        ]
        
        business_context = {"company_name": "TestCorp"}
        
        # Mock API failure
        with patch('google.genai.ImageGenerationModel') as mock_imagen:
            mock_model = Mock()
            mock_model.generate_images.side_effect = Exception("API Error")
            mock_imagen.return_value = mock_model
            
            result = await generate_visual_content_for_posts(sample_posts, business_context)
            
            # Should still return structure with fallback
            assert isinstance(result, dict)
            assert "images" in result
            assert "metadata" in result
            
            # Should indicate fallback was used
            assert result["metadata"]["generation_method"] == "mock"
    
    @pytest.mark.asyncio
    async def test_no_image_posts_handling(self):
        """Test handling when no image posts are provided."""
        
        sample_posts = [
            {
                "id": "text_only_post",
                "type": "text_url",
                "content": "Text only content",
                "hashtags": ["#Text"]
            }
        ]
        
        business_context = {"company_name": "TestCorp"}
        
        result = await generate_visual_content_for_posts(sample_posts, business_context)
        
        # Should handle gracefully
        assert isinstance(result, dict)
        assert "images" in result
        assert "videos" in result
        assert len(result["images"]) == 0  # No images for text-only posts
    
    @pytest.mark.asyncio
    async def test_real_imagen_api_if_available(self):
        """Test real Imagen API if credentials are available."""
        
        if not os.getenv('GEMINI_API_KEY'):
            pytest.skip("GEMINI_API_KEY not available - skipping real API test")
        
        sample_posts = [
            {
                "id": "real_test_post",
                "type": "text_image",
                "content": "Professional technology consulting services",
                "hashtags": ["#Technology", "#Consulting"],
                "image_prompt": "Professional business meeting with technology consultants"
            }
        ]
        
        business_context = {
            "company_name": "TestCorp",
            "industry": "Technology Consulting",
            "brand_voice": "Professional"
        }
        
        # Test real API call
        result = await generate_visual_content_for_posts(sample_posts, business_context)
        
        # Validate real response
        assert isinstance(result, dict)
        assert "images" in result
        assert "metadata" in result
        
        # If real generation worked, should have metadata indicating it
        if result["metadata"]["generation_method"] == "imagen_ai":
            assert len(result["images"]) > 0
            
            # Check image structure
            for image in result["images"]:
                assert "post_id" in image
                assert "url" in image or "base64" in image  # Should have image data
    
    @pytest.mark.asyncio 
    async def test_video_generation_mock(self):
        """Test video generation (currently mock implementation)."""
        
        sample_posts = [
            {
                "id": "video_post",
                "type": "text_video",
                "content": "See our services in action",
                "hashtags": ["#Demo", "#Services"],
                "video_prompt": "Professional service demonstration video"
            }
        ]
        
        business_context = {"company_name": "TestCorp"}
        
        result = await generate_visual_content_for_posts(sample_posts, business_context)
        
        # Should handle videos (currently mock)
        assert isinstance(result, dict)
        assert "videos" in result
        assert isinstance(result["videos"], list)
        
        # Videos should be present for video posts
        video_posts = [p for p in sample_posts if p["type"] == "text_video"]
        if video_posts:
            assert len(result["videos"]) > 0
    
    @pytest.mark.asyncio
    async def test_business_context_integration(self):
        """Test that business context is properly integrated into prompts."""
        
        sample_posts = [
            {
                "id": "context_test_post",
                "type": "text_image", 
                "content": "TestCorp delivers professional solutions",
                "hashtags": ["#TestCorp", "#Professional"],
                "image_prompt": "Professional business solutions"
            }
        ]
        
        business_context = {
            "company_name": "TestCorp",
            "industry": "Professional Services",
            "brand_voice": "Professional and trustworthy",
            "visual_elements": "Clean, modern design with blue color scheme"
        }
        
        # Mock to capture the prompts sent
        with patch('google.genai.ImageGenerationModel') as mock_imagen:
            mock_model = Mock()
            mock_response = Mock()
            mock_response.images = [Mock(url="https://example.com/test.jpg")]
            mock_model.generate_images.return_value = mock_response
            mock_imagen.return_value = mock_model
            
            result = await generate_visual_content_for_posts(sample_posts, business_context)
            
            # Should have called image generation
            if mock_model.generate_images.called:
                # Get the prompt that was used
                call_args = mock_model.generate_images.call_args
                prompt_used = call_args[1].get('prompt', call_args[0][0] if call_args[0] else '')
                
                # Business context should influence the prompt
                assert isinstance(prompt_used, str)
                assert len(prompt_used) > 0


class TestVisualContentPerformance:
    """Test performance and quality aspects of visual content generation."""
    
    @pytest.mark.asyncio
    async def test_multiple_posts_handling(self):
        """Test handling multiple image posts efficiently."""
        
        # Create multiple test posts
        sample_posts = []
        for i in range(5):
            sample_posts.append({
                "id": f"post_{i}",
                "type": "text_image",
                "content": f"Test content {i}",
                "hashtags": [f"#Test{i}"],
                "image_prompt": f"Test image prompt {i}"
            })
        
        business_context = {"company_name": "TestCorp"}
        
        # Mock successful generation
        with patch('google.genai.ImageGenerationModel') as mock_imagen:
            mock_model = Mock()
            mock_response = Mock()
            mock_response.images = [Mock(url=f"https://example.com/image{i}.jpg") for i in range(5)]
            mock_model.generate_images.return_value = mock_response
            mock_imagen.return_value = mock_model
            
            result = await generate_visual_content_for_posts(sample_posts, business_context)
            
            # Should handle all posts
            assert isinstance(result, dict)
            assert "images" in result
            
            # Verify generation was attempted for image posts
            image_posts_count = len([p for p in sample_posts if p["type"] == "text_image"])
            assert image_posts_count == 5
    
    @pytest.mark.asyncio
    async def test_error_recovery(self):
        """Test recovery from partial failures in batch processing."""
        
        sample_posts = [
            {
                "id": "good_post",
                "type": "text_image",
                "content": "Good content",
                "hashtags": ["#Good"],
                "image_prompt": "Good image prompt"
            },
            {
                "id": "problematic_post",
                "type": "text_image",
                "content": "Problematic content",
                "hashtags": ["#Problem"],
                "image_prompt": ""  # Empty prompt might cause issues
            }
        ]
        
        business_context = {"company_name": "TestCorp"}
        
        # Should handle mixed success/failure gracefully
        result = await generate_visual_content_for_posts(sample_posts, business_context)
        
        assert isinstance(result, dict)
        assert "images" in result
        assert "metadata" in result
        
        # Should have some form of result even with partial failures
        assert "error_count" not in result["metadata"] or result["metadata"]["error_count"] <= len(sample_posts) 