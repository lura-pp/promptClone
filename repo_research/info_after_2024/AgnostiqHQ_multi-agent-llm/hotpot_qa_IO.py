import asyncio
import json
import os
import random
import sys
from datetime import datetime
from typing import List, Type

import pandas as pd
from pydantic import BaseModel, Field
from rich import print
from tqdm.asyncio import tqdm

from multi_agent_llm import OpenAILLM


def save_models_to_json(models: List[BaseModel], filepath: str):
    """
    Save a list of Pydantic models to a JSON file.
    """
    with open(filepath, "w") as json_file:
        json.dump([model.model_dump()
                  for model in models], json_file, indent=4)


def load_models_from_json(
    model_class: Type[BaseModel], filepath: str
) -> List[BaseModel]:
    """
    Load a list of Pydantic models from a JSON file.
    """
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
        return [model_class.model_validate(item) for item in data]


class QA(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation for the answer"
    )
    answer: str = Field(
        ...,
        description="Answer to the question, without being verbose. You are given a question. Exact answer in the shortest form possible. Do not include any additional information, descriptions, or explanations.",
    )


class SemanticEquivalence(BaseModel):
    is_equivalent: bool = Field(
        ...,
        description="Whether the predicted answer is semantically equivalent to the ground truth",
    )


def get_nth_data_from_dataframe(df, n):
    row = df.iloc[n]
    return row


def calculate_metrics(true_positives, false_positives, false_negatives, total):
    accuracy = true_positives / total * 100
    precision = (
        true_positives / (true_positives + false_positives)
        if (true_positives + false_positives) > 0
        else 0
    )
    recall = (
        true_positives / (true_positives + false_negatives)
        if (true_positives + false_negatives) > 0
        else 0
    )
    f1_score = (
        2 * (precision * recall) / (precision + recall)
        if (precision + recall) > 0
        else 0
    )
    return accuracy, precision, recall, f1_score


async def evaluate_semantic_equivalence(llm, prediction, ground_truth, question):
    prompt = f"""Evaluate if the following two answers are semantically equivalent answer for the question:

Question: {question}

Predicted answer: {prediction}
Ground truth: {ground_truth}


Return true if they convey the same meaning, even if worded differently. Return false otherwise."""

    result = await llm.generate_async(
        llm.format_prompt("", prompt), SemanticEquivalence
    )
    return result.is_equivalent


async def process_question(task, item, schema):
    """Wrapper around LLM generate to allow for future extensions"""
    llm = OpenAILLM("gpt-4o-mini")
    system_prompt = "Please answer the following based on the context provided:\n"
    messages = llm.format_prompt(system_prompt, task(item))
    return await llm.generate_async(messages, schema=schema)


async def main(
        answer_schema: BaseModel,
        n: int = 50,
):
    # Set up the environment for OpenAI
    llm = OpenAILLM(
        model_name="gpt-4o-mini",
        api_key="...",
    )

    # Load the dataset
    data = pd.read_csv("hard_hotpot.csv")

    # Sample random indices
    random.seed(1993)
    indices = random.sample(range(len(data)), n)
    test_data = [get_nth_data_from_dataframe(data, i) for i in indices]

    # Define the task format function
    task = (
        lambda x: f"With the given context, answer the question exactly from context's paraphrase.\n\n{x.context}\n\nQuestion: {x.question}"
    )

    # Process questions with progress bar
    print("Processing questions...")
    results = await tqdm.gather(
        *[process_question(task, item, schema=QA) for item in test_data]
    )

    # Extract the answers
    predictions = [r.answer for r in results]
    ground_truths = [item.answer for item in test_data]

    # Evaluate semantic equivalence with progress bar
    print("Evaluating semantic equivalence...")
    evaluations = await tqdm.gather(
        *[
            evaluate_semantic_equivalence(llm, p, g, q)
            for p, g, q in zip(
                predictions, ground_truths, [
                    item.question for item in test_data]
            )
        ]
    )

    # Calculate metrics
    true_positives = sum(evaluations)
    false_positives = len(evaluations) - true_positives
    # In this binary classification, false positives equal false negatives
    false_negatives = false_positives
    total = len(evaluations)

    accuracy, precision, recall, f1_score = calculate_metrics(
        true_positives, false_positives, false_negatives, total
    )

    print(f"Accuracy: {accuracy:.2f}%")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"F1 Score: {f1_score:.2f}")

    # Prepare metadata
    class MetaData(BaseModel):
        indices: List[int]
        accuracy: float
        precision: float
        recall: float
        f1_score: float
        predictions: List[str]
        ground_truths: List[str]

    metadata = MetaData(
        indices=indices,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1_score,
        predictions=predictions,
        ground_truths=ground_truths,
    )

    # Add the metadata to the results list
    results.append(metadata)

    # The save_models_to_json call remains the same:
    save_models_to_json(
        results,
        f"./results/hotpot_qa_IO_n_{n}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json",
    )


if __name__ == "__main__":
    # Run the main function with asyncio
    asyncio.run(
        main(
            n=100,
            answer_schema=QA,
        )
    )
