import os
import json
from openai import OpenAI

class DeepseekNode:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
    
    def load_config(self):
        """从配置文件加载API密钥"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('api_key')
                self.base_url = config.get('base_url', 'https://api.deepseek.com')
        except Exception as e:
            print(f"Error loading config: {e}")
            self.api_key = None
            self.base_url = "https://api.deepseek.com"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "You are a helpful assistant"
                }),
            },
            "optional": {
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "创造性，随机性"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    FUNCTION = "execute"
    CATEGORY = "💎DeepAide"

    @classmethod
    def get_icon(cls):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(dir_path, "deepseek_icon.svg")
        if os.path.exists(icon_path):
            with open(icon_path, "r") as f:
                return f.read()
        return None

    def execute(self, prompt, system_prompt="You are a helpful assistant", temperature=0.7):
        if not self.api_key:
            return ("Error: Please configure your API key in config.json",)
            
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                stream=False
            )
            
            return (response.choices[0].message.content,)
        except Exception as e:
            return (f"Error: {str(e)}",)

class DeepseekAdvancedNode:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
    
    def load_config(self):
        """从配置文件加载API密钥"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('api_key')
                self.base_url = config.get('base_url', 'https://api.deepseek.com')
        except Exception as e:
            print(f"Error loading config: {e}")
            self.api_key = None
            self.base_url = "https://api.deepseek.com"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "You are a helpful assistant"
                }),
            },
            "optional": {
                "temperature": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "创造性（越大越有创意，越小越严谨）"
                }),
                "max_tokens": ("INT", {
                    "default": 2048,
                    "min": 1,
                    "max": 4096,
                    "step": 1,
                    "tooltip": "最大输出长度"
                }),
                "top_p": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "tooltip": "采样范围（影响回答的多样性）"
                }),
                "frequency_penalty": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "用词重复度（越大越不爱重复用词）"
                }),
                "presence_penalty": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "话题重复度（越大越容易换新话题）"
                }),
                "stop_sequence": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "停止标记（AI看到这个词就停止回答）"
                }),
            }
        }
    
    RETURN_TYPES = ("STRING",)
    FUNCTION = "execute"
    CATEGORY = "💎DeepAide"

    @classmethod
    def get_icon(cls):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(dir_path, "deepseek_icon.svg")
        if os.path.exists(icon_path):
            with open(icon_path, "r") as f:
                return f.read()
        return None

    def execute(self, prompt, system_prompt="You are a helpful assistant", 
                temperature=1.0, max_tokens=2048, top_p=1.0,
                frequency_penalty=0.0, presence_penalty=0.0, 
                stop_sequence=""):
        if not self.api_key:
            return ("Error: Please configure your API key in config.json",)
            
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 构建请求参数
            params = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature, 
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
                "stream": False,
                "response_format": {"type": "text"}
            }
            
            # 如果提供了stop_sequence，添加到参数中
            if stop_sequence:
                params["stop"] = [stop_sequence]
            
            response = client.chat.completions.create(**params)
            
            return (response.choices[0].message.content,)
        except Exception as e:
            return (f"Error: {str(e)}",)

class DeepseekReasonerNode:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
        self.message_history = []
    
    def load_config(self):
        """从配置文件加载API密钥"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('api_key')
                self.base_url = config.get('base_url', 'https://api.deepseek.com')
        except Exception as e:
            print(f"Error loading config: {e}")
            self.api_key = None
            self.base_url = "https://api.deepseek.com"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "clear_history": ("BOOLEAN", {
                    "default": False, 
                    "tooltip": "清除历史对话记录"
                }),
            },
            "optional": {
                "temperature": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "创造性（越大越有创意，越小越严谨）"
                }),
                "max_tokens": ("INT", {
                    "default": 2048,
                    "min": 1,
                    "max": 4096,
                    "step": 1,
                    "tooltip": "最大输出长度"
                }),
                "top_p": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "tooltip": "采样范围（影响回答的多样性）"
                }),
                "frequency_penalty": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "用词重复度（越大越不爱重复用词）"
                }),
                "presence_penalty": ("FLOAT", {
                    "default": 0.0,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "话题重复度（越大越容易换新话题）"
                })
            }
        }
    
    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("reasoning", "answer",)
    FUNCTION = "execute"
    CATEGORY = "💎DeepAide"

    @classmethod
    def get_icon(cls):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        icon_path = os.path.join(dir_path, "deepseek_icon.svg")
        if os.path.exists(icon_path):
            with open(icon_path, "r") as f:
                return f.read()
        return None

    def execute(self, prompt, clear_history=False, temperature=0.7, 
                max_tokens=2048, top_p=1.0,
                frequency_penalty=0.0, presence_penalty=0.0):
        if not self.api_key:
            return ("Error: Please configure your API key in config.json", "Error: API key not found")
        
        if clear_history:
            self.message_history = []
            
        try:
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            # 构建请求参数
            params = {
                "model": "deepseek-reasoner",
                "messages": self.message_history + [
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
                "stream": False,
                "response_format": {"type": "text"}
            }
            
            response = client.chat.completions.create(**params)
            
            reasoning = response.choices[0].message.reasoning_content
            answer = response.choices[0].message.content
            
            # 将助手的回答添加到历史记录
            self.message_history.append({"role": "user", "content": prompt})
            self.message_history.append({
                "role": "assistant",
                "content": answer
            })
            
            return (reasoning, answer,)
        except Exception as e:
            return (f"Error: {str(e)}", "Error occurred during API call")

