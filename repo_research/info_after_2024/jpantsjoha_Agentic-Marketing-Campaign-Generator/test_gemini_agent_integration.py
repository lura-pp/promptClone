"""
FILENAME: test_gemini_agent_integration.py
DESCRIPTION/PURPOSE: Comprehensive tests for Gemini AI integration and real content generation
Author: JP + 2025-06-16

Tests validate that Gemini integration works correctly with business context,
error handling, and end-to-end workflow execution.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, List, Any

# Import the functions we want to test
from agents.marketing_orchestrator import (
    _generate_real_social_content,
    execute_campaign_workflow,
    _format_generated_content
)
from agents.business_analysis_agent import analyze_business_urls

class TestGeminiContentGeneration:
    """Test suite for Gemini-powered content generation."""
    
    @pytest.mark.asyncio
    async def test_gemini_content_generation_structure(self, sample_business_analysis, sample_context):
        """Test that Gemini generates content with proper structure."""
        
        # Mock Gemini API response
        mock_gemini_response = Mock()
        mock_gemini_response.text = '''
        {
            "text_url_posts": [
                {
                    "content": "Transform your business with AI-driven solutions from TechInnovate Solutions. Our expert team delivers scalable cloud architectures that drive real ROI. Ready to innovate? Let's discuss your digital transformation journey.",
                    "hashtags": ["#DigitalTransformation", "#CloudSolutions", "#TechConsulting"],
                    "platform_focus": "linkedin"
                },
                {
                    "content": "Why choose TechInnovate? 10+ years of proven expertise, certified architects, and 24/7 support. Discover how we help CTOs build future-ready technology stacks.",
                    "hashtags": ["#TechLeadership", "#CloudArchitecture", "#ITConsulting"],
                    "platform_focus": "twitter"
                }
            ],
            "text_image_posts": [
                {
                    "content": "Scalable. Secure. Innovative. TechInnovate Solutions transforms how businesses leverage technology for competitive advantage.",
                    "hashtags": ["#Innovation", "#TechSolutions"],
                    "image_prompt": "Modern technology consulting team working on cloud architecture diagrams"
                }
            ],
            "text_video_posts": [
                {
                    "content": "Watch how TechInnovate's AI-driven approach revolutionizes business processes. From consultation to implementation, we deliver results.",
                    "hashtags": ["#AITransformation", "#BusinessInnovation"],
                    "video_prompt": "Professional tech consultants presenting innovative solutions"
                }
            ]
        }
        '''
        
        with patch('google.genai.Client') as mock_genai_client:
            mock_client = Mock()
            mock_client.models.generate_content.return_value = mock_gemini_response
            mock_genai_client.return_value = mock_client
            
            # Test content generation
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Validate structure
            assert isinstance(result, list)
            assert len(result) > 0
            
            # Check for different post types
            post_types = {post['type'] for post in result}
            assert 'text_url' in post_types
            assert 'text_image' in post_types
            assert 'text_video' in post_types
            
            # Validate content fields
            for post in result:
                assert 'content' in post
                assert 'hashtags' in post
                assert 'type' in post
                assert isinstance(post['hashtags'], list)
                assert len(post['content']) > 0
    
    @pytest.mark.asyncio
    async def test_gemini_business_context_integration(self, sample_business_analysis, sample_context):
        """Test that generated content properly incorporates business context."""
        
        mock_gemini_response = Mock()
        mock_gemini_response.text = '''
        {
            "text_url_posts": [
                {
                    "content": "TechInnovate Solutions delivers AI-driven business transformation with our certified cloud architects. 10+ years of expertise, 24/7 support - that's the TechInnovate difference.",
                    "hashtags": ["#TechInnovate", "#AITransformation", "#CloudConsulting"],
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
                    "content": "See how our expert team transforms IT infrastructure for lasting competitive advantage.",
                    "hashtags": ["#TechLeadership", "#ITTransformation"],
                    "video_prompt": "Technology consulting team in action"
                }
            ]
        }
        '''
        
        with patch('google.genai.Client') as mock_genai_client:
            mock_client = Mock()
            mock_client.models.generate_content.return_value = mock_gemini_response
            mock_genai_client.return_value = mock_client
            
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Check business context integration
            content_text = ' '.join([post['content'] for post in result])
            
            # Should include company name
            assert sample_business_analysis['company_name'] in content_text
            
            # Should reflect competitive advantages
            has_advantage = any(adv.lower() in content_text.lower() 
                               for adv in sample_business_analysis['competitive_advantages'])
            assert has_advantage
            
            # Should match brand voice
            assert len(result) > 0  # At least some content generated
    
    @pytest.mark.asyncio
    async def test_gemini_error_handling_fallback(self, sample_business_analysis, sample_context):
        """Test that Gemini failures gracefully fall back to enhanced content."""
        
        with patch('google.genai.Client') as mock_genai_client:
            # Simulate API failure
            mock_client = Mock()
            mock_client.models.generate_content.side_effect = Exception("API Error")
            mock_genai_client.return_value = mock_client
            
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Should still return content (fallback)
            assert isinstance(result, list)
            assert len(result) > 0
            
            # Fallback content should still be business-relevant
            content_text = ' '.join([post['content'] for post in result])
            assert sample_business_analysis['company_name'] in content_text
    
    @pytest.mark.asyncio
    async def test_gemini_prompt_construction(self, sample_business_analysis, sample_context):
        """Test that Gemini prompts are properly constructed with business context."""
        
        with patch('google.genai.Client') as mock_genai_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = '{"text_url_posts": [], "text_image_posts": [], "text_video_posts": []}'
            mock_client.models.generate_content.return_value = mock_response
            mock_genai_client.return_value = mock_client
            
            await _generate_real_social_content(sample_business_analysis, sample_context)
            
            # Verify API was called
            assert mock_client.models.generate_content.called
            
            # Get the prompt that was sent
            call_args = mock_client.models.generate_content.call_args
            prompt = call_args[1]['contents'] if 'contents' in call_args[1] else call_args[0][1]
            
            # Verify key business context is in prompt
            assert sample_business_analysis['company_name'] in prompt
            assert sample_business_analysis['industry'] in prompt
            assert sample_context['target_audience'] in prompt
    
    @pytest.mark.asyncio
    async def test_real_gemini_integration_if_available(self):
        """Test real Gemini integration if API key is available."""
        import os
        
        # Only run if API key is available
        if not os.getenv('GEMINI_API_KEY'):
            pytest.skip("GEMINI_API_KEY not available - skipping real API test")
            
        sample_business = {
            "company_name": "Test Tech Solutions",
            "industry": "Technology",
            "brand_voice": "Professional yet innovative",
            "competitive_advantages": ["Expert team", "Advanced technology"],
            "target_audience": "Small business owners",
            "value_propositions": ["Innovation", "Reliability"]
        }
        
        sample_ctx = {
            "campaign_type": "service",
            "objective": "Test content generation",
            "creativity_level": 7
        }
        
        # Test real API call
        result = await _generate_real_social_content(sample_business, sample_ctx)
        
        # Validate real response
        assert isinstance(result, list)
        assert len(result) > 0
        
        # Check content quality
        for post in result:
            assert len(post['content']) > 20  # Meaningful content
            assert len(post['hashtags']) > 0   # Has hashtags

class TestGeminiWorkflowIntegration:
    """Test suite for end-to-end workflow integration with Gemini."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_campaign_workflow_with_gemini(self):
        """Test complete campaign workflow with Gemini integration."""
        
        # Mock the URL analysis to focus on content generation
        with patch('agents.business_analysis_agent.analyze_business_urls') as mock_url_analysis:
            mock_url_analysis.return_value = {
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
            
            # Test workflow execution
            result = await execute_campaign_workflow(
                business_description="Tech company focused on productivity tools",
                objective="Increase brand awareness",
                target_audience="Business professionals", 
                campaign_type="service",
                creativity_level=7,
                business_website="https://workflowtest.com"
            )
            
            # Validate workflow results
            assert "generated_posts" in result
            assert "workflow_metadata" in result
            assert isinstance(result["generated_posts"], list)
            assert len(result["generated_posts"]) > 0
            
            # Check post structure
            for post in result["generated_posts"]:
                assert "content" in post
                assert "type" in post
                assert "hashtags" in post
                
            # Verify business context was used
            post_content = ' '.join([post['content'] for post in result["generated_posts"]])
            assert len(post_content) > 100  # Substantial content generated
    
    @pytest.mark.asyncio
    async def test_url_analysis_with_real_context(self):
        """Test URL analysis integration with business context extraction."""
        
        # Test with mock URLs to focus on analysis logic
        test_urls = ["https://example-tech-company.com", "https://example-tech-company.com/about"]
        
        with patch('agents.business_analysis_agent.aiohttp.ClientSession') as mock_session:
            # Mock successful HTTP response
            mock_response = Mock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value="""
            <html>
                <title>TechCorp - AI Solutions</title>
                <meta name="description" content="Leading AI consulting firm with 10+ years experience">
                <body>
                    <h1>TechCorp Solutions</h1>
                    <p>We provide innovative AI consulting services to enterprise clients.</p>
                    <p>Our expert team has delivered 100+ successful projects.</p>
                </body>
            </html>
            """)
            
            mock_session_instance = AsyncMock()
            mock_session_instance.get.return_value.__aenter__.return_value = mock_response
            mock_session.return_value.__aenter__.return_value = mock_session_instance
            
            # Test URL analysis
            result = await analyze_business_urls(test_urls, "comprehensive")
            
            # Validate analysis result structure
            assert "business_analysis" in result
            assert "url_insights" in result
            assert "analysis_metadata" in result
            
            # Check business analysis content
            business_analysis = result["business_analysis"]
            assert "company_name" in business_analysis
            assert "industry" in business_analysis
            assert "brand_voice" in business_analysis
    
    @pytest.mark.asyncio
    async def test_content_quality_metrics(self):
        """Test that generated content meets quality standards."""
        
        sample_business = {
            "company_name": "QualityTest Solutions",
            "industry": "Software",
            "brand_voice": "Professional and innovative",
            "competitive_advantages": ["Expert team", "Cutting-edge technology"],
            "target_audience": "Enterprise customers"
        }
        
        sample_context = {
            "campaign_type": "product",
            "objective": "Quality test",
            "creativity_level": 8
        }
        
        # Mock successful Gemini response
        with patch('google.genai.Client') as mock_genai_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.text = '''
            {
                "text_url_posts": [
                    {
                        "content": "QualityTest Solutions revolutionizes enterprise software with cutting-edge technology and expert team support. Transform your business operations today.",
                        "hashtags": ["#Innovation", "#Enterprise", "#Software"],
                        "platform_focus": "linkedin"
                    }
                ],
                "text_image_posts": [
                    {
                        "content": "Professional software solutions that deliver results for enterprise customers.",
                        "hashtags": ["#QualityTest", "#Enterprise"],
                        "image_prompt": "Modern software interface with professional design"
                    }
                ],
                "text_video_posts": [
                    {
                        "content": "See how QualityTest Solutions transforms enterprise workflows with innovative technology.",
                        "hashtags": ["#Innovation", "#Transformation"],
                        "video_prompt": "Professional software demonstration"
                    }
                ]
            }
            '''
            mock_client.models.generate_content.return_value = mock_response
            mock_genai_client.return_value = mock_client
            
            result = await _generate_real_social_content(sample_business, sample_context)
            
            # Quality metrics validation
            for post in result:
                # Content length check
                assert len(post['content']) >= 50, "Content should be substantial"
                assert len(post['content']) <= 500, "Content should be concise"
                
                # Hashtag quality
                assert len(post['hashtags']) >= 2, "Should have sufficient hashtags"
                assert len(post['hashtags']) <= 10, "Should not have excessive hashtags"
                
                # Content relevance
                content_lower = post['content'].lower()
                assert any(word in content_lower for word in ['qualitytest', 'solution', 'enterprise']), \
                    "Content should be business-relevant"

