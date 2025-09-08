import asyncio
import csv
import json
import random
from datetime import datetime
from typing import List

from pydantic import BaseModel, Field
from rich import print
from tqdm.asyncio import tqdm

from multi_agent_llm import OpenAILLM


class GPQAQuestion(BaseModel):
    question: str
    options: List[str]
    correct_answer: str


class QA(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation for the answer"
    )
    answer: str = Field(
        ...,
        description="Final answer (only give A/B/C/D/Uncertain) without any additional explanation.",
    )


class GPQADataset:
    def __init__(self, file_path: str):
        self.questions = self._load_questions(file_path)

    def _load_questions(self, file_path: str) -> List[GPQAQuestion]:
        questions = []
        with open(file_path, "r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                options = [
                    row["Correct Answer"],
                    row["Incorrect Answer 1"],
                    row["Incorrect Answer 2"],
                    row["Incorrect Answer 3"],
                ]
                random.shuffle(options)  # Shuffle the options
                correct_index = options.index(row["Correct Answer"])
                correct_label = ["A", "B", "C", "D"][correct_index]
                question = GPQAQuestion(
                    question=row["Question"],
                    options=options,
                    correct_answer=correct_label,
                )
                questions.append(question)
        return questions

    def __len__(self) -> int:
        return len(self.questions)

    def __getitem__(self, index: int) -> GPQAQuestion:
        return self.questions[index]


def save_results_to_json(results: List[BaseModel], filepath: str):
    with open(filepath, "w") as json_file:
        json.dump([result.model_dump()
                  for result in results], json_file, indent=4)


def calculate_metrics(correct_answers: int, total: int):
    accuracy = correct_answers / total * 100
    return accuracy


async def generate(prompt: str, schema):
    """Wrapper around LLM generate to allow for future extensions"""
    llm = OpenAILLM(
        model_name="gpt-4o",
        temperature=0.3,
        api_key="...",
    )
    system_prompt = "Please answer the following based on the context provided:\n"
    messages = llm.format_prompt(system_prompt, prompt)
    return await llm.generate_async(messages, schema=schema)


async def process_question(task, item: GPQAQuestion):
    result = await generate(task(item), schema=QA)
    return result


async def process_batch(task, batch: List[GPQAQuestion]):
    return await asyncio.gather(*[process_question(task, item) for item in batch])


async def main(
    file_path: str,
    n: int = 100,
    batch_size: int = 10,
):

    # Load the dataset
    dataset = GPQADataset(file_path)

    # Sample random indices
    random.seed(1993)
    indices = random.sample(range(len(dataset)), n)
    test_data = [dataset[i] for i in indices]

    # Define the task format function
    task = (
        lambda x: f"""Answer the following multiple-choice question. Provide your final answer as 'A', 'B', 'C', or 'D', followed by a brief explanation.

Question: {x.question}

Options:
A. {x.options[0]}
B. {x.options[1]}
C. {x.options[2]}
D. {x.options[3]}

Answer (A/B/C/D/Uncertain)
"""
    )

    # Process questions in batches with progress bar
    print("Processing questions...")
    results = []
    for i in tqdm(range(0, n, batch_size)):
        batch = test_data[i: i + batch_size]
        batch_results = await process_batch(task, batch)
        results.extend(batch_results)

    # Calculate accuracy
    correct_answers = sum(
        1
        for r, q in zip(results, test_data)
        if r.answer.strip().upper() == q.correct_answer
    )
    accuracy = calculate_metrics(correct_answers, len(results))

    print(f"Accuracy: {accuracy:.2f}%")

    # Prepare metadata
    class MetaData(BaseModel):
        indices: List[int]
        accuracy: float
        predictions: List[str]
        correct_answers: List[str]

    metadata = MetaData(
        indices=indices,
        accuracy=accuracy,
        predictions=[r.answer.strip().upper() for r in results],
        correct_answers=[q.correct_answer for q in test_data],
    )

    # Add the metadata to the results list
    results.append(metadata)

    # Save results to JSON
    save_results_to_json(
        results,
        f"./results/gpqa_IO_4o_n_{n}_batch_{batch_size}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json",
    )


if __name__ == "__main__":
    # Run the main function with asyncio
    asyncio.run(
        main(
            "./gpqa_diamond.csv",
            n=198,
            batch_size=200,
        )
    )
