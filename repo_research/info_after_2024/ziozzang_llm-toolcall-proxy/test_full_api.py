#!/usr/bin/env python3
"""
Test all OpenAI API endpoints through the proxy server
"""

import json
import requests
import time

def test_endpoint(method, endpoint, data=None, description=""):
    """Test a single endpoint"""
    print(f"\n=== Testing {method} {endpoint} ===")
    if description:
        print(f"Description: {description}")
    
    try:
        if method.upper() == 'GET':
            response = requests.get(f"http://localhost:5000{endpoint}", timeout=10)
        elif method.upper() == 'POST':
            response = requests.post(f"http://localhost:5000{endpoint}", json=data, timeout=30)
        else:
            print(f"❌ Unsupported method: {method}")
            return False
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print("✅ Response received (JSON)")
                
                # Show first few lines of response
                response_str = json.dumps(result, indent=2)
                lines = response_str.split('\n')
                if len(lines) > 10:
                    print('\n'.join(lines[:10]) + '\n  ... (truncated)')
                else:
                    print(response_str)
                    
                return True
            except json.JSONDecodeError:
                print("Response (non-JSON):")
                print(response.text[:200] + ("..." if len(response.text) > 200 else ""))
                return True
        else:
            print(f"❌ HTTP error: {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    print("Testing Full OpenAI API Compatibility")
    print("=" * 50)
    
    # Test health endpoint
    health_ok = test_endpoint('GET', '/health', description="Proxy health check")
    
    if not health_ok:
        print("\n❌ Proxy server is not running. Please start it first:")
        print("python app.py")
        return
    
    # Test /v1/models
    models_ok = test_endpoint('GET', '/v1/models', description="List available models")
    
    # Test /v1/chat/completions (with tool call conversion)
    chat_data = {
        "model": "glm-4.5-air-hi-mlx",
        "messages": [
            {"role": "user", "content": "Tell me about Python programming"}
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "fetch_wikipedia_content",
                    "description": "Fetch Wikipedia content",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_query": {"type": "string"}
                        },
                        "required": ["search_query"]
                    }
                }
            }
        ]
    }
    chat_ok = test_endpoint('POST', '/v1/chat/completions', chat_data, 
                           "Chat completions with tool calls (GLM conversion)")
    
    # Test /v1/chat/completions (without tools)
    simple_chat_data = {
        "model": "glm-4.5-air-hi-mlx",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"}
        ]
    }
    simple_chat_ok = test_endpoint('POST', '/v1/chat/completions', simple_chat_data,
                                  "Simple chat completions (no tools)")
    
    # Test /v1/completions
    completions_data = {
        "model": "glm-4.5-air-hi-mlx",
        "prompt": "The future of AI is",
        "max_tokens": 50
    }
    completions_ok = test_endpoint('POST', '/v1/completions', completions_data,
                                  "Text completions")
    
    # Test /v1/embeddings
    embeddings_data = {
        "model": "glm-4.5-air-hi-mlx",
        "input": "Hello world"
    }
    embeddings_ok = test_endpoint('POST', '/v1/embeddings', embeddings_data,
                                 "Text embeddings")
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print(f"Health Check: {'✅ PASS' if health_ok else '❌ FAIL'}")
    print(f"/v1/models: {'✅ PASS' if models_ok else '❌ FAIL'}")
    print(f"/v1/chat/completions (with tools): {'✅ PASS' if chat_ok else '❌ FAIL'}")
    print(f"/v1/chat/completions (simple): {'✅ PASS' if simple_chat_ok else '❌ FAIL'}")
    print(f"/v1/completions: {'✅ PASS' if completions_ok else '❌ FAIL'}")
    print(f"/v1/embeddings: {'✅ PASS' if embeddings_ok else '❌ FAIL'}")
    
    all_passed = all([health_ok, models_ok, chat_ok, simple_chat_ok, completions_ok, embeddings_ok])
    
    if all_passed:
        print("\n🎉 All OpenAI API endpoints are working!")
        print("The proxy server is fully compatible with OpenAI clients.")
    else:
        print("\n⚠️  Some endpoints failed. Check the backend LM Studio server:")
        print("- Make sure LM Studio is running on port 8888")
        print("- Ensure GLM model is loaded")
        print("- Check that all endpoints are supported by your backend")

if __name__ == '__main__':
    main()