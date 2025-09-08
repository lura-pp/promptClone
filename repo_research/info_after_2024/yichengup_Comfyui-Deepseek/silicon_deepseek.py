import os
import json
import requests

class SiliconDeepseekChat:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
    
    def load_config(self):
        """从配置文件加载API密钥"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('silicon_api_key')
                self.base_url = config.get('silicon_base_url', 'https://api.siliconflow.cn/v1')
        except Exception as e:
            print(f"Error loading config: {e}")
            self.api_key = None
            self.base_url = "https://api.siliconflow.cn/v1"

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
                    "tooltip": "创造性（越大越有创意，越小越严谨）"
                }),
                "max_tokens": ("INT", {
                    "default": 512,
                    "min": 1,
                    "max": 4096,
                    "step": 1,
                    "tooltip": "最大输出长度"
                }),
                "top_p": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "tooltip": "采样范围"
                }),
                "top_k": ("INT", {
                    "default": 50,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "tooltip": "保留最高概率的K个token"
                }),
                "frequency_penalty": ("FLOAT", {
                    "default": 0.5,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "用词重复度（越大越不爱重复用词）"
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
                temperature=0.7, max_tokens=512, top_p=0.7,
                top_k=50, frequency_penalty=0.5, stop_sequence=""):
        if not self.api_key:
            return ("错误: 请在config.json中配置silicon_api_key",)
            
        try:
            url = f"{self.base_url}/chat/completions"
            
            payload = {
                "model": "deepseek-ai/DeepSeek-V3",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "frequency_penalty": frequency_penalty,
                "n": 1,
                "response_format": {"type": "text"}
            }
            
            # 如果提供了stop_sequence，添加到参数中
            if stop_sequence:
                payload["stop"] = [stop_sequence]
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()  # 检查HTTP错误
            
            result = response.json()
            return (result["choices"][0]["message"]["content"],)
            
        except requests.exceptions.RequestException as e:
            return (f"API请求错误: {str(e)}",)
        except KeyError as e:
            return (f"响应格式错误: {str(e)}",)
        except Exception as e:
            return (f"未知错误: {str(e)}",)

class SiliconDeepseekReasoner:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.load_config()
        self.message_history = []
    
    def load_config(self):
        """从配置文件加载API密钥"""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.api_key = config.get('silicon_api_key')
                self.base_url = config.get('silicon_base_url', 'https://api.siliconflow.cn/v1')
        except Exception as e:
            print(f"Error loading config: {e}")
            self.api_key = None
            self.base_url = "https://api.siliconflow.cn/v1"

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", {"multiline": True}),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": "You are a helpful assistant that can reason step by step"
                }),
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
                    "default": 512,
                    "min": 1,
                    "max": 4096,
                    "step": 1,
                    "tooltip": "最大输出长度"
                }),
                "top_p": ("FLOAT", {
                    "default": 0.7,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.1,
                    "tooltip": "采样范围"
                }),
                "top_k": ("INT", {
                    "default": 50,
                    "min": 1,
                    "max": 100,
                    "step": 1,
                    "tooltip": "保留最高概率的K个token"
                }),
                "frequency_penalty": ("FLOAT", {
                    "default": 0.5,
                    "min": -2.0,
                    "max": 2.0,
                    "step": 0.1,
                    "tooltip": "用词重复度（越大越不爱重复用词）"
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

    def execute(self, prompt, system_prompt="You are a helpful assistant that can reason step by step", 
                clear_history=False, temperature=0.7, max_tokens=512, top_p=0.7, top_k=50, frequency_penalty=0.5):
        if not self.api_key:
            return ("错误: 请在config.json中配置silicon_api_key", "错误: API密钥未配置")
        
        if clear_history:
            self.message_history = []
            
        try:
            url = f"{self.base_url}/chat/completions"
            
            payload = {
                "model": "deepseek-ai/DeepSeek-R1",
                "messages": [
                    {"role": "system", "content": system_prompt}
                ] + self.message_history + [
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "frequency_penalty": frequency_penalty,
                "n": 1,
                "response_format": {"type": "text"}
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            # 解析响应
            answer = result["choices"][0]["message"]["content"]
            reasoning = result["choices"][0]["message"].get("reasoning_content", "未提供推理过程")
            
            # 将助手的回答添加到历史记录（不包含system_prompt）
            self.message_history.append({"role": "user", "content": prompt})
            self.message_history.append({
                "role": "assistant",
                "content": answer
            })
            
            return (reasoning, answer,)
            
        except requests.exceptions.RequestException as e:
            return (f"API请求错误: {str(e)}", "请求失败")
        except KeyError as e:
            return (f"响应格式错误: {str(e)}", "格式错误")
        except Exception as e:
            return (f"未知错误: {str(e)}", "执行失败")
