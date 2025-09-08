"""An API library for sider.ai, providing alternative access to ChatGPT, Gemini, Claude, and other models. \
国内访问ChatGPT、Gemini、Claude的替代解决方案，访问sider.ai的API请求库。
For the documentation, see github.com/qfcy/sider-ai-api.
"""
import sys,os,json,traceback,pprint
import gzip,bz2,zlib
from warnings import warn
from urllib.parse import unquote
import requests
try:import brotli # 处理brotli压缩格式
except ImportError:brotli=None

__version__="1.0.2"

ORIGIN="chrome-extension://dhoenijjpgpeimemopealfcbiecgceod"
TIMEZONE="Asia/Shanghai"
APP_NAME="ChitChat_Edge_Ext"
APP_VERSION="4.40.0"

DEFAULT_TOKEN_FILE="_token.json"
COOKIE_TEMPLATE='token=Bearer%20{token}; '
'refresh_token=discard; '
'userinfo-avatar=https://chitchat-avatar.s3.amazonaws.com/default-avatar-14.png; '
'userinfo-name=User; userinfo-type=phone; '

HEADER={ # 从浏览器的开发工具复制获得
 'Accept': '*/*',
 'Accept-Encoding': 'gzip, deflate, br, zstd',
 'Accept-Language': 'zh-CN,zh;q=0.9,en,en-US;q=0.8,en-GB;q=0.7,ja;q=0.6',
 'Cache-Control': 'no-cache',
 'Origin': ORIGIN,
 'Pragma': 'no-cache',
 'Sec-Fetch-Dest': 'empty',
 'Sec-Fetch-Mode': 'cors',
 'Sec-Fetch-Site': 'none',
 'sec-ch-ua': '"Chromium";v="133", "Microsoft Edge";v="133", "Not?A_Brand";v="99"',
 'sec-ch-ua-mobile': '?0',
 'sec-ch-ua-platform': '"Windows"',
 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
               '(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 '
               'Edg/133.0.0.0'
}

MODELS=["sider", # Sider Fusion
    "gpt-4o-mini",
    "claude-3-haiku",
    "claude-3.5-haiku",
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "llama-3", # llama 3.1 70B
    "llama-3.3-70b",
    "deepseek-chat", # deepseek-v3
    "deepseek-r1-distill-llama-70b" # deepseek r1 70B
]
ADVANCED_MODELS=["gpt-4o",
"claude-3.5-sonnet",
"gemini-1.5-pro",
"llama-3.1-405b",
"o1-mini",
"o1", # o1
"deepseek-reasoner" # deepseek-r1
]
def normpath(path):
    # 重写os.path.normpath。规范化Windows路径，如去除两端的双引号等
    path=os.path.normpath(path).strip('"')
    if path.endswith(':'): # 如果路径是盘符，如 C:
        path += '\\'
    return path

def parse_cookie(cookie):
    cookie_dict = {}
    pairs = cookie.split(';')

    for pair in pairs:
        # 去除前后空格
        pair = pair.strip()
        if '=' in pair:
            # 按等号分割键和值
            key, value = pair.split('=', 1)  # 只从头开始分割一次
            value = unquote(value.strip())
            cookie_dict[key.strip()] = value  # 去除空格并存入字典

    return cookie_dict

def upload_image(filename,header):
    url="https://api1.sider.ai/api/v1/imagechat/upload"
    header = header.copy()
    #header["content-type"] = "multipart/form-data"
    #header["accept-encoding"] = "gzip, deflate"
    with open(filename, 'rb') as img:
        files = {'file': ("ocr.jpg",img,'application/octet-stream')}  # file 应与API要求的字段名一致
        response = requests.post(url, headers=header, files=files)
        if response.status_code!=200:
            # respose.text可能过长 (如果遇到了Cloudflare验证等)，因此截取前1024个字符
            raise Exception({"error": response.status_code, "message": response.text[:1024]})
    coding=response.headers.get('Content-Encoding')
    if not response.content.startswith(b"{") and coding is not None:
        decompress=None
        if coding == 'deflate':
            decompress=zlib.decompress
        elif coding == 'gzip':decompress=gzip.decompress
        elif coding == 'bzip2':decompress=bz2.decompress
        elif brotli is not None and coding == 'br':
            decompress=brotli.decompress
        data=decompress(response.content)
    else:
        data=response.content
    return json.loads(data.decode("utf-8"))

