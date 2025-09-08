import json
import random
from datetime import datetime
from typing import List, Type

import pandas as pd
from pydantic import BaseModel, Field
from rich import print
from tqdm.asyncio import tqdm

from multi_agent_llm import OpenAILLM


def save_models_to_json(models: List[BaseModel], filepath: str):
    with open(filepath, "w") as json_file:
        json.dump([model.model_dump()
                  for model in models], json_file, indent=4)


def load_models_from_json(
    model_class: Type[BaseModel], filepath: str
) -> List[BaseModel]:
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
        return [model_class.model_validate(item) for item in data]


class PuzzleAnswer(BaseModel):
    explanation: str = Field(
        ...,
        description="Explanation of the solution"
    )
    answer_expression: str = Field(
        ..., description="Only the final expression that can be evaluated in python."
    )


def check_ans(answer, input_num):
    import re

    # Extract numbers from the answer and the input
    numbers = [int(num) for num in re.findall(r"\d+", answer.split("=")[0])]
    actual = [int(num) for num in re.findall(r"\d+", input_num.split("=")[0])]
    # Check if the number of extracted numbers is exactly 4
    if len(numbers) != 4:
        # print("Failed: Number of extracted numbers is not 4.")
        return False
    # Check if the numbers match the expected set of numbers
    if set(numbers) != set(actual):
        # print("Failed: Extracted numbers do not match the actual numbers.")
        return False
    # Check if the sum value is 24
    try:
        sum_value = eval(answer.split("=")[0])
    except:
        # print("Failed: Error in evaluating the sum expression.")
        return False
    if sum_value != 24:
        # print("Failed: The evaluated sum is not 24.")
        return False
    # If all checks pass, return True
    return True


async def generate(prompt: str, schema):
    """Wrapper around LLM generate to allow for future extensions"""
    llm = OpenAILLM(
        model_name="gpt-4o-mini",
        api_key="...",
    )
    system_prompt = "Please answer the following based on the context provided:\n"
    messages = llm.format_prompt(system_prompt, prompt)
    return await llm.generate_async(messages, schema=schema)


async def main(n: int = 20):

    # Load the CSV file and parse the data
    data = pd.read_csv("./24.csv")
    puzzles = [
        ",".join(i.split()) for i in data.sort_index(ascending=False)["Puzzles"].values
    ]

    # Number of puzzles to sample
    n = min(n, len(puzzles))

    # Define the task format function
    task = (
        lambda puzzle: f"""The "24 Game" is a mathematical card game where the objective is to manipulate four numbers to reach the result of 24 using basic arithmetic operations: addition (+), subtraction (-), multiplication (*), and division (/). Each number must be used exactly once, and you can use any combination of operations.
    Make sure you follow exactly the rules of the Game:
    1. You are given four numbers (e.g., 3, 8, 8, 3).
    2. You should use each number given without skipping any number
    3. You should use each number exactly once.
    4. You can use addition, subtraction, multiplication, and division.
    5. Parentheses can be used to group numbers and operations.
    6. The goal is to make the numbers equal to 24.
    Now solve {puzzle} using the rules of the game.
    """
    )

    # Select random puzzles
    selected_indices = random.sample(range(len(puzzles)), n)
    selected_puzzles = [puzzles[i] for i in selected_indices]
    tasks = [task(puzzle) for puzzle in selected_puzzles]

    # Initialize the list to store futures
    result_futures = []

    for task in tasks:
        future = generate(task, schema=PuzzleAnswer)
        result_futures.append(future)
    # Run the tasks asynchronously and gather the results
    results = await tqdm.gather(*result_futures, desc="Solving puzzles")

    # Extract the results and check correctness
    correct_solutions = 0
    for result, puzzle in zip(results, selected_puzzles):
        if check_ans(result.answer_expression, puzzle):
            correct_solutions += 1

    accuracy = correct_solutions / n * 100

    # Prepare metadata
    class MetaData(BaseModel):
        indices: List[int]
        accuracy: float

    results.append(MetaData(indices=selected_indices, accuracy=accuracy))

    # Save results
    save_models_to_json(
        results,
        f"./results/24_game_IO_n_{n}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json",
    )

    print(f"Accuracy: {accuracy}%")
    return accuracy
