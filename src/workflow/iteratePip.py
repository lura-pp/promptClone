from copy import deepcopy
from util.openaiApiRetra import GPTApp
from util.dataDealing import Data, defense, feedback, WORKDIR
from util.similarity import get_simi_by_two_list

import json


DATA = Data()
def get_clo_answers(index, prompt, question, hasDenfense=True):
    if hasDenfense == True:
        defen = defense
    else:
        defen = ""

    output = []
    print(f'        get {index} answers.....')
    app = GPTApp(defen, prompt, f"./{index}_get_clo_answers.json", 'gpt-4o-mini')
    app.clear_history()
    messages = deepcopy(app.messages)

    for i in range(3):
        app.messages = deepcopy(messages)
        output.append(app.chat(question))
    return output

def get_simi_max_index(list1, list2):
    import torch
    tensor = get_simi_by_two_list(list1, list2)
    max_value = torch.max(tensor)  # 获取最大值
    max_index = torch.argmax(tensor)  # 获取最大值的索引（展平后的一维索引）
    coords = torch.unravel_index(max_index, tensor.shape)  # 转换为二维坐标

    print(tensor, max_value.item(), int(coords[0]), int(coords[1]))
    return max_value.item(), int(coords[0]), int(coords[1])

def get_feedback(index, sys_prompt, ques, answer_ori, answer_clo):
    app_ori = GPTApp(defense, sys_prompt, f"./{index}temp_get_feedback.json", "gpt-4o-mini")
    app_ori.clear_history()
    app_ori.messages.append({"role": "user", "content": ques})
    app_ori.messages.append({"role": "assistant", "content": answer_ori})
    # print(app_ori.messages)
    return app_ori.chat(feedback + answer_clo)

def len_dic(prompt_clone):
    sum = 0
    for key in prompt_clone["analysis"]:
        sum += len(prompt_clone["analysis"][key]["contents"])
    return sum

def get_contents(list1, string):
    simi_sentences = []
    ret_sentences = []
    from sbert import sbert
    from deepseek import deepseek
    for s in list1:
        if sbert(s, string) > 0.7:
            simi_sentences.append(s)
        else:
            ret_sentences.append(s)

    # print(len(ret_sentences))
    if len(simi_sentences) > 0:
        prom = """I have a list and a sentence. I think their semantics are similar. Please help me summarize them into a smooth sentence. Make sure no words are missing.
To facilitate my subsequent script processing, only return this sentence without any other words."""
        pp = json.dumps(simi_sentences)
        prom = prom + pp + string
        string = deepseek('gpt-4o-mini', "", prom)
    else:
        print(f"        no simi_sentences")
    
    ret_sentences.append(string)
    return ret_sentences



