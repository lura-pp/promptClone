import json
from typing import Dict
import os

from util.dataDealing import WORKDIR, Data
from util.similarity import sbert

DATA = Data()

def work2_get_similarities(fileIndex, 
                     promptIndex, 
                     input_dir="./base_data", 
                     output_dir="./output/similarities/auto_split"):
    
    with open(f"{input_dir}/{fileIndex}_{promptIndex}.json", 'r') as f:
        data = json.load(f)

    output = {}
    output["input1_similarities"] = sbert(data["input1_ans"][0], data["input1_ans"][1])  
    output["input2_similarities"] = sbert(data["input2_ans"][0], data["input2_ans"][1])

    with open(f'{output_dir}/{fileIndex}_{promptIndex}.json', 'w') as f:
        json.dump(output, f, indent=4)


def work2_run():
    fileIndex = 1
    while fileIndex < 342:
        for promptIndex in range(120):
            try:
                work2_get_similarities(fileIndex, promptIndex)
            except:
                continue
        fileIndex = fileIndex + 10


def get_high_factors_and_low_factors(high = 0.9, low = 0.80): 
    j = 1

    output_high = {}
    output_low = {}

    count_high = 0
    count_low = 0
    while j < 342:
        for i in range(120):
            print(j, i)
            
            try:
                with open(f"{WORKDIR}/base_data/{j}_{i}.json", 'r') as f:
                    data = json.load(f)
            except:
                continue

            split_prompt:str = data["split_prompt"]
            split_prompt = split_prompt.replace("This is a prompt description:```json\n", "")
            split_prompt = split_prompt.replace("```", "")
            
            try:
                dd = json.loads(split_prompt)
            except json.JSONDecodeError as e:
                print("erro: ", data["split_prompt"])
                print("j&i:", j, "&", i)
                continue

            with open(f"{WORKDIR}/output/similarities/auto_split/{j}_{i}.json", 'r') as f:
                data = json.load(f)
            
            st = max(data["input1_similarities"], data["input2_similarities"]) 

            try:
                if st > high:
                    count_high += 1
                    for key_ in dd["spliting prompt"]:
                        key = key_.lower()
                        if key in output_high:
                            output_high[key] = output_high[key] + 1
                        else:
                            output_high[key] = 1
                if st < low:
                    count_low += 1
                    for key_ in dd["spliting prompt"]:
                        key = key_.lower()
                        if key in output_low:
                            output_low[key] = output_low[key] + 1
                        else:
                            output_low[key] = 1
            except:
                continue
        j += 10

    print("high:   ", count_high, "low   ", count_low)

    sorted_data = dict(sorted(output_high.items(), key=lambda item: item[1], reverse=True))
    # with open(f'{WORKDIR}/output/factors/h{high}_value.json', 'w') as f:
    #     json.dump(sorted_data, f, indent=4)
    DATA.store_to_output("factors", f"h{high}_value.json", sorted_data)

    sorted_data = dict(sorted(output_low.items(), key=lambda item: item[1], reverse=True))
    # with open(f'{WORKDIR}/output/factors/l{low}_value.json', 'w') as f:
    #     json.dump(sorted_data, f, indent=4)
    DATA.store_to_output("factors", f"h{low}_value.json", sorted_data)



def merge(folder=f"{WORKDIR}/output/factors",
          outputpath=f"{WORKDIR}/output/merged_elements",
          simi=0.65):
    
    for filename in os.listdir(folder):
        inputfile = os.path.join(folder, filename)
        outputfile = os.path.join(outputpath, filename)
        
        try:
            with open(f"{inputfile}", 'r') as f:
                data:Dict[str, int] = json.load(f)
        except:
            continue

        output = {}
        keylist = list(data.keys())

        print(keylist, type(keylist))

        while len(keylist) != 0:
            with open("./temp_lenkey.txt", "w") as f:
                f.write(inputfile + '\n' + str(len(keylist)))

            key_temp = keylist.pop(0)
            
            key_need_merge = []
            temp_list = []
            for key in keylist:
                similarity = sbert(key_temp, key)
                print(similarity)
                if similarity > simi:
                    key_need_merge.append(key)
                else:
                    temp_list.append(key)
                    
            keylist = temp_list

            str_key = key_temp
            value = data[key_temp]
            for key in key_need_merge:
                str_key = str_key + ", " + key
                value = value + data[key]
            
            output[str_key] = value

        with open(f"{outputfile}", 'w') as f:
            json.dump(output, f, indent=4)


def run():
    # work2_run()
    get_high_factors_and_low_factors()
    merge()


if __name__ == "__main__":
    run()