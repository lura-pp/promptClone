import json

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from rouge_score import rouge_scorer

from multi_agent_llm import OpenAILLM

llm = OpenAILLM(
    model_name="gpt-4o-mini",
    api_key="...",
)

morehop_df = pd.read_csv('MoreHopQA.csv')
np.random.seed(42)
morehop_df = morehop_df.sample(n=100)


class QA(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation for the answer in detail",
    )
    answer: str = Field(
        ...,
        description="Final answer derived from the explanation",
    )


system_prompt = (
    "Answer the question directly without any explanations."
)
for i in range(100):
    index = morehop_df.index[i]
    context = [morehop_df.iloc[i]['context']]
    question = morehop_df.iloc[i]['question']
    context.append([question + "\n Answer: "])
    task = ' '.join([f'{c}' for c in context])
    user_prompt = (
        "Answer the question directly without any explanations. "
    )
    user_prompt += task
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    output = llm.generate(prompt, schema=QA)
    print('******************************************************************************************')
    print(output.answer)
    # save output as json
    filepath = f"../MultiHopQA/IO_morehop_{index}.json"

    with open(filepath, "w") as json_file:
        json.dump(output.dict(), json_file, indent=4)
    print('******************************************************************************************')
    print(morehop_df.iloc[i]['answer'])


# EM Calculation

correct = 0
for i in range(100):
    index = morehop_df.index[i]
    filepath = f"./results/IO_morehop_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
    if answer == morehop_df.iloc[i]['answer']:
        correct += 1
    else:
        continue
print('Accuracy:', correct/100)


# Rouge Calculation


def rouge_score(pred, truth):
    scorer = rouge_scorer.RougeScorer(['rouge1'], use_stemmer=True)

    # Calculate the scores
    scores = scorer.score(pred, truth)

    return scores['rouge1'].fmeasure


f1 = 0
for i in range(100):
    index = morehop_df.index[i]
    filepath = f"./results/IO_morehop_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
    f1 += rouge_score(answer, morehop_df.iloc[i]['answer'])

print('Rouge-1 F1 Score:', f1/100)


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
    index = morehop_df.index[i]
    filepath = f"./results/IO_morehop_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
    question = morehop_df.iloc[i]['question']
    user_prompt = (
        "You are provided with two answers to a question. You need to compare the two answers and return True if they are the same, and False otherwise. "
        "The question is as follows: \n"
        f"{question}\n"
        "The two answers are as follows: \n"
        f"Answer 1: {answer}\n"
        f"Answer 2: {morehop_df.iloc[i]['answer']}\n"
        "You need to compare the two answers and return True if they are the same, and False otherwise."
    )
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    output = llm.generate(prompt, schema=compare_schema)
    outputs.append(output)
    accuracy += int(output.answer)

print('Accuracy:', accuracy/100)