class Session:
    def __init__(self,token=None,context_id="",cookie=None,update_info_at_init=True):
        if token is None:
            if cookie is None:
                if not os.path.isfile(DEFAULT_TOKEN_FILE):
                    raise OSError(f"{DEFAULT_TOKEN_FILE} is required since neither token nor cookie is provided")
                with open(DEFAULT_TOKEN_FILE,encoding="utf-8") as f:
                    config=json.load(f)
                    token=config.get("token")
                    cookie=config.get("cookie")
                if token is None and cookie is None:
                    raise ValueError(f"Neither token nor cookie is provided in {DEFAULT_TOKEN_FILE}")
        if token is None:
            token=parse_cookie(cookie).get("token")
            if token is None:
                raise ValueError("token is not provided in cookie")
            if token.startswith("Bearer "):
                token=token[7:] # token不包含头部的Bearer
        self.context_id=context_id
        self.total=self.remain=None # 总/剩下调用次数
        self.advanced_total=self.advanced_remain=None # 高级模型的调用次数
        self.header=HEADER.copy()
        self.header['authorization']=f'Bearer {token}'
        if cookie is None:
            cookie=COOKIE_TEMPLATE.format(token=token)
        self.header['Cookie']=cookie
        if update_info_at_init:
            try:self.update_userinfo()
            except Exception as err:
                warn(f"Failed to get user info ({type(err).__name__}): {err}")
    def update_userinfo(self):
        url="https://api3.sider.ai/api/v1/completion/limit/user"
        params = {
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "tz_name": TIMEZONE
        }
        response = requests.get(url, params=params, headers=self.header)
        response.raise_for_status()
        data = response.json()
        self.total=data["data"]["basic_credit"]["count"] or self.total
        self.remain=data["data"]["basic_credit"]["remain"] or self.remain
        self.advanced_total=data["data"]["advanced_credit"]["count"] or self.advanced_total
        self.advanced_remain=data["data"]["advanced_credit"]["remain"] or self.advanced_remain
    def get_text(self,url,header,payload,deep_search=False):
        # 一个生成器，获取输出结果
        resp = requests.post(url, headers=header, json=payload, stream=True)
        resp.raise_for_status()
        for line_raw in resp.iter_lines():
            if not line_raw.strip():continue
            try:
                # 解析每一行的数据
                line = line_raw.decode("utf-8")
                if payload.get("stream",True):
                    if not line.startswith("data:"):continue
                    response = line[5:]  # 去掉前缀 "data:"
                else:
                    response = line

                if not response:continue # 确保数据非空
                if response=="[DONE]":break
                data = json.loads(response)

                if data["msg"].strip():
                    yield "<Message: %s Code: %d>" % (data["msg"],data["code"])
                if data["data"] is None:continue
                if "text" in data["data"]:
                    self.context_id=data["data"].get("cid","") or self.context_id # 对话上下文
                    if payload.get("model") in ADVANCED_MODELS:
                        self.advanced_total=data["data"].get("total",None) or self.advanced_total
                        self.advanced_remain=data["data"].get("remain",None) or self.advanced_remain
                    else:
                        self.total=data["data"].get("total",None) or self.total # or: 保留旧的self.total
                        self.remain=data["data"].get("remain",None) or self.remain
                    yield data["data"]["text"] # 返回文本响应

                if deep_search and "deep_search" in data["data"]:
                    search=data["data"]["deep_search"]
                    if search["status"]=="answering":
                        yield search["field"].get("answer_fragment","")
                    elif "field" in search:
                        field=str(search['field'])
                        if len(field)>=128:field=pprint.pformat(search['field'])
                        yield f"<Status: {search['status']}: {field}>\n"
                    else:
                        yield f"<Status: {search['status']}>\n"
            except Exception as err:
                warn(f"Error processing stream ({type(err).__name__}): {err} Raw: {line_raw}")
    def chat(self,prompt,model="gpt-4o-mini",
             stream=True,output_lang=None,thinking_mode=False,
             data_analysis=True,search=False,
             text_to_image=False,artifact=True):
        # 使用提示词调用AI，返回结果的字符串生成器(如果参数stream为True，默认)
        # 或结果字符串(如果stream为False)
        auto_tools=[]
        if data_analysis:auto_tools.append("data_analysis")
        if search:auto_tools.append("search")
        if text_to_image:auto_tools.append("artifact")

        url = "https://sider.ai/api/v3/completion/text"
        header = self.header.copy()
        header["content-type"] = 'application/json'
        payload = {
            "prompt": prompt,
            "stream": stream,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "tz_name": TIMEZONE,
            "cid": self.context_id, # 对话上下文id，如果为空则开始新对话
            "model": model,
            "search": False,
            "auto_search": False,
            "filter_search_history": False,
            "from": "chat",
            "group_id": "default",
            "chat_models": [],
            "files": [],
            "prompt_templates": [],
            "tools": {"auto": auto_tools},
            "extra_info": {
                "origin_url": ORIGIN+"/standalone.html",
                "origin_title": "Sider"
            }
        }
        if artifact: # 在artifact的新窗口中显示结果
            payload["prompt_templates"].append(
                {"key":"artifacts", "attributes": {"lang": "original"}}
            )
        if thinking_mode:
            payload["prompt_templates"].append(
                {"key": "thinking_mode", "attributes": {}}
            )
        if output_lang is not None: # 模型输出语言，如"en","zh-CN"
            payload["output_language"]=output_lang

        if stream:
            return self.get_text(url,header,payload)
        else:
            return "".join(self.get_text(url,header,payload))
    def ocr(self,filename,model="gemini-2.0-flash",stream=True):
        # 一个生成器，调用OCR并返回结果
        data = upload_image(filename,self.header)
        img_id = data["data"]["id"]
        url="https://api2.sider.ai/api/v2/completion/text"
        payload = {
            "prompt": "ocr",
            "stream": stream,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "tz_name": TIMEZONE,
            "cid": self.context_id,
            "model": model,
            "from": "ocr",
            "image_id": img_id,
            "ocr_option": {
                "force_ocr": True,
                "use_azure": False
            },
            "tools": {},
            "extra_info": {
                "origin_url": ORIGIN+"/standalone.html",
                "origin_title": "Sider"
            }
        }
        if stream:
            return self.get_text(url,self.header,payload)
        else:
            return "".join(self.get_text(url,self.header,payload))
    def translate(self,content,target_lang="English",model="gpt-4o-mini",stream=True):
        url="https://api3.sider.ai/api/v2/completion/text"
        payload = {
            "prompt": "",
            "stream": stream,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "tz_name": TIMEZONE,
            "model": model,
            "from": "translate",
            "prompt_template": {
                "key": "translate-basic",
                "attributes": {
                    "input": content,
                    "target_lang": target_lang # 目标语言名称，如"English"或"Chinese (Simplified)"
                }
            },
            "tools": {
                "force": "reader"
            },
            "extra_info": {
                "origin_url": ORIGIN+"/standalone.html",
                "origin_title": "Sider"
            }
        }
        if stream:
            return self.get_text(url,self.header,payload)
        else:
            return "".join(self.get_text(url,self.header,payload))
    def search(self,content,model="gpt-4o-mini",stream=True,focus=None):
        # focus为字符串列表，包含搜索网站的域名，如"wikipedia.org"或"youtube.com"等
        url="https://api3.sider.ai/api/v2/completion/text"
        payload = {
            "prompt": content,
            "stream": stream,
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
            "tz_name": TIMEZONE,
            "model": model,
            "from": "deepsearch",
            "deep_search": {
                "enable": True
            },
            "tools": {},
            "extra_info": {
                "origin_url": ORIGIN+"/standalone.html",
                "origin_title": "Sider"
            }
        }
        if focus:
            payload["deep_search"]["focus"]=focus
        if stream:
            return self.get_text(url,self.header,payload,deep_search=True)
        else:
            return "".join(self.get_text(url,self.header,payload,deep_search=True))
    def improve_grammar(self,content,model="gpt-4o-mini"):
        url="https://api3.sider.ai/api/v1/completion/improve_writing"
        payload = {"content":content,
                   "model":model,
                   "tz_name":TIMEZONE,
                   "app_name":APP_NAME,
                   "app_version":APP_VERSION}
        return self.get_text(url,self.header,payload)


