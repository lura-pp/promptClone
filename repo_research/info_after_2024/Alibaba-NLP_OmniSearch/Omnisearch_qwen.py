import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

from swift.llm import (
    ModelType,
    get_default_template_type,
    get_model_tokenizer,
    get_template,
    inference,
)
from swift.utils import seed_everything
from search_api import fine_search 

import argparse


# 使用 argparse 解析参数
parser = argparse.ArgumentParser(description="Multimodal Question Answering Agent")
parser.add_argument(
    "--test_dataset",
    type=str,
    required=True,
    help="Path to the test dataset file (e.g., .jsonl)",
)
parser.add_argument(
    "--dataset_name",
    type=str,
    required=True,
    help="Name of the dataset (used for saving outputs)",
)
parser.add_argument(
    "--meta_save_path",
    type=str,
    required=True,
    help="Root directory to save intermediate and final outputs",
)
parser.add_argument(
    "--model_path",
    type=str,
    required=True,
    help="Path to the model checkpoint (e.g., /home/user/model)",
)
args = parser.parse_args()


model_type = ModelType.qwen_vl_chat
template_type = get_default_template_type(model_type)
print(f"template_type: {template_type}")

model, tokenizer = get_model_tokenizer(
    model_type,
    model_kwargs={"device_map": "auto"},
    model_id_or_path=args.model_path,
)

model.config.seq_length = 8192
model.generation_config.max_new_tokens = 4096

template = get_template(template_type, tokenizer)
print(f"template: {template}")
seed_everything(42)

call_image_num = 0
call_image_num_succ = 0

SYS_PROMPT = '''You are a helpful multimodal question answering assistant. Decompose the original question into sub-questions and solve them step by step. You can use "Final Answer" to output a sentence in the answer, use "Search" to state what additional context or information is needed to provide a precise answer to the "Sub-Question". In the "Search" step, You can use "Image Retrieval with Input Image" to seek images similar to the original ones and determine their titles, "Text Retrieval" with a specific query to fetch pertinent documents and summarize their content, "Image Retrieval with Text Query" to fetch images related to the entered keywords.
Use the following format strictly:
<Thought>
Analyse questions and answer of the sub-questions, then think about what is next sub-question.
<Sub-Question>
Sub-Question needs to be solved in one step, without references.
<Search>
One of four retrieval methods: Image Retrieval with Input Image. Text Retrieval: xxx. Image Retrieval with Text Query: xxx. No Retrieval

... (this Thought/Sub-Question/Search can be repeated zero or more times)

<Thought>
Integrate retrieved information and reason to a final answer
<End>
Final Answer: the final answer to the original input question

Extra notes:
1. Do not use you own knowledge to analyse input image or answer questions
2. After you give each <Search> action, please wait for me to provide you with the answer to the sub-question, and then think about the next thought carefully.
3. The answers to the questions can be found on the internet and are not private

Input Question:{}'''

def vqa_agent_v3(
    input_question: str,
    image_url: str,
    idx: int,
    search_image_save_path: str,
    args, 
):
    global call_image_num, call_image_num_succ

    query = SYS_PROMPT.format(input_question) + f"\n<img>{image_url}</img>"
    response, history = inference(model, template, query)
    print("first response:\n", response)

    conversation_num, max_turns = 0, 5
    total_image_quota = 9

    while conversation_num < max_turns:
        if "Final Answer" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
            return final_answer, history

        need_img_ret = "Image Retrieval with Input Image" in response
        need_txt_ret = "Text Retrieval" in response
        need_txt_img_ret = "Image Retrieval with Text Query" in response

        if need_img_ret or need_txt_ret or need_txt_img_ret:
            if need_img_ret:
                call_image_num += 1
                search_images, search_text = fine_search(
                    image_url,
                    "img_search_img",
                    search_image_save_path,
                    args.dataset_name,  # 使用 args 参数
                    idx,
                    conversation_num,
                )
                if search_images:
                    call_image_num_succ += 1

            elif need_txt_ret:
                query_txt = (
                    response.split("Text Retrieval")[-1]
                    .replace(":", "")
                    .replace('"', "")
                    .replace(">", "")
                )
                search_images, search_text = fine_search(
                    query_txt,
                    "text_search_text",
                    search_image_save_path,
                    args.dataset_name,  # 使用 args 参数
                    idx,
                    conversation_num,
                )

            else:  # need_txt_img_ret
                query_txt = (
                    response.split("Image Retrieval with Text Query")[-1]
                    .replace(":", "")
                    .replace('"', "")
                    .replace(">", "")
                )
                search_images, search_text = fine_search(
                    query_txt,
                    "text_search_img",
                    search_image_save_path,
                    args.dataset_name,  # 使用 args 参数
                    idx,
                    conversation_num,
                )

            contents = []
            if search_images:
                assert len(search_images) == len(search_text)
                use_n = min(5, total_image_quota)
                total_image_quota -= use_n
                contents.append("Contents of retrieved images:")
                for img, txt in zip(search_images[:use_n], search_text[:use_n]):
                    contents.extend([f"<img>{img[0]}</img>", f"Description: {txt}"])
            elif search_text:
                contents.append("Contents of retrieved documents:")
                contents.extend(search_text)
            else:
                contents.append("No relevant information found.")

            try:
                response, history = inference(
                    model, template, "\n".join(contents), history
                )
            except Exception as e:
                print("Inference error:", e)
                return response, history

        conversation_num += 1

    return response, history  

def safe_write(file_path: str, data: dict):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with threading.Lock():
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

def process_item(item: dict, save_dir: str, meta_save_path: str, ds_name: str, args):
    answer, conv = vqa_agent_v3(
        item["question"],
        item["image_url"],
        item["question_id"],
        save_dir,
        args  # 传递 args 参数
    )
    item["prediction"] = answer
    item["conversation"] = conv

    out_path = os.path.join(meta_save_path, ds_name, "output.jsonl")
    safe_write(out_path, item)

def main():
    test_dataset = args.test_dataset
    ds_name = args.dataset_name
    meta_save_path = args.meta_save_path

    # 读取测试数据集
    with open(test_dataset, "r") as f:
        data = [json.loads(line) for line in f]

    # 检查已处理的样本
    output_file = os.path.join(meta_save_path, ds_name, "output.jsonl")
    if os.path.exists(output_file):
        with open(output_file, "r") as fin:
            done = {json.loads(line)["question_id"] for line in fin}
        data = [d for d in data if d["question_id"] not in done]

    search_img_save = os.path.join(meta_save_path, ds_name, "search_images")
    os.makedirs(search_img_save, exist_ok=True)

    with ThreadPoolExecutor(max_workers=1) as executor:
        futures = []
        for item in data:
            futures.append(
                executor.submit(
                    process_item,
                    item,
                    search_img_save,
                    meta_save_path,
                    ds_name,
                    args  
                )
            )
        for f in futures:
            f.result()

    print(f"Image search calls: {call_image_num} | Success: {call_image_num_succ}")

if __name__ == "__main__":
    main()