def iterate_pip(index_set):
    answersss = DATA.get_from_output("results", "p_key_answerss_by_ori_prompt_gpt_mini.json")

    for index in range(0, 200):
        index = str(index)
        if index not in index_set:
            continue
        questions = DATA.get_from_output("semi_open_questions", f"{index}.json")

        clone_prompt = DATA.get_from_output("compress_0.7_max", f"{index}_0.7.json")
        for key in clone_prompt["analysis"]:
            temp = [text for text in clone_prompt["analysis"][key]["contents"] if len(text) > 4]
            clone_prompt["analysis"][key]["contents"] = temp
        
        with open(f"{WORKDIR}/output/prompts/{index}.json", "r") as f:
            prompt = f.readline()

        ori_answerss = answersss[index]
        clo_answerss = []

        for ques in range(len(questions)):
            clo_answers = []
            print('----------------------------------------------------------------')
            print(f"    process question:{ques}")
            print(f"    get ori answers.......") 
            
            clone_prompt_str = json.dumps(clone_prompt)
            print(f"    get clone answers.......")
            clo_answers = get_clo_answers(index, clone_prompt_str, questions[ques])
            
            now_simi_max, max_i, max_j = get_simi_max_index(ori_answerss[ques], clo_answers)
            
            # if now_simi_max < 0.9:  #Whether to iterate if the similarity is high
            print(f"    simi:{now_simi_max} need to iterate")
            
            pre_simi = now_simi_max
            for i in range(3):
                clone_prompt_cp = deepcopy(clone_prompt)
                # iterate clone_prompt
                print('----------------------------')
                print(len_dic(clone_prompt_cp))        
                print(f"        iterate: {i}")
                
                has_fbk = False
                for j in range(3):
                    print("        get fbk.......")
                    fbk = get_feedback(index, prompt, questions[ques], ori_answerss[ques][max_i], clo_answers[max_j])
                    fbk_print = fbk.replace('\n', '\n        ')
                    fbk_print = '      ' + fbk_print
                    print(f"        fbk is:\n", fbk_print)
                    try:
                        print("        try fbk:{}")
                        fbk = json.loads(fbk)
                        has_fbk = True
                        break
                    except:
                        try:
                            print("        try fbk:```json{}```")
                            fbk = fbk.split("json")[1].strip("```")
                            fbk = json.loads(fbk)
                            has_fbk = True
                        except:
                            continue
                        break
                    
                if has_fbk:
                    for key in fbk:
                        if key in clone_prompt_cp["analysis"]:
                            #The second method to handle the suggestion
                            list1 = clone_prompt_cp["analysis"][key]["contents"]
                            print('---------------------------------------------------------')
                            print(f"        before key is:{key}, length is:{len(list1)}")
                            tmp = get_contents(list1, fbk[key])
                            print(f"        after key is:{key}, length is:{len(tmp)}")
                            print('----------------------------------------------------------')
                            clone_prompt_cp["analysis"][key]["contents"] = tmp   #The second method to handle the suggestion
                            # print(tmp)                            
                            # The first method to handle the suggestion
                            # clone_prompt_cp["analysis"][key]["contents"].append(fbk[key]) 
                    
                    # The first method to handle the suggestion
                    # print(f"        before remove duplicates {len_dic(clone_prompt_cp)}")
                    # clone_prompt_cp = remove_duplicates(index, threshold, clone_prompt_cp)
                    # print(f"        after remove duplicates {len_dic(clone_prompt_cp)}")

                    clone_prompt_str = json.dumps(clone_prompt_cp)
                    clo_answers_cp = get_clo_answers(index, clone_prompt_str, questions[ques])
                    
                    now_simi_max, max_i, max_j = get_simi_max_index(ori_answerss[ques], clo_answers_cp)
                    if now_simi_max < pre_simi:
                        print(f"        pre_simi:{pre_simi} now_simi:{now_simi_max} Invalid feedback")
                        continue
                    else:
                        print(f"        pre_simi:{pre_simi} now_simi:{now_simi_max} valid feedback")
                        clo_answers = clo_answers_cp
                        clone_prompt = deepcopy(clone_prompt_cp)
                        pre_simi = now_simi_max
                else:
                    print(f"        fail to get fbk")

            clo_answerss.append(clo_answers)

        DATA.store_to_output("iterate_prompt", f"{index}_v2.json", clone_prompt)
        DATA.store_to_output("clone_answerss", f"{index}_v2.json", clo_answerss)

def get_no_loop(beginIndex, endIndex):
    p_set = DATA.p_indexes
    # print(p_set)
    for index in range(beginIndex, endIndex):
        if str(index) not in p_set:
            # print(str(index), len(p_set))
            continue
        questions = DATA.get_from_output("semi_open_questions", f"{index}.json")
        if len(questions) == 0:
            print(index, 0)
            exit()

        clone_prompt = DATA.get_from_output("compress_0.7_max", f"{index}_0.7.json")
        for key in clone_prompt["analysis"]:
            temp = [text for text in clone_prompt["analysis"][key]["contents"] if len(text) > 4]
            clone_prompt["analysis"][key]["contents"] = temp

        clo_answerss = list()

        for ques in range(len(questions)):
            # if "Sorry, bro! Not possible." not in ori_answerss[ques]:
            print('----------------------------------------------------------------')
            print(f"    process question:{ques}")
            clone_prompt_str = json.dumps(clone_prompt)
            print(f"    get clone answers.......")
            clo_answers = get_clo_answers(index, clone_prompt_str, questions[ques])
            clo_answerss.append(clo_answers)
        
        DATA.store_to_output("no_loop_answerss", f"{index}.json", clo_answerss)

def run():
    import threading
    thread1 = threading.Thread(target=get_no_loop, args=(0, 40))
    thread2 = threading.Thread(target=get_no_loop, args=(40, 80))
    thread3 = threading.Thread(target=get_no_loop, args=(80, 120))
    thread4 = threading.Thread(target=get_no_loop, args=(120, 160))
    thread5 = threading.Thread(target=get_no_loop, args=(160, 200))

    thread1.start()
    thread2.start()
    thread3.start()
    thread4.start()
    thread5.start()

    print("-----wait all-----")
    thread1.join()
    thread2.join()
    thread3.join()
    thread4.join()
    thread5.join()

if __name__ == "__main__":
    run()