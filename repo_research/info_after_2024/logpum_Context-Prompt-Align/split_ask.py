import torch
import argparse
from tqdm import tqdm
import numpy as np
import pandas as pd
import json
import os
import sys
sys.path.append("../..") 
from llms import get_registed_model
import json
import re

def build_prompt(user, user_des, tweets, k):
    # head = clean_symbol_in_rel(head)
    instruction = """We need to summarize the description of a Twitter user. Please refer to the user description information and his tweet information. If the returned content contains emojis, please convert it into words.Afterwards, based on the above information, please select the {} most representative tweets from the this user's tweets.Note that if there is a hyperlink in the tweet information, be sure to refer to the content of the hyperlink. This Twitter user’s information is as follows: \n""".format(k)
    
    context_1 = f'The uid of this Twitter user is "{user}", his description information is "{user_des}",'
    context_2 = f'\nand this user has posted these tweets:\n "{tweets}"'
    context = context_1 + context_2
    predict_1 = "\n\nThe user's description and tweets end here.\n\nBased on the above rules, please first generate generate the impression of this Twitter user. Please be as detailed as possible. Return the impression only without any explanations."
    predict_2 = """You only need to answer a json string, which has two keys, the first is description, type is string, the second is tweets, type is list. When filling in the tweets parameter, you only need to copy the original tweet content.Remember you just need to select the 2 most representative tweets from the this user's tweets.This is the answer format I requested:{'description':"",'tweets':["",""]}, Output Example：{"description": "lutar sempre desisti nunca","tweets": ["TV: PSG aceita receber R$ 485 milhões ","@fredcaldeira Agora é só o city contratar Neymar e ganhar a Champions na próxima temporada"]}.Note that the content "description" and "tweets" in the output sample need to be filled in by yourself. Do not output it as is in the output sample here."""
    predict = predict_1 + predict_2
    
    return instruction, context, predict

def tweet_process(tweet_content):
    tweet_str = ""
    for t in tweet_content["tweets"]:
        t = t.strip("\n")
        t = t.replace("\n","")
        t = "'"+t+"'"
        t = t + '\n'
        tweet_str += t
    tweet_str = tweet_str.strip("\n")
    tweet_str = "{"+tweet_str+"}"
    return tweet_str

def check_prompt_length(prompt, model):
    length_flag = True
    all_tokens = prompt
    maximun_token = model.maximun_token
    # print("maximun_token: ", maximun_token)
    if model.token_len(all_tokens) < maximun_token:
        length_flag = True
    else:
        length_flag = False
    
    return length_flag

def Unified_format(res):
    pattern = r'\{[^{}]*\]'
    matches = re.findall(pattern, res)

# 对于每一个匹配到的部分，补充 '}' 并打印结果
    for match in matches:
        if match[-1] != '}':
            match += '}'
            return match
        
def generate_rule(row_des, row_tweet, model, args):
    rule_path = args.rule_path
    user = row_des["uid"]
    user_des = row_des["description"]
    assert row_des["uid"] == row_tweet["uid"]
    tweet_list = tweet_process(row_tweet)
    instruction, context, predict= build_prompt(user, user_des, tweet_list, args.k)
    current_prompt = instruction + context + predict
    # current_prompt_2 = instruction + context + predict_2
    length_flag = check_prompt_length(current_prompt, model)
    # length_flag_2 = check_prompt_length(current_prompt_2, model)
    if length_flag:
        with open(os.path.join(rule_path, f"{user}.txt"), "w") as rule_file, open(
            os.path.join(rule_path, f"{user}.query"), "w"
        ) as query_file:
            query_file.write(current_prompt + "\n")
            try:
                # query_file.write(current_prompt_2 + "\n")
                response = model.generate_sentence(instruction, context, predict)
                res = ""
                for resp in response:
                    res = res + resp
                    res = res + "\n"
                    res = Unified_format(res)
                # response_2 = model.generate_sentence(instruction, context, predict_2)
                # print("response: ", response)
                # print("response_2: ", response_2)
                rule_file.write(res)
            except Exception as e:
                print(e)
                err = "had error!!!!!!!"
                rule_file.write(err + "\n")
                # rule_file.write(e)
    else:
        print("out length!!!!!!!")  
    
    
def read_paths(path):
    results = []
    with open(path, "r") as f:
        for line in f:
            results.append(json.loads(line.strip()))
    return results


                               

def main(args, LLM):
    des_samples = read_paths(args.des_path)
    df_des_samples = pd.DataFrame(des_samples)
    tweet_samples = read_paths(args.twt_path)
    df_tweet_samples = pd.DataFrame(tweet_samples)


    if not os.path.exists(args.rule_path):
        os.makedirs(args.rule_path)
    with open('error_un1.txt', 'r', encoding='utf-8') as file:
        content = file.read()
        error_list = eval(content)
    model = LLM(args)
    print("Prepare pipline for inference...")
    model.prepare_for_inference()
    for uid in error_list:
        uid = uid.replace('.txt','')
        index = df_des_samples.loc[df_des_samples['uid'] == uid].index.item()
        des = des_samples[index]
        index = df_tweet_samples.loc[df_tweet_samples['uid'] == uid].index.item()
        tweet = tweet_samples[index]
        generate_rule(des,tweet,model,args)
        # n = 2
        # mid_index = len(tweet) // n
        # tweets = []
        # for i in range(n):
        #     if i == n - 1:
        #         tweets.append({'uid':tweet_samples[index]['uid'], 'tweets':tweet[mid_index * (n-1):]})
        #         continue
        #     tweets.append({'uid':tweet_samples[index]['uid'], 'tweets':tweet[mid_index * i:mid_index * (i+1)]})
        # for i in range(n):
        #     generate_rule(des,tweets[i],model,args,str(i))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--des_path", type=str, default="/root/autodl-tmp/BotRGCN/twibot_20/processed_data/user_description_train.jsonl", help="data directory"
    )
    parser.add_argument("--twt_path", type=str, default="/root/autodl-tmp/BotRGCN/twibot_20/processed_data/tweet_train.jsonl", help="dataset")
    parser.add_argument(
        "--rule_path", type=str, default="/root/autodl-tmp/BotRGCN/twibot_20/yangweibin/split_ask/processed_data/train_error_qlora", help="rule path dir"
    )
    parser.add_argument("--model_name", type=str, default="llama2-7B-chat-hf", help="model name")
    # parser.add_argument("--model_path", type=str, default="/root/autodl-tmp/llama-main/llama-7b-chat-hf", help="model path")
    parser.add_argument(
        "-k",
        type=int,
        default=2,
        help="Number of generated rules, 0 denotes as much as possible",
    )


    args, _ = parser.parse_known_args()
    LLM = get_registed_model(args.model_name)
    LLM.add_args(parser)
    args = parser.parse_args()

    main(args, LLM)
    
    