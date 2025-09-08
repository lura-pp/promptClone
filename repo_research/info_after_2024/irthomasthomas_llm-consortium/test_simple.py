#!/usr/bin/env python3

# Simple test with gemini-2.5-flash-preview-04-17 for the new judging methods

import subprocess
import tempfile
import json

def test_pick_one():
    print("=== Testing pick-one method ===")
    
    # Create a simple prompt
    prompt = "What is 2+2?"
    
    # Test if we can run the consortium with pick-one
    try:
        result = subprocess.run([
            'llm', 'consortium', 'run',
            '--model', 'gemini/gemini-2.5-flash-preview-04-17:2',
            '--arbiter', 'gemini/gemini-2.5-flash-preview-04-17', 
            '--judging-method', 'pick-one',
            '--max-iterations', '1',
            prompt
        ], capture_output=True, text=True, cwd='.')
        
        print(f"Exit code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
            
    except Exception as e:
        print(f"Test failed with exception: {e}")

def test_rank():
    print("=== Testing rank method ===")
    
    # Create a simple prompt
    prompt = "What is 3+3?"
    
    # Test if we can run the consortium with rank
    try:
        result = subprocess.run([
            'llm', 'consortium', 'run',
            '--model', 'gemini/gemini-2.5-flash-preview-04-17:2',
            '--arbiter', 'gemini/gemini-2.5-flash-preview-04-17', 
            '--judging-method', 'rank',
            '--max-iterations', '1',
            prompt
        ], capture_output=True, text=True, cwd='.')
        
        print(f"Exit code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        if result.stderr:
            print(f"Stderr: {result.stderr}")
            
    except Exception as e:
        print(f"Test failed with exception: {e}")

if __name__ == "__main__":
    test_pick_one()
    print()
    test_rank()
