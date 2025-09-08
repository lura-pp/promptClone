import os
import json
import time
import psutil
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from ollama import Client
from datetime import datetime

# Load environment variables
load_dotenv()

class QAGenerator:
    def __init__(self):
        """Initialize the Q&A Generator with configuration from .env file"""
        self.input_folder = Path(os.getenv("QA_INPUT_FOLDER", "./output/chunked_output"))
        self.output_folder = Path(os.getenv("QA_OUTPUT_FOLDER", "./qa_pairs"))
        self.ollama_host = os.getenv("QA_OLLAMA_HOST", "http://localhost:11434")
        self.ollama_model = os.getenv("QA_OLLAMA_MODEL", "mistral")
        self.qa_pairs_per_chunk = int(os.getenv("QA_PAIRS_PER_CHUNK", "3"))
        
        # Create output folder if it doesn't exist
        self.output_folder.mkdir(exist_ok=True)
        
        # Initialize Ollama client
        self.ollama = Client(host=self.ollama_host)
        
        print(f"🔧 Configuration:")
        print(f"   Input folder: {self.input_folder}")
        print(f"   Output folder: {self.output_folder}")
        print(f"   Ollama host: {self.ollama_host}")
        print(f"   Ollama model: {self.ollama_model}")
        print(f"   Q&A pairs per chunk: {self.qa_pairs_per_chunk}")
        print()

    def get_gpu_usage(self):
        """Get current GPU usage using nvidia-smi"""
        try:
            result = subprocess.run(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.total', '--format=csv,noheader,nounits'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                gpu_info = []
                for line in lines:
                    parts = line.split(', ')
                    if len(parts) >= 3:
                        gpu_util = int(parts[0])
                        mem_used = int(parts[1])
                        mem_total = int(parts[2])
                        gpu_info.append({
                            'utilization': gpu_util,
                            'memory_used': mem_used,
                            'memory_total': mem_total,
                            'memory_percent': (mem_used / mem_total) * 100
                        })
                return gpu_info
        except Exception as e:
            print(f"   ⚠️ Could not get GPU info: {e}")
        return []

    def test_ollama_connection(self):
        """Test Ollama connection and monitor resource usage"""
        print("🔍 Testing Ollama connection and GPU usage...")
        
        try:
            # Get initial system stats
            cpu_before = psutil.cpu_percent(interval=1)
            memory_before = psutil.virtual_memory().percent
            gpu_before = self.get_gpu_usage()
            
            print(f"   📊 System stats before request:")
            print(f"      CPU: {cpu_before:.1f}%")
            print(f"      Memory: {memory_before:.1f}%")
            if gpu_before:
                for i, gpu in enumerate(gpu_before):
                    print(f"      GPU {i}: {gpu['utilization']}% util, {gpu['memory_percent']:.1f}% memory ({gpu['memory_used']}MB/{gpu['memory_total']}MB)")
            
            start_time = time.time()
            
            # Test with a longer, more complex request to see GPU usage
            response = self.ollama.chat(
                model=self.ollama_model,
                messages=[{"role": "user", "content": """Generate 5 detailed question-answer pairs about artificial intelligence, machine learning, and digital transformation. Each answer should be at least 100 words long and include specific technical details, benefits, and real-world applications. Format as JSON array."""}],
                options={
                    "temperature": 0.8,
                    "top_p": 0.9,
                    "num_predict": 2000,  # Force longer generation
                    "num_gpu": -1  # Use all available GPU layers
                }
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Get system stats after
            cpu_after = psutil.cpu_percent(interval=1)
            memory_after = psutil.virtual_memory().percent
            gpu_after = self.get_gpu_usage()
            
            print(f"   📊 System stats after request:")
            print(f"      CPU: {cpu_after:.1f}%")
            print(f"      Memory: {memory_after:.1f}%")
            if gpu_after:
                for i, gpu in enumerate(gpu_after):
                    print(f"      GPU {i}: {gpu['utilization']}% util, {gpu['memory_percent']:.1f}% memory ({gpu['memory_used']}MB/{gpu['memory_total']}MB)")
            
            print(f"   ⏱️ Processing time: {processing_time:.2f} seconds")
            print(f"   ✅ Connection successful!")
            print(f"   📝 Sample response: {response['message']['content'][:150]}...")
            print()
            
            return True
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            return False

    def generate_qa_pairs(self, text_chunk: str, chunk_id: str = "") -> List[Dict[str, str]]:
        """Generate Q&A pairs for a given text chunk using Ollama"""
        
        # More detailed prompt for better Q&A generation
        prompt = f"""
You are an expert assistant helping create training data for a company chatbot about Bayanat, a digital transformation and business solutions company in Jordan.

Given the following document chunk, generate exactly {self.qa_pairs_per_chunk} high-quality question-answer pairs in JSON format. 

REQUIREMENTS:
1. Questions should be natural, varied, and cover different aspects of the content
2. Answers must be accurate and based ONLY on the provided text
3. Include specific details, numbers, dates, and technical terms when available
4. Make questions that a customer or business partner might ask
5. Output must be valid JSON format

Document Chunk:
\"\"\"
{text_chunk}
\"\"\"

Output format (must be valid JSON array):
[
  {{
    "prompt": "What specific services does Bayanat provide?",
    "response": "Based on the document, Bayanat provides..."
  }},
  {{
    "prompt": "What are Bayanat's key capabilities or expertise areas?",
    "response": "According to the text, Bayanat's key capabilities include..."
  }},
  {{
    "prompt": "What industries or sectors does Bayanat work with?",
    "response": "The document indicates that Bayanat works with..."
  }}
]
"""
        
        try:
            print(f"   📝 Generating Q&A pairs for {chunk_id}...")
            
            # Monitor resource usage
            cpu_before = psutil.cpu_percent(interval=0.1)
            memory_before = psutil.virtual_memory().percent
            gpu_before = self.get_gpu_usage()
            start_time = time.time()
            
            print(f"      💻 CPU: {cpu_before:.1f}%, Memory: {memory_before:.1f}%")
            if gpu_before:
                for i, gpu in enumerate(gpu_before):
                    print(f"      🎮 GPU {i}: {gpu['utilization']}% util, {gpu['memory_percent']:.1f}% mem")
            
            response = self.ollama.chat(
                model=self.ollama_model, 
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.7,  # Add some creativity
                    "top_p": 0.9,
                    "num_predict": 1500,  # Allow longer responses
                    "num_gpu": -1,  # Use all available GPU layers
                    "repeat_penalty": 1.1  # Improve text quality
                }
            )
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            cpu_after = psutil.cpu_percent(interval=0.1)
            memory_after = psutil.virtual_memory().percent
            gpu_after = self.get_gpu_usage()
            
            print(f"      ⏱️ Processing time: {processing_time:.2f}s")
            print(f"      💻 CPU: {cpu_after:.1f}%, Memory: {memory_after:.1f}%")
            if gpu_after:
                for i, gpu in enumerate(gpu_after):
                    print(f"      🎮 GPU {i}: {gpu['utilization']}% util, {gpu['memory_percent']:.1f}% mem")
            
            # Parse the JSON response
            content = response["message"]["content"].strip()
            
            # Try to extract JSON if it's wrapped in markdown code blocks
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            if content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove ```
            
            # Clean up the content
            content = content.strip()
            
            qa_pairs = json.loads(content)
            
            # Validate the structure
            if not isinstance(qa_pairs, list):
                print(f"   ⚠️ Warning: Expected list, got {type(qa_pairs)}")
                return []
            
            # Clean and validate each Q&A pair
            validated_pairs = []
            for qa in qa_pairs:
                if isinstance(qa, dict) and "prompt" in qa and "response" in qa:
                    validated_pairs.append({
                        "prompt": str(qa["prompt"]).strip(),
                        "response": str(qa["response"]).strip()
                    })
            
            print(f"   ✅ Generated {len(validated_pairs)} valid Q&A pairs")
            return validated_pairs
            
        except json.JSONDecodeError as e:
            print(f"   ❌ JSON parsing error: {e}")
            print(f"   Raw response: {response['message']['content'][:300]}...")
            return []
        except Exception as e:
            print(f"   ❌ Failed to process chunk: {e}")
            return []

    def process_file(self, json_file_path: Path) -> bool:
        """Process a single JSON file and generate Q&A pairs"""
        print(f"📁 Processing: {json_file_path.name}")
        
        try:
            # Load the chunked data
            with open(json_file_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            
            print(f"   📊 Found {len(chunks)} chunks")
            
            qa_results = []
            
            # Process each chunk
            for i, chunk in enumerate(chunks, 1):
                print(f"   🔄 Processing chunk {i}/{len(chunks)}")
                
                # Extract text and metadata
                chunk_text = chunk.get("text", "")
                chunk_id = chunk.get("chunk_id", f"chunk_{i}")
                source_file = chunk.get("source_file", "unknown")
                
                if not chunk_text.strip():
                    print(f"   ⚠️ Skipping empty chunk {chunk_id}")
                    continue
                
                # Generate Q&A pairs for this chunk
                qas = self.generate_qa_pairs(chunk_text)
                
                # Add metadata to each Q&A pair
                for qa in qas:
                    qa_results.append({
                        "source_file": source_file,
                        "chunk_id": chunk_id,
                        "chunk_index": chunk.get("chunk_index", i-1),
                        "prompt": qa["prompt"],
                        "response": qa["response"],
                        "character_count": chunk.get("character_count", len(chunk_text)),
                        "word_count": chunk.get("word_count", len(chunk_text.split())),
                        "generated_at": datetime.now().isoformat()
                    })
                
                # Small delay and show system status between chunks
                gpu_current = self.get_gpu_usage()
                print(f"      💻 Current CPU: {psutil.cpu_percent(interval=0.1):.1f}%, Memory: {psutil.virtual_memory().percent:.1f}%")
                if gpu_current:
                    for i, gpu in enumerate(gpu_current):
                        print(f"      🎮 GPU {i}: {gpu['utilization']}% util, {gpu['memory_percent']:.1f}% mem")
                time.sleep(1)  # Increased delay to see GPU usage
            
            # Save the results to a separate file for this document
            output_filename = json_file_path.stem.replace("_extracted_vectorized_st", "_qa_pairs")
            output_file = self.output_folder / f"{output_filename}.json"
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(qa_results, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Saved {len(qa_results)} Q&A pairs to {output_file}")
            print()
            return True
            
        except Exception as e:
            print(f"   ❌ Error processing {json_file_path.name}: {e}")
            print()
            return False

    def process_all_files(self):
        """Process all JSON files in the input folder"""
        # Find all JSON files
        json_files = list(self.input_folder.glob("*.json"))
        
        if not json_files:
            print(f"❌ No JSON files found in {self.input_folder}")
            return
        
        print(f"🚀 Found {len(json_files)} files to process")
        print()
        
        # Process each file
        successful = 0
        failed = 0
        total_files = len(json_files)
        for idx, json_file in enumerate(json_files, 1):
            files_left = total_files - idx
            if self.process_file(json_file):
                successful += 1
            else:
                failed += 1
            print(f"➡️  {files_left} files left to process\n")
        # Summary
        print("📊 Processing Summary:")
        print(f"   ✅ Successfully processed: {successful} files")
        print(f"   ❌ Failed: {failed} files")
        print(f"   📁 Output folder: {self.output_folder}")


def main():
    """Main function to run the Q&A generation process"""
    print("🤖 Q&A Pairs Generator for Bayanat Chatbot Training")
    print("=" * 50)
    
    try:
        generator = QAGenerator()
        
        # Test connection first
        if not generator.test_ollama_connection():
            print("❌ Cannot connect to Ollama. Please make sure Ollama is running and the model is available.")
            return
        
        generator.process_all_files()
    except KeyboardInterrupt:
        print("\n⚠️ Process interrupted by user")
    except Exception as e:
        print(f"❌ An error occurred: {e}")


if __name__ == "__main__":
    main()
