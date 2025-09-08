#!/usr/bin/env python3
"""
Comprehensive GPU/CPU test for Ollama
This script will test and validate GPU usage more thoroughly
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Add the current directory to Python path so we can import generate_qa
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def check_system_info():
    """Check system information"""
    print("🔍 System Information Check")
    print("-" * 30)
    
    # Check NVIDIA drivers
    try:
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ NVIDIA drivers detected")
            lines = result.stdout.split('\n')
            for line in lines:
                if 'CUDA Version' in line:
                    print(f"   {line.strip()}")
                elif 'GeForce' in line or 'RTX' in line or 'GTX' in line:
                    print(f"   {line.strip()}")
        else:
            print("❌ NVIDIA drivers not working")
    except:
        print("❌ NVIDIA drivers not found")
    
    # Check Ollama
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Ollama CLI detected")
            print("   Available models:")
            for line in result.stdout.split('\n'):
                if line.strip() and not line.startswith('NAME'):
                    print(f"   - {line.strip()}")
        else:
            print("❌ Ollama CLI not working")
    except:
        print("❌ Ollama CLI not found")
    
    # Check environment variables
    print("\n🔧 Environment Variables:")
    for var in ['CUDA_VISIBLE_DEVICES', 'CUDA_DEVICE_ORDER']:
        value = os.environ.get(var, 'Not set')
        print(f"   {var}: {value}")
    
    print()

def test_ollama_performance():
    """Test Ollama performance with different configurations"""
    print("🚀 Ollama Performance Test")
    print("-" * 30)
    
    from generate_qa import QAGenerator
    
    # Test 1: Default configuration
    print("Test 1: Default configuration")
    generator = QAGenerator()
    
    # Test 2: Force CPU mode
    print("\nTest 2: Force CPU mode")
    generator_cpu = QAGenerator()
    generator_cpu.use_gpu = False
    os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
    
    # Test short generation for both
    test_prompt = "What is machine learning? Answer in 2 sentences."
    
    for name, gen in [("GPU", generator), ("CPU", generator_cpu)]:
        try:
            print(f"\n   Testing {name} mode...")
            start_time = time.time()
            
            response = gen.ollama.chat(
                model=gen.ollama_model,
                messages=[{"role": "user", "content": test_prompt}],
                options={
                    "num_gpu": -1 if gen.use_gpu else 0,
                    "num_predict": 100,
                    "temperature": 0.7
                }
            )
            
            duration = time.time() - start_time
            print(f"   ✅ {name} test completed in {duration:.2f} seconds")
            print(f"   📝 Response: {response['message']['content'][:100]}...")
            
        except Exception as e:
            print(f"   ❌ {name} test failed: {e}")

def main():
    """Main test function"""
    print("🧪 Comprehensive Ollama GPU/CPU Test")
    print("=" * 50)
    
    # System info check
    check_system_info()
    
    # Performance test
    test_ollama_performance()
    
    print("\n📊 Test completed!")
    print("\nIf GPU tests are slow or show low utilization:")
    print("1. Make sure Ollama was built with GPU support")
    print("2. Check if your model supports GPU acceleration")
    print("3. Try: ollama pull llama2 (for a GPU-optimized model)")
    print("4. Restart Ollama service: ollama serve")

if __name__ == "__main__":
    main()
