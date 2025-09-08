import re
import json

from langdetect import detect, DetectorFactory, lang_detect_exception

DetectorFactory.seed = 0

def has_non_english_except_emoji(text):
    '''
    移除Emoji和符号，只保留文字部分进行语言检测
    '''
    text_without_emoji = re.sub(r'[^\w\s]', '', text)
    
    if not text_without_emoji.strip():
        return False
    
    try:
        lang = detect(text_without_emoji)
        return lang != 'en'
    except lang_detect_exception.LangDetectException:
        return has_non_english_except_emoji_fallback(text)

def has_non_english_except_emoji_fallback(text):
    """回退方法：检测特定语言的字符"""
    non_english_patterns = [
        r'[\u4e00-\u9fff]',  # 中日韩统一表意文字
        r'[\u3040-\u309f]',  # 日文平假名
        r'[\u30a0-\u30ff]',  # 日文片假名
        r'[\u0400-\u04ff]',  # 西里尔字母
        r'[\u0600-\u06ff]',  # 阿拉伯文
        r'[\u0900-\u097f]',  # 梵文
    ]
    
    for pattern in non_english_patterns:
        if re.search(pattern, text):
            return True
    
    return False


def count_prompts_in_repo(target_dir="temp_repo"):
    try:
        
        if not os.path.exists(target_dir):    
            return
        
        
        # 定义prompt匹配的正则表达式模式
        patterns = [
            # prompt  基本都是对的
            r'\w*prompt\w*\s*=\s*["\'](.*?)["\']',
            r'\w*prompt\w*\s*=\s*"""(.*?)"""',
            r"\w*prompt\w*\s*=\s*'''(.*?)'''",
            r'["\']\s*\w*prompt\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            r'(?<!-> )["\']\s*\w*prompt\w*\s*["\']\s*:\s*"""(.*?)"""',
            r"(?<!-> )[\"']\s*\w*prompt\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            # instruction   基本都是对的 使用inst 会出现fp误认为是install  使用inst的时候观察十几个，发现前面都是完整的instruction，所以推荐完整使用
            r'\w*instruction\w*\s*=\s*["\'](.*?)["\']',
            r'\w*instruction\w*\s*=\s*"""(.*?)"""',
            r"\w*instruction\w*\s*=\s*'''(.*?)'''",
            r'["\']\s*\w*instruction\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            r'(?<!-> )["\']\s*\w*instruction\w*\s*["\']\s*:\s*"""(.*?)"""',
            r"(?<!-> )[\"']\s*\w*instruction\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            # rule   基本没找到 看到一两个是符合的
            r'\w*rule\w*\s*=\s*["\'](.*?)["\']',
            r'\w*rule\w*\s*=\s*"""(.*?)"""',
            r"\w*rule\w*\s*=\s*'''(.*?)'''",
            r'["\']\s*\w*rule\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            r'(?<!-> )["\']\s*\w*rule\w*\s*["\']\s*:\s*"""(.*?)"""',
            r"(?<!-> )[\"']\s*\w*rule\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            r'<system>(.*?)</system>',  # XML系统提示
            r'<user>(.*?)</user>',  # XML用户提示
            r'### Instruction:\s*(.*?)(###|$)',  # 常见指令模式
            
            # # guidance 基本没找到 感觉可以不开
            # r'\w*guidance\w*\s*=\s*["\'](.*?)["\']',
            # r'\w*guidance\w*\s*=\s*"""(.*?)"""',
            # r"\w*guidance\w*\s*=\s*'''(.*?)'''",
            # r'["\']\s*\w*guidance\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            # r'(?<!-> )["\']\s*\w*guidance\w*\s*["\']\s*:\s*"""(.*?)"""',
            # r"(?<!-> )[\"']\s*\w*guidance\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            # # # description  fp很多，很多函数内的默认参数会这样使用
            # r'\w*description\w*\s*=\s*["\'](.*?)["\']',
            # r'\w*description\w*\s*=\s*"""(.*?)"""',
            # r"\w*description\w*\s*=\s*'''(.*?)'''",
            # r'["\']\s*\w*description\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            # r'(?<!-> )["\']\s*\w*description\w*\s*["\']\s*:\s*"""(.*?)"""',
            # r"(?<!-> )[\"']\s*\w*description\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            # # # text  基本都是项目介绍
            # r'\w*text\w*\s*=\s*["\'](.*?)["\']',
            # r'\w*text\w*\s*=\s*"""(.*?)"""',
            # r"\w*text\w*\s*=\s*'''(.*?)'''",
            # r'["\']\s*\w*text\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            # r'(?<!-> )["\']\s*\w*text\w*\s*["\']\s*:\s*"""(.*?)"""',
            # r"(?<!-> )[\"']\s*\w*text\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            
            # # set  超高fp
            # r'\w*set\w*\s*=\s*["\'](.*?)["\']',
            # r'\w*set\w*\s*=\s*"""(.*?)"""',
            # r"\w*set\w*\s*=\s*'''(.*?)'''",
            # r'["\']\s*\w*set\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            # r'(?<!-> )["\']\s*\w*set\w*\s*["\']\s*:\s*"""(.*?)"""',
            # r"(?<!-> )[\"']\s*\w*set\w*\s*[\"']\s*:\s*'''(.*?)'''",
            
            # # # config 没看到对的，找到全是错误的
            # r'\w*config\w*\s*=\s*["\'](.*?)["\']',
            # r'\w*config\w*\s*=\s*"""(.*?)"""',
            # r"\w*config\w*\s*=\s*'''(.*?)'''",
            # r'["\']\s*\w*config\w*\s*["\']\s*:\s*["\'](.*?)["\']',
            # r'(?<!-> )["\']\s*\w*config\w*\s*["\']\s*:\s*"""(.*?)"""',
            # r"(?<!-> )[\"']\s*\w*config\w*\s*[\"']\s*:\s*'''(.*?)'''",
        ]
        
        
        
        info = dict()
        visited_str = set()
        for root, dirs, files in os.walk(target_dir):
            for file in files:
                if file.endswith(('.py', '.js', 'json', '.xml', '.yaml', '.yml')):  
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            for pattern in patterns:
                                matches = re.findall(pattern, content, re.I | re.DOTALL)
                                if len(matches) != 0:
                                    for m in matches:
                                        text = m
                                        if len(text.split()) >= 20:
                                            if file not in info:
                                                info[file] = 0
                                            if text not in visited_str and not has_non_english_except_emoji(text):
                                                print(file_path)
                                                print(text)
                                                visited_str.add(text)
                                                info[file] += 1
                                                print('---------------------------------------------')
                                
                    except UnicodeDecodeError:
                        continue  # 跳过二进制文件
                    except Exception as e:
                        print(f"处理文件 {file_path} 时出错: {str(e)}")
                        
        if not os.path.exists(f"info_/{target_dir.split('/')[1]}"):
            os.mkdir(f"info_/{target_dir.split('/')[1]}")
        with open(f'info_/{target_dir.split('/')[1]}/AAA_info.json', 'w') as ff:
            json.dump(info, ff, indent=4)
    except Exception as e:
        print(f"处理仓库 {target_dir} 时发生异常: {str(e)}")


import os
import concurrent.futures

def process_repo(repo_name, count):
    print(f'--------------{count}----------------')
    count_prompts_in_repo(f'repos/{repo_name}')

def test(max_workers=4, timeout=1800, repo_names_=None):
    """
    并行处理 repos 文件夹下的所有 repo
    - max_workers: 最大并行进程数
    - timeout: 单个 repo 最长处理时间（秒），默认30分钟
    """
    if repo_names_ == None:
        repo_names = os.listdir('repos')
    else:
        repo_names = repo_names_

    print(len(repo_names))
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_repo, repo_name, i): repo_name
            for i, repo_name in enumerate(repo_names)
        }

        for future in concurrent.futures.as_completed(futures):
            repo_name = futures[future]
            try:
                future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                print(f"⏱️ 跳过 {repo_name}（超过 {timeout//60} 分钟）")
            except Exception as e:
                print(f"❌ {repo_name} 处理出错: {e}")

def get_large_than_x(target_year=2024, x=1, target_dir='info_copy'):
    print(__file__)

    with open('last_commit_year.json', 'r') as f:
        last_commit_year = json.load(f)
    rebuttle_path = os.path.dirname(__file__)


    result = list()
    all_count = 0
    

    for repo in os.listdir(os.path.join(rebuttle_path, target_dir)):
        info_path = os.path.join(rebuttle_path, target_dir, repo, 'AAA_info.json')
        # repo_path = os.path.join(rebuttle_path, 'repos', repo)
        repo_year = last_commit_year[repo]
        if repo_year and int(repo_year) < target_year:
            continue
            
        if not os.path.exists(info_path):
            continue
        all_count += 1
        with open(info_path, 'r') as f:
            info = json.load(f)
            
            count = 0
            for k in info:
                count += info[k]
                
            if count not in range(x+1):
                result.append(repo)
                
    with open(f'tmp_large_than_{x}_prompts.json', 'w') as f:
        json.dump(result, f,indent=4)
    print(len(result))
    return result

def run_test():
    with open(f'tmp_large_than_1_prompts.json', 'r') as f:
        result = json.load(f)    
    test(max_workers=6, repo_names_=result)

if __name__ == "__main__":
    # get_large_than_x(x=1)
    run_test()               
