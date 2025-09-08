import requests
import re
import os
import time
import subprocess  
from git import Repo, GitCommandError
from pathlib import Path
import json

SEARCH_KEYWORDS = [
    "LLM assistant",
    "AI tool calling",
    "prompt engineering",
    "ChatGPT prompt",
    "AI office assistant",
    "AI learning assistant",
    "language model prompt",
    "system prompt",
    "tool calling LLM"
]

SEARCH_KEYWORDS = [
    # 原始关键词
    "LLM assistant",
    "AI tool calling",
    "prompt engineering",
    "ChatGPT prompt",
    "AI office assistant",
    "AI learning assistant",
    "language model prompt",
    "system prompt",
    "tool calling LLM",

    # 通用 LLM / prompt / agent
    "LLM",
    "GPT",
    "LLM application",
    "LLM framework",
    "LLM agent",
    "AI agent",
    "AI assistant",
    "virtual assistant",
    "AI copilot",
    "coding assistant",
    "AI chatbot",
    "chatbot LLM",
    "chatbot prompt",
    "AI conversation",
    "LLM chatbot",
    "prompt-based AI",
    "prompt optimization",
    "prompt template",
    "prompt library",
    "prompt design",
    "instruction tuning",
    "few-shot prompt",
    "context prompt",
    "AI workflow",
    "AI automation",
    "AI integration",
    "tool-augmented LLM",
    "retrieval augmented generation",
    "RAG LLM",
    "langchain",
    "llamaindex",
    "autogen",
    "AI orchestration",
    "multi-agent LLM",

    # OpenAI 系相关
    "openai client",
    "openai wrapper",
    "gpt api",
    "chatgpt api",
    "gpt agent",
    "gpt assistant",

    # 其他厂商 LLM API
    "deepseek api",
    "deepseek llm",
    "deepseek chatbot",
    "ali llm",
    "ali tongyi",
    "qwen api",
    "qwen llm",
    "baidu wenxin",
    "ernie bot",
    "zhipu glm",
    "glm api",
    "anthropic claude",
    "claude api",
    "xunfei spark",
    "sparkdesk api",
    "google gemini",
    "gemini api",
    "mistral api",
    "mistral llm",
    "cohere api",
    "cohere llm"
]



MAX_REPOS = 1000 
MIN_STARS = 5
OUTPUT_FILE = "llm_prompt_stats.csv"

GITHUB_TOKEN = "YOUR_GITHUB_KEY"

def search_github_repos(keywords, min_stars, max_repos):
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    repos = []
    for keyword in keywords:
        query = f"{keyword} stars:>={min_stars}"
        url = f"https://api.github.com/search/repositories?q={query}&per_page={max_repos}"
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"API错误 for {keyword}: {response.status_code}")
            print(f"响应内容: {response.text}")
            continue
        data = response.json()
        for item in data.get('items', []):
            repo_info = {
                'name': item['full_name'],
                'stars': item['stargazers_count'],
                'url': item['html_url'],
                'clone_url': item['clone_url']
            }
            if repo_info not in repos: 
                repos.append(repo_info)
        time.sleep(0.1) 
    return repos

def clone_repo_with_subprocess(repo_clone_url, temp_dir):
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", repo_clone_url, temp_dir],
            capture_output=True,
            text=True,
            timeout=300  
        )
        if result.returncode != 0:
            print(f"克隆失败: {repo_clone_url}")
            print(f"错误输出: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"克隆超时: {repo_clone_url}")
        return False
    except Exception as e:
        print(f"克隆异常: {repo_clone_url}, 错误: {str(e)}")
        return False

def count_prompts_in_repo(repo_clone_url, temp_dir="temp_repo"):
    prompt_count = 0
    try:
        
        if not os.path.exists(temp_dir):    
            if not clone_repo_with_subprocess(repo_clone_url, temp_dir):
                return 0
        
        patterns = [
            r'prompt\s*[=:]\s*["\'](.*?)["\']',  # 匹配 prompt = "..." 或 prompt: "..."
            r'<system>(.*?)</system>',  # XML系统提示
            r'<user>(.*?)</user>',  # XML用户提示
            r'{"prompt":\s*"(.*?)"}',  # JSON格式
            r'system_prompt\s*[=:]\s*["\'](.*?)["\']',  # 系统提示变量
            r'### Instruction:\s*(.*?)(###|$)',  # 常见指令模式
        ]
        
        info = dict()
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith(('.py', '.js', '.json', '.txt', '.md', '.xml', '.yaml', '.yml')): 
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for pattern in patterns:
                                matches = re.findall(pattern, content, re.DOTALL)
                                prompt_count += len(matches)
                                
                                if len(matches) != 0:
                                    info[file] = len(matches)
                                    
                                    if not os.path.exists(f"info/{temp_dir.split('/')[1]}"):
                                        os.mkdir(f"info/{temp_dir.split('/')[1]}")
                                        
                                    with open(f"info/{temp_dir.split('/')[1]}/{file}", 'w') as ff:
                                        ff.write(content)
                                
                    except UnicodeDecodeError:
                        continue 
                    except Exception as e:
                        print(f"读取文件 {file_path} 时出错: {str(e)}")
                        
        if not os.path.exists(f"info/{temp_dir.split('/')[1]}"):
            os.mkdir(f"info/{temp_dir.split('/')[1]}")
        with open(f'info/{temp_dir.split('/')[1]}/AAA_info.json', 'w') as ff:
            json.dump(info, ff, indent=4)
    except Exception as e:
        print(f"处理仓库 {repo_clone_url} 时发生异常: {str(e)}")
    return prompt_count

def main():
    repos = search_github_repos(SEARCH_KEYWORDS, MIN_STARS, MAX_REPOS)
    print(f"找到 {len(repos)} 个仓库")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("Repository,Stars,Prompt_Count,URL\n")
        for repo in repos:
            print(f"处理仓库: {repo['name']} (stars: {repo['stars']})")
            prompt_count = count_prompts_in_repo(repo['clone_url'], f"repos/{repo['name'].replace('/', '_')}")
            f.write(f"{repo['name']},{repo['stars']},{prompt_count},{repo['url']}\n")
            time.sleep(0.5)
    print(f"结果已保存到 {OUTPUT_FILE}")

if __name__ == "__main__":
    for i in range(2):
        try:
            main()
        except:
            continue