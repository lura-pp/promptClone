import json

import numpy as np
import pandas as pd
from datasets import load_dataset
from pydantic import BaseModel, Field
from rouge_score import rouge_scorer

from multi_agent_llm import OpenAILLM

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
    "Answer the following question directly without any explanations."
)
for i in range(100):
    index = hybrid_qa_df.index[i]
    context = hybrid_qa_df.iloc[i]['table']
    context = {k: v for k, v in context.items() if k not in [
        'uid', 'intro', 'section_title', 'section_text']}
    question = hybrid_qa_df.iloc[i]['question']
    # Join the context dictionary and question to form the task
    # task = ' '.join([f'{k}: {v}' for k, v in context.items()]) + f' Question: {question}' + ' Answer: '
    user_prompt = (
        f"Given the table: \n'{context}', answer the question: \n'{question}'.\n\n- For simple problems:"
        "\nDirectly provide the answer without any explanations."
        "\n\n- For complex problems:"
        "\nUse this step-by-step approach:"
        "\n## Step 1: [Concise description of the first step]\n[Brief explanation of the first step]\n"
        "## Step 2: [Concise description of the second step]\n[Brief explanation of the second step]\n\n"
        "Regardless of the approach, always conclude with the final answer.\n\n"
        "Let's think step by step.\n"
    )
    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    output = llm.generate(prompt, schema=QA)
    print('******************************************************************************************')
    print(output.answer)
    # save output as json
    filepath = f"./results/COT_hybridqa_{index}.json"

    with open(filepath, "w") as json_file:
        json.dump(output.dict(), json_file, indent=4)
    print('******************************************************************************************')
    print(hybrid_qa_df.iloc[i]['answer_text'])


# EM Calculation

correct = 0
for i in range(100):
    index = hybrid_qa_df.index[i]
    filepath = f"./results/COT_hybridqa_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
    if answer == hybrid_qa_df.iloc[i]['answer_text']:
        correct += 1
    else:
        continue
print('Accuracy:', correct/100)


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
    filepath = f"./results/COT_hybridqa_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    answer = data['answer']
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
    filepath = f"./results/COT_hybridqa_{index}.json"
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
    question = hybrid_qa_df.iloc[i]['question']
    answer = data['answer']
    user_prompt = (
        "You are provided with two answers to a question. You need to compare the two answers and return True if they are the same, and False otherwise. "
        "The question is as follows: \n"
        f"{question}\n"
        "The two answers are as follows: \n"
        f"Answer 1: {answer}\n"
        f"Answer 2: {hybrid_qa_df.iloc[i]['answer_text']}\n"
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