class TestGeminiPerformanceAndReliability:
    """Test suite for Gemini performance and reliability aspects."""
    
    @pytest.mark.asyncio
    async def test_gemini_response_time_acceptable(self, sample_business_analysis, sample_context):
        """Test that Gemini responses come back in reasonable time."""
        
        import time
        
        with patch('google.genai.Client') as mock_genai_client:
            # Simulate realistic response time
            def slow_response(*args, **kwargs):
                time.sleep(0.1)  # 100ms simulated delay
                mock_resp = Mock()
                mock_resp.text = '{"text_url_posts": [], "text_image_posts": [], "text_video_posts": []}'
                return mock_resp
            
            mock_client = Mock()
            mock_client.models.generate_content.side_effect = slow_response
            mock_genai_client.return_value = mock_client
            
            start_time = time.time()
            result = await _generate_real_social_content(sample_business_analysis, sample_context)
            end_time = time.time()
            
            # Should complete within reasonable time (5 seconds for test)
            assert (end_time - start_time) < 5.0
            assert isinstance(result, list)
    
    @pytest.mark.asyncio
    async def test_gemini_json_parsing_robustness(self, sample_business_analysis, sample_context):
        """Test handling of malformed JSON responses from Gemini."""
        
        malformed_responses = [
            '{"text_url_posts": [{"content": "Test", "hashtags": ["#test"]}]',  # Missing closing brace
            'Invalid JSON response from model',  # No JSON at all
            '{"text_url_posts": "not_an_array"}',  # Wrong data type
            ''  # Empty response
        ]
        
        for malformed_response in malformed_responses:
            with patch('google.genai.Client') as mock_genai_client:
                mock_client = Mock()
                mock_response = Mock()
                mock_response.text = malformed_response
                mock_client.models.generate_content.return_value = mock_response
                mock_genai_client.return_value = mock_client
                
                # Should handle gracefully and fall back
                result = await _generate_real_social_content(sample_business_analysis, sample_context)
                
                # Should still return content (fallback)
                assert isinstance(result, list)
                assert len(result) > 0
    
    @pytest.mark.asyncio 
    async def test_gemini_api_key_handling(self):
        """Test proper handling of missing or invalid API keys."""
        
        # Test with no API key
        with patch.dict('os.environ', {}, clear=True):
            # Remove GEMINI_API_KEY from environment
            sample_business = {"company_name": "Test Corp"}
            sample_context = {"campaign_type": "service"}
            
            result = await _generate_real_social_content(sample_business, sample_context)
            
            # Should fall back gracefully
            assert isinstance(result, list)
            assert len(result) > 0 