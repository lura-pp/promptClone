import json
from typing import Dict, List
import sys

from util.dataDealing import WORKDIR
from util.openaiApiRetra import chat_once_str

def splitPrompt(string) -> str:

    sys_prompt = """
    #You are a prompt splitting machine. Split a prompt into different dimensions.
    
    ##These dimensions should be specific, clear,independent of each other and have specific names.You should discover as many dimensions as possible.

    ##You should have a highly versatile solution. This solution should be able to express most prompts. 

    ##When you receive a prompt, you should split it according to that splitting plan. 

    ##In addition, I hope that the result after splitting can be directly used as a prompt and have the same function as the original prompt effect.

    ##Your output format should only contain the split content and be output in the following json format.
    ```json
    {
        "spliting prompt": {
            "dimension1":[
                "placeholder",
                "placeholder",
                ...
            ],
            "dimension2":[
                "placeholder",
                "placeholder",
                ...
            ],
            "dimension3":[
                "placeholder",
                "placeholder",
                ...
            ],
            ...
        }
    }
    ```
    """
    
    return chat_once_str(sys_prompt, string)

def getInput(prompt):

    sys_prompt = """
    #I have a prompt that I want to test now, but I don't have a good input.You generate two inputs based on the prompt I gave you.
    #The input should be more complex to take full advantage of the prompt.
    #Your output format should only contain the two test inputs I want.
    #You should anwser with english.
    #And in order to facilitate my code reading, the following format should be strictly maintained:
    
    #input format:
    input1: placeholder
    
    input2: placeholder

    #prompt is:
    """

    return chat_once_str(sys_prompt, prompt)

def work1(fileIndex=1, 
        promptIndex=0, 
        model='gpt-4o-mini'):

    file_path = f"{WORKDIR}/raw_data/{fileIndex}.json"
    print(f"file: {file_path}  index:{promptIndex}")

    with open(f"{file_path}", 'r', encoding='utf-8') as f:
        datas:List[Dict[str, str]] = json.load(f)

    output = {}
    data = datas[promptIndex]
    title = data["title"]
    original_prompt = data["prompt"]

    output["title"] = title
    output["original_prompt"] = original_prompt

    split_prompt = splitPrompt(model, original_prompt)
    split_prompt = "This is a prompt description:" + split_prompt
    print('--------------------split done-------------------------')
    output["split_prompt"] = split_prompt

    ques = getInput(model, original_prompt)
    ques = "ll" + ques
    ques = ques.split("input1:")[1]
    ques = ques.split("input2:")
    print('----------------question generated done--------------------')

    if len(ques) == 2:    
        output["input1"] = ques[0]
        output["input2"] = ques[1]


        for i in range(2):
            original_ans = chat_once_str(original_prompt, ques[i])
            print("-----------------get original ans------------------------")
            split_ans = chat_once_str(split_prompt, ques[i])
            print("-------------------get split ans-------------------------")

            output[f"input{i+1}_ans"] = [original_ans, split_ans]   

        with open(f'{WORKDIR}/base_data/{fileIndex}_{promptIndex}.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=4)

    else:
        print("question erro")


def run():
    fileIndex = 1         #开始的文件
    while True:
        for promptIndex in range(12, 13):
            try:
                work1(fileIndex, promptIndex, 'gpt-4o-mini')
            except:
                continue    
        fileIndex = fileIndex + 10
        if fileIndex > 2:  #结束的文件
            break

if __name__ == "__main__":
    run()