def test_chat(session):
    while True:
        try:
            if session.remain is not None:
                msg=f"输入提示词 ({session.remain}/{session.total}): "
            else:msg="输入提示词: "
            prompt=input(msg)
            if prompt.strip():
                for result in session.chat(prompt, "gpt-4o-mini"):
                    print(result,end="")
                print()
        except Exception:
            traceback.print_exc()

def test_translate(session):
    while True:
        try:
            if session.remain is not None:
                msg=f"输入待翻译为英文的句子 ({session.remain}/{session.total}): "
            else:msg="输入待翻译为英文的句子: "
            content=input(msg)
            if content.strip():
                for result in session.translate(content, "English"):
                    print(result,end="")
                print()
        except Exception:
            traceback.print_exc()

def test_search(session):
    while True:
        try:
            if session.remain is not None:
                msg=f"输入搜索词 ({session.remain}/{session.total}): "
            else:msg="输入搜索词: "
            content=input(msg)
            if content.strip():
                for result in session.search(content):
                    print(result,end="")
                print()
        except Exception:
            traceback.print_exc()

def test_ocr(session):
    while True:
        try:
            filename=normpath(input("拖曳文件到本窗口（或输入文件路径），再按Enter: ").strip())
            if filename.strip():
                for result in session.ocr(filename):
                    print(result,end="")
                print()
        except Exception:
            traceback.print_exc()

def test_grammar(session):
    while True:
        try:
            if session.remain is not None:
                msg=f"输入待改进的英文句子 ({session.remain}/{session.total}): "
            else:msg="输入待改进的英文句子: "
            content=input(msg)
            if content.strip():
                for result in session.improve_grammar(content):
                    print(result,end="")
                print()
        except Exception:
            traceback.print_exc()

if __name__=="__main__":
    token_file=sys.argv[1] if len(sys.argv)>=2 else DEFAULT_TOKEN_FILE
    with open(token_file,encoding="utf-8") as f:
        config=json.load(f)
        token=config.get("token")
        cookie=config.get("cookie")
    sess=Session(token=token,cookie=cookie)
    test_chat(sess)