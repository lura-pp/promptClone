import sys,os,warnings,subprocess,traceback
import time,locale,shlex
from logging import basicConfig,info,debug,DEBUG
from sider_ai_api import Session

CODE_BLOCK="```"
FIRST_PROMPT="""这是用户需求：
{need}
请编写符合需求的代码，假定文件名为{source_file}，只需给出Windows中运行代码的单条命令，不需要给出设置环境、切换目录等所有额外的命令。
"""
PROMPT="""这是运行结果：
return code: {retcode}
stdout:
{stdout}
stderr:
{stderr}
请根据运行结果改进代码。如果没有错误，说出"{success_sign}"，否则不能说出。
"""
SUCCESS_SIGN="成功通过"
REQUEST_CODE_SIGN="请给出代码"
REQUEST_CMD_SIGN="请给出运行命令"
REQUEST_CODE_CMD_SIGN="请给出代码和运行命令"

LOG_FILE="code_generation_tool.log"
MODEL="gpt-4o-mini"
PROJECT_PATH="code"
FILENAME="code.bat"
LANGUAGE=["bash","bat",""]
MAX_TRIES=6
def extract_code(text, language=None):
    if isinstance(language,str):
        language=(language,)
    codes=[];cur_code=[];in_block=False;match_lang=False
    for lineno,line in enumerate(text.splitlines(),start=1):
        stripped=line.strip()
        if stripped.startswith(CODE_BLOCK):
            if not in_block: # 代码块开头
                if language is None:
                    match_lang=True
                else:
                    # 检查语言是否匹配
                    match_lang=False
                    for lang in language:
                        if stripped[len(CODE_BLOCK):].lower()==lang.lower():
                            match_lang=True;break
            else: # 到达代码块末尾
                if match_lang:codes.append("\n".join(cur_code))
                cur_code.clear()
                if len(stripped)>len(CODE_BLOCK):
                    warnings.warn("MarkdownSyntax: "
                        f'"```language_name" used at the end of code blocks at {lineno}')
            in_block=not in_block
        else:
            if in_block and match_lang: # 在代码块中且语言匹配
                cur_code.append(line.rstrip()) # 去除ai生成的行尾空格
    if in_block:
        warnings.warn("MarkdownSyntax: still in a code block at the end")
        if match_lang:
            codes.append("\n".join(cur_code))
    return codes

def run_cmd(cmd,shell="cmd /c chcp 65001 > nul &"):
    stdout=stderr="";returncode=None
    try:
        for line in cmd.splitlines():
            line="%s %s"%(shell,line.strip())
            result=subprocess.run(shlex.split(line),capture_output=True)
            stdout+=result.stdout.decode("utf-8","backslashreplace")+'\n'
            stderr+=result.stderr.decode("utf-8","backslashreplace")+'\n'
            returncode=result.returncode
            if returncode!=0:break
    except Exception:
        stderr+=traceback.format_exc()
    return stdout,stderr,returncode

def revise_code(session,code,cmd,max_tries=MAX_TRIES,model=MODEL):
    tries=max_tries-1
    while tries:
        stdout,stderr,returncode=run_cmd(cmd)
        
        debug("运行结果:\nstdout:\n%r\nstderr:\n%r\n最后一个命令的返回值: %s\n"%(stdout,stderr,returncode))
        prompt=PROMPT.format(retcode=returncode,stdout=stdout,
                             stderr=stderr,success_sign=SUCCESS_SIGN)
        content="".join(session.chat(prompt,model));tries-=1
        debug("剩余API次数: %s\n原始回答: %r"% (session.remain,content))
        if returncode==0 and SUCCESS_SIGN in content:
            info("代码在 %d 次调用之后编写成功"%(MAX_TRIES-tries))
            break
        codes=extract_code(content,LANGUAGE)
        if codes:code=codes[0]
        debug("代码: \n%s\n命令: %s" % (code,cmd))
        with open(FILENAME,"w",encoding="utf-8") as f:
            f.write(code)

def write_code(session,user_need,max_tries=MAX_TRIES,model=MODEL):
    prompt=FIRST_PROMPT.format(need=user_need,source_file=FILENAME)
    content="".join(session.chat(prompt,model))
    debug("初次回答: %r"%content)
    tries=max_tries-1;code=cmd=None
    while tries:
        codes=extract_code(content,LANGUAGE)
        if codes:code=codes[0]
        cmd_codes=extract_code(content,["bash","cmd",""])
        if cmd_codes:cmd=cmd_codes[0]

        if code and cmd:break # 检查是否同时有代码和命令
        elif code:sign=REQUEST_CMD_SIGN
        elif cmd:sign=REQUEST_CODE_SIGN
        else:sign=REQUEST_CODE_CMD_SIGN
        info("重新请求完整内容：%r"%sign)
        content="".join(session.chat(sign,model));tries-=1
        debug("剩余API次数: %s\n原始回答: %r"% (session.remain,content))
        
    debug("初次代码: \n%s\n命令: %s" % (code,cmd))
    pre_cwd=os.getcwd();os.chdir(PROJECT_PATH)
    with open(FILENAME,"w",encoding="utf-8") as f:
        f.write(code)
    revise_code(session,code,cmd,tries,model=model)
    os.chdir(pre_cwd)

def show_usage():
    info("显示帮助")
    print(f"""\
用法: python {sys.argv[0]} [代码文件] "命令"：修正一个代码文件
      python {sys.argv[0]} (不带参数)：输入需求并从头编写新的代码
      python {sys.argv[0]} -h：显示此帮助信息
""")

def _check_coding():
    coding=locale.getpreferredencoding().lower()
    if "utf-8" not in coding and "65001" not in coding:
        warnings.warn('''\
Current encoding is {repr(coding)}. \
Re-run with "python -Xutf8" to fix any encoding issues that may arise''')

def main():
    _check_coding()
    basicConfig(filename=LOG_FILE,filemode="w",level=DEBUG)
    info("---- 程序开始 %s 参数: %r ----" % (time.asctime(),sys.argv[1:]))
    if "-h" in sys.argv:
        show_usage();return
    if len(sys.argv)==3:
        code,cmd=sys.argv[1:]
        session=Session()
        revise_code(session,code,cmd,model=MODEL)
    elif len(sys.argv)==1:
        os.makedirs(PROJECT_PATH,exist_ok=True)
        need=input("输入需求：")
        if need.strip():
            debug("需求：%s"%need)
            session=Session()
            write_code(session,need,model=MODEL)
    else:
        show_usage();return

if __name__=="__main__":main()