#!/usr/bin/env python3

import requests
import json
import os
import time
import sys
from urllib.parse import urlparse

# Default Qwen configuration (from qwen-code)
DEFAULT_QWEN_API_BASE_URL = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
DEFAULT_MODEL = 'qwen3-coder-plus'
QWEN_OAUTH_CLIENT_ID = 'f0304373b74a44d2b584a3fb70ca9e56'

def load_credentials():
    """Load Qwen credentials from file"""
    home_dir = os.path.expanduser("~")
    creds_path = os.path.join(home_dir, ".qwen", "oauth_creds.json")
    
    try:
        with open(creds_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("No credentials found. Please authenticate with qwen-code first.")
        return None
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def get_api_endpoint(credentials):
    """Get the API endpoint, using resource_url if available"""
    # Check if credentials contain a custom endpoint
    if credentials and 'resource_url' in credentials and credentials['resource_url']:
        endpoint = credentials['resource_url']
        # Ensure it has a scheme
        if not urlparse(endpoint).scheme:
            endpoint = f"https://{endpoint}"
        # Ensure it has the /v1 suffix
        if not endpoint.endswith('/v1'):
            if endpoint.endswith('/'):
                endpoint += 'v1'
            else:
                endpoint += '/v1'
        return endpoint
    else:
        # Use default endpoint
        return DEFAULT_QWEN_API_BASE_URL

def make_api_call(prompt):
    """Make a direct API call to Qwen using existing credentials"""
    print("Making direct API call to Qwen...")
    
    # Load credentials
    credentials = load_credentials()
    if not credentials:
        return False
    
    access_token = credentials.get('access_token')
    if not access_token:
        print("No access token found in credentials.")
        return False
    
    # Get the correct API endpoint
    api_endpoint = get_api_endpoint(credentials)
    print(f"Using API endpoint: {api_endpoint}")
    
    # Make API call
    url = f"{api_endpoint}/chat/completions"
    payload = {
        "model": DEFAULT_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "QwenCode/1.0.0 (linux; x64)"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print("Response from Qwen:")
            print(data["choices"][0]["message"]["content"])
            print("\nDirect API call successful!")
            return True
        else:
            print(f"API call failed with status code: {response.status_code}")
            print(response.text)
            return False
            
    except requests.exceptions.Timeout:
        print("API call timed out.")
        return False
    except Exception as e:
        print(f"Error making API call: {str(e)}")
        return False

def read_file_content(file_path):
    """Read content from a file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {str(e)}")
        return None

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python3 simple_qwen_test.py \"your prompt here\"")
        print("   or: python3 simple_qwen_test.py /path/to/file")
        return
    
    # Check if the argument is a file path
    arg = sys.argv[1]
    if os.path.isfile(arg):
        # Read file content as prompt
        prompt = read_file_content(arg)
        if prompt is None:
            return
        print(f"Using content of file '{arg}' as prompt")
    else:
        # Use command line arguments as prompt
        prompt = " ".join(sys.argv[1:])
    
    print("Qwen Direct API Test")
    print("=" * 20)
    print(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    
    success = make_api_call(prompt)
    if not success:
        print("\nTest failed")

if __name__ == "__main__":
    main()