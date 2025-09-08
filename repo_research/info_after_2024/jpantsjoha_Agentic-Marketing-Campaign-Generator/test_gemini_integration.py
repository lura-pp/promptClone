"""
FILENAME: test_gemini_integration.py
DESCRIPTION/PURPOSE: Tests for Gemini AI integration and real content generation
Author: JP + 2025-06-16

Validates Gemini integration works correctly with business context,
error handling, and actual API calls when credentials are available.
"""

import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

# Import functions to test
from agents.marketing_orchestrator import execute_campaign_workflow, _generate_real_social_content
from agents.business_analysis_agent import analyze_business_urls


class TestGeminiContentGeneration:
    """Test Gemini-powered content generation functionality."""
    
    @pytest.mark.asyncio
    async def test_content_generation_with_business_context(self, sample_business_analysis, sample_context):
        """Test that content generation incorporates business context correctly."""
        
        # Mock Gemini response with valid JSON
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = '''{
                "text_url_posts": [
                    {
                        "content": "TechInnovate Solutions delivers cloud expertise with 10+ years of proven results. Transform your IT infrastructure today.",
                        "hashtags": ["#TechInnovate", "#CloudSolutions", "#ITTransformation"],
                        "platform_focus": "linkedin"
                    }
                ],
                "text_image_posts": [
                    {
                        "content": "Professional technology consulting that scales with your business needs.",
                        "hashtags": ["#TechConsulting", "#ScalableSolutions"],
                        "image_prompt": "Professional technology consulting visualization"
                    }
                ],
                "text_video_posts": [
                    {
                        "content": "See how our certified architects transform business operations.",
                        "hashtags": ["#TechLeadership", "#Innovation"],
                        "video_prompt": "Technology consulting team working"
                    }
                ]
            }'''
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            # Test content generation
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Validate structure
            assert isinstance(result, list)
            assert len(result) >= 3  # Should have multiple post types
            
            # Check content incorporates business context
            all_content = ' '.join([post['content'] for post in result])
            assert sample_business_analysis['company_name'] in all_content
            
            # Validate post structure
            for post in result:
                assert 'content' in post
                assert 'hashtags' in post
                assert 'type' in post
                assert len(post['content']) > 0
                assert isinstance(post['hashtags'], list)
    
    @pytest.mark.asyncio
    async def test_gemini_error_fallback(self, sample_business_analysis, sample_context):
        """Test graceful fallback when Gemini API fails."""
        
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_client.models.generate_content.side_effect = Exception("API Error")
            mock_client_class.return_value = mock_client
            
            # Should handle error gracefully
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Should still return content (fallback)
            assert isinstance(result, list)
            assert len(result) > 0
            
            # Content should still be business-relevant
            all_content = ' '.join([post['content'] for post in result])
            assert sample_business_analysis['company_name'] in all_content
    
    @pytest.mark.asyncio
    async def test_malformed_json_handling(self, sample_business_analysis, sample_context):
        """Test handling of malformed JSON responses."""
        
        malformed_responses = [
            '{"text_url_posts": [{"content": "Test"}',  # Invalid JSON
            'Plain text response',  # No JSON
            '{"wrong_structure": "data"}',  # Wrong structure
            ''  # Empty response
        ]
        
        for malformed_response in malformed_responses:
            with patch('google.genai.Client') as mock_client_class:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.text = malformed_response
                mock_client.models.generate_content.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                # Should handle gracefully
                result = await _generate_real_social_content(sample_business_analysis, sample_context)
                
                assert isinstance(result, list)
                assert len(result) > 0
    
    @pytest.mark.asyncio
    async def test_real_gemini_api_if_available(self):
        """Test real Gemini API if credentials are available."""
        
        if not os.getenv('GEMINI_API_KEY'):
            pytest.skip("GEMINI_API_KEY not available - skipping real API test")
        
        # Use simple test data
        business_analysis = {
            "company_name": "TestCorp Solutions",
            "industry": "Technology",
            "brand_voice": "Professional",
            "competitive_advantages": ["Expert team", "Quality service"],
            "target_audience": "Business owners",
            "value_propositions": ["Innovation", "Reliability"]
        }
        
        context = {
            "campaign_type": "service",
            "objective": "Test real API integration",
            "target_audience": "Business owners",
            "creativity_level": 7
        }
        
        # Test real API call
        result = await _generate_real_social_content(business_analysis, context)
        
        # Validate real response
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check content quality
        for post in result:
            assert len(post['content']) > 20  # Meaningful content
            assert 'hashtags' in post
            assert len(post['hashtags']) > 0


