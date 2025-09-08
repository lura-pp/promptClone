import asyncio
import json

import numpy as np
import pandas as pd
from datasets import load_dataset
from pydantic import BaseModel, Field
from rouge_score import rouge_scorer

from multi_agent_llm import OpenAILLM
from multi_agent_llm.agents.iteration_of_thought import AIOT


class QA(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation for the answer in detail",
    )
    answer: str = Field(
        ...,
        description="Final answer derived from the explanation",
    )


llm = OpenAILLM(
    model_name="gpt-4o-mini",
    api_key="...",
)

hybrid_qa = load_dataset("wenhu/hybrid_qa", trust_remote_code=True)
hybrid_qa = hybrid_qa['train']

# Make it into a dataframe
hybrid_qa_df = pd.DataFrame(hybrid_qa)
np.random.seed(0)
hybrid_qa_df = hybrid_qa_df.sample(n=100)


# Initialize AIOT
aiot_hybrid = AIOT(
    llm=llm,
    iterations=10,
    answer_schema=QA,
)


async def run_aiot_async():
    for i in range(100):
        index = hybrid_qa_df.index[i]
        context = hybrid_qa_df.iloc[i]['table']
        context = {k: v for k, v in context.items() if k not in [
            'uid', 'intro', 'section_title', 'section_text']}
        table = ' '.join([f'{k}: {v}' for k, v in context.items()])
        question = hybrid_qa_df.iloc[i]['question']
        # Join the context dictionary and question to form the task
        task = table + f'\n Question: {question}' + ' Answer: '
        task = "Using the context table, answer the question without any explanation. \n Table:" + task
        output = await aiot_hybrid.run_async(task)
        print('******************************************************************************************')
        print(output.answer.answer)
        # save output as json
        filepath = f"./results/AIOT_hybridqa_{index}_10.json"

        with open(filepath, "w") as json_file:
            json.dump(output.dict(), json_file, indent=4)
        print('******************************************************************************************')
        print(hybrid_qa_df.iloc[i]['answer_text'])

asyncio.run(run_aiot_async())

# EM Calculation
correct = 0
for i in range(100):
    index = hybrid_qa_df.index[i]
    filepath = f"./results/AIOT_hybridqa_{index}_10.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
    if answer['answer'] == hybrid_qa_df.iloc[i]['answer_text']:
        correct += 1
    else:
        continue
print('EM score:', correct/100)


# F1 Calculation
# Rouge Calculation
def rouge_score(pred, truth):
    scorer = rouge_scorer.RougeScorer(['rouge1'], use_stemmer=True)

    # Calculate the scores
    scores = scorer.score(pred, truth)

    return scores['rouge1'].fmeasure


f1 = 0
for i in range(100):
    index = hybrid_qa_df.index[i]
    filepath = f"./results/AIOT_hybridqa_{index}_10.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']['answer']
    f1 += rouge_score(answer, hybrid_qa_df.iloc[i]['answer_text'])

print('F1 Score:', f1/100)


system_prompt = "For a given question, compare the two answers and return True if they are the same, and False otherwise."


class compare_schema(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation for the answer in detail",
    )
    answer: bool = Field(
        ...,
        description="True or False derived from the explanation",
    )


accuracy = 0
outputs = []
for i in range(100):
    index = hybrid_qa_df.index[i]
    filepath = f"./results/AIOT_hybridqa_{index}_10.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']['answer']
    question = hybrid_qa_df.iloc[i]['question']
    user_prompt = (
        "You are provided with two answers to a question. "
        "The question is as follows: \n"
        f"{question}\n"
        "The two answers are as follows: \n"
        f"Answer 1: {answer}\n"
        f"Answer 2: {hybrid_qa_df.iloc[i]['answer_text']}\n"
        "You need to compare the two answers and return True if they are the same in the context of the question at a general level, and False otherwise."
        "The answers are also considered the same if the second answer is a subset of the first answer and you must return True in this case."
    )
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    output = llm.generate(prompt, schema=compare_schema)
    outputs.append(output)
    accuracy += int(output.answer)

print('Accuracy:', accuracy/100)
