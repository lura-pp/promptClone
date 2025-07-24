import os
import sys
import json
from subprocess import Popen

WORKDIR = os.path.dirname(__file__)

sys.path.append(os.path.join(WORKDIR, "src"))

from util.dataDealing import Data

data = Data()

def test_compress():
    def get_number(d):
        ret = 0
        for k in d["analysis"]:
            ret += len(d["analysis"][k]["contents"])
            
        return ret
    
    def get_length(d):
        return len(json.dumps(d))        
    
    number_max = 0
    length_max = 0
    
    number_min = 0
    length_min = 0
    
    number_ori = 0
    length_ori = 0
    
    for index in range(0, 100):
        if str(index) in data.p_indexes:
            prom_compress_by_max = data.get_from_output(f"compress_{0.7}_max", f"{index}_{0.7}.json")
            prom_compress_by_min = data.get_from_output(f"compress_{0.7}_min", f"{index}_{0.7}.json")    
            prom_ori = data.get_from_output("attack_results", f"{index}.json")

            number_max += get_number(prom_compress_by_max)
            length_max += get_length(prom_compress_by_max)
            
            number_min += get_number(prom_compress_by_min)
            length_min += get_length(prom_compress_by_min)
            
            number_ori += get_number(prom_ori)
            length_ori += get_length(prom_ori)
            
    print(number_max, length_max)
    print(number_min, length_min)
    print(number_ori, length_ori)

def tmp():
    from util.openaiApiRetra import chat_once_str
    for index in range(0, 200):
        index = str(index)
        if index in data.p_indexes:
            if os.path.exists(os.path.join(WORKDIR, "output", f"compress_{0.7}_max_answerss", f"{index}_{0.7}_answerss.json")) and \
                os.path.exists(os.path.join(WORKDIR, "output", f"compress_{0.7}_min_answerss", f"{index}_{0.7}_answerss.json")):
                    print(index, ": skip")
                    continue
                
            print(f"-----{index}------")
            quesiotns = data.p_questions[index]
            prom_compress_by_max = data.get_from_output(f"compress_{0.7}_max", f"{index}_{0.7}.json")
            prom_compress_by_min = data.get_from_output(f"compress_{0.7}_min", f"{index}_{0.7}.json") 
            
            answerss_max = []
            answerss_min = []
            
            for ques in quesiotns:
                answers_max = []
                answers_min = []
                for i in range(3):
                    answers_max.append(chat_once_str(json.dumps(prom_compress_by_max), ques))
                    answers_min.append(chat_once_str(json.dumps(prom_compress_by_min), ques))
                answerss_max.append(answers_max)
                answerss_min.append(answers_min)
    
            data.store_to_output(f"compress_{0.7}_max_answerss", f"{index}_{0.7}_answerss.json", answerss_max)
            data.store_to_output(f"compress_{0.7}_min_answerss", f"{index}_{0.7}_answerss.json", answerss_min)


def ttt():
    keys = [_.split('_')[0] for _ in os.listdir(os.path.join(WORKDIR, "output/compress_0.7_min_answerss"))]
    print(keys)
    
    ori_answerss = data.get_from_output("results", "p_key_answerss_by_ori_prompt_gpt_mini.json")
    
    answerss_max = {}
    answerss_min = {}
    
    for key in keys:
        answerss_max[key] = data.get_from_output("compress_0.7_max_answerss", f"{key}_0.7_answerss.json")
        answerss_min[key] = data.get_from_output("compress_0.7_min_answerss", f"{key}_0.7_answerss.json")

    tatal_max_median, tatal_max_max = data.compare(ori_answerss, answerss_max, keys)
    tatal_min_median, tatal_min_max = data.compare(ori_answerss, answerss_min, keys)

    print('---------------------------------')
    print(tatal_max_median, tatal_max_max)
    print(tatal_min_median, tatal_min_max)


from workflow.mergeElements import run
if __name__ == "__main__":
    # run()
    ttt()
    # tmp()