class TestWorkflowIntegration:
    """Test end-to-end workflow integration."""
    
    @pytest.mark.asyncio
    async def test_campaign_workflow_execution(self):
        """Test complete campaign workflow execution."""
        
        # Mock URL analysis to focus on content generation
        with patch('agents.business_analysis_agent.analyze_business_urls') as mock_analysis:
            mock_analysis.return_value = {
                "business_analysis": {
                    "company_name": "WorkflowTest Corp",
                    "industry": "Technology",
                    "brand_voice": "Professional",
                    "competitive_advantages": ["Innovation", "Quality"],
                    "target_audience": "Business professionals",
                    "value_propositions": ["Efficiency", "Reliability"]
                },
                "url_insights": {},
                "analysis_metadata": {"ai_analysis_used": True}
            }
            
            # Test workflow
            result = await execute_campaign_workflow(
                business_description="Tech company",
                objective="Increase awareness",
                target_audience="Business professionals",
                campaign_type="service",
                creativity_level=7,
                business_website="https://example.com"
            )
            
            # Validate results
            assert "generated_posts" in result
            assert "workflow_metadata" in result
            assert isinstance(result["generated_posts"], list)
            assert len(result["generated_posts"]) > 0
    
    @pytest.mark.asyncio
    async def test_url_analysis_functionality(self):
        """Test URL analysis with mocked HTTP responses."""
        
        with patch('agents.business_analysis_agent.aiohttp.ClientSession') as mock_session:
            # Create properly structured mock
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="""
                <html>
                    <title>Test Company - Solutions</title>
                    <meta name="description" content="Professional consulting services">
                    <body>
                        <h1>Test Company</h1>
                        <p>We provide consulting services to businesses.</p>
                    </body>
                </html>
            """)
            
            # Setup the async context manager properly
            mock_session_instance = AsyncMock()
            mock_session_instance.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            
            # Test URL analysis
            result = await analyze_business_urls(["https://example.com"], "comprehensive")
            
            # Validate result structure
            assert "business_analysis" in result
            assert "url_insights" in result
            assert "analysis_metadata" in result


class TestPerformanceAndReliability:
    """Test performance and reliability aspects."""
    
    @pytest.mark.asyncio
    async def test_content_quality_standards(self, sample_business_analysis, sample_context):
        """Test that generated content meets quality standards."""
        
        # Mock good quality response
        with patch('google.genai.Client') as mock_client_class:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = '''{
                "text_url_posts": [
                    {
                        "content": "TechInnovate Solutions transforms businesses with cutting-edge cloud architecture and certified expertise. Our 10+ years of proven results speak for themselves.",
                        "hashtags": ["#TechInnovate", "#CloudSolutions", "#DigitalTransformation"],
                        "platform_focus": "linkedin"
                    }
                ],
                "text_image_posts": [
                    {
                        "content": "Professional technology consulting that delivers measurable business results.",
                        "hashtags": ["#TechConsulting", "#BusinessResults"],
                        "image_prompt": "Professional consulting team presentation"
                    }
                ],
                "text_video_posts": [
                    {
                        "content": "Watch how TechInnovate's certified architects deliver transformation projects on time and on budget.",
                        "hashtags": ["#Innovation", "#TechLeadership"],
                        "video_prompt": "Technology consultants in action"
                    }
                ]
            }'''
            mock_client.models.generate_content.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Quality checks
            for post in result:
                # Content length checks
                assert len(post['content']) >= 50, "Content should be substantial"
                assert len(post['content']) <= 500, "Content should be concise"
                
                # Hashtag quality
                assert len(post['hashtags']) >= 2, "Should have sufficient hashtags"
                assert len(post['hashtags']) <= 10, "Should not be hashtag spam"
                
                # Business relevance
                content_lower = post['content'].lower()
                company_mentioned = any(
                    word in content_lower 
                    for word in ['techinnovate', 'solutions', 'business', 'technology']
                )
                assert company_mentioned, "Content should be business-relevant"
    
    @pytest.mark.asyncio
    async def test_no_api_key_fallback(self):
        """Test behavior when no API key is provided."""
        
        # Remove API key from environment
        with patch.dict('os.environ', {}, clear=True):
            business_analysis = {
                "company_name": "TestCorp",
                "industry": "Technology",
                "brand_voice": "Professional",
                "competitive_advantages": ["Quality"],
                "target_audience": "Businesses"
            }
            
            context = {
                "campaign_type": "service",
                "objective": "Test fallback",
                "creativity_level": 7
            }
            
            # Should still work with fallback
            result = await _generate_real_social_content(business_analysis, context)
            
            assert isinstance(result, list)
            assert len(result) > 0
            
            # Should include business context even in fallback
            all_content = ' '.join([post['content'] for post in result])
            assert business_analysis['company_name'] in all_content 