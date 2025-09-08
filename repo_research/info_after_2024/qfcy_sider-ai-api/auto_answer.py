import requests,json,traceback,re,sys
from sider_ai_api import Session

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("用法: python %s <包含问题的txt文件>"%sys.argv[0])
        exit(1)

    questions=[]
    session=Session()
    with open(sys.argv[1],encoding="utf-8") as f:
        cur_question="";started=False
        for line in f:
            if not line.strip():continue
            if re.match("^(\\d)*?(\\.|、)",line):
                if started:
                    questions.append(cur_question)
                started=True
                cur_question=""
            cur_question+=line
        questions.append(cur_question)
    for q in questions:
        try:
            prompt="请回答这道问题，输出答案，并用20~30字说明理由：\n"+q
            result = "".join(session.chat(prompt, "gpt-4o-mini")) # 可以改成gpt-4o
            print(result)
            print()
        except Exception:
            traceback.print_exc()