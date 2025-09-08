import asyncio
import json
import random
from datetime import datetime
from typing import List, Type

from pydantic import BaseModel, Field
from rich import print

from multi_agent_llm import OpenAILLM


async def generate_cot(prompt: str, schema):
    """Wrapper around LLM generate to allow for future extensions"""
    llm = OpenAILLM(
        model_name="gpt-4o-mini",
        api_key="...",
    )
    system_prompt = "Please answer the following based on the context provided:\n"
    user_prompt = (
        f"Answer the question: \n'{prompt}'.\n\n- For simple problems:"
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
    return await llm.generate_async(prompt, schema=schema)


def save_models_to_json(models: List[BaseModel], filepath: str):
    """
    Save a list of Pydantic models to a JSON file.

    :param models: A list of Pydantic model instances.
    :param filepath: The path where the JSON file will be saved.
    """
    # Convert each model to a dictionary and save as a list
    with open(filepath, "w") as json_file:
        json.dump([model.model_dump() for model in models], json_file, indent=4)


def load_models_from_json(
    model_class: Type[BaseModel], filepath: str
) -> List[BaseModel]:
    """
    Load a list of Pydantic models from a JSON file.

    :param model_class: The Pydantic model class to load into.
    :param filepath: The path of the JSON file to read from.
    :return: A list of instances of the Pydantic model.
    """
    with open(filepath, "r") as json_file:
        data = json.load(json_file)
        # Parse each dictionary in the list back into the Pydantic model
        return [model_class.model_validate(item) for item in data]


class Crossword:
    def __init__(self, clues, solution):
        # Split clues into horizontal and vertical based on indices
        self.h_clues = {f"h{i+1}": clues[i]
                        for i in range(5)}  # First 5 are horizontal
        self.v_clues = {
            f"v{i+1}": clues[i + 5] for i in range(5)
        }  # Next 5 are vertical
        self.solution = solution

    def clues(self):
        puzzle = "\n"
        # Display clues in organized format
        for label, clue in self.h_clues.items():
            puzzle += f"{label}. {clue}\n"
        for label, clue in self.v_clues.items():
            puzzle += f"{label}. {clue}\n"
        return puzzle


def calculate_crossword_metrics(answers, actual_solutions):
    # Initialize lists to store metrics for each answer
    correct_letters_percentages = []
    correct_words_percentages = []
    correct_games_percentages = []

    # Loop through each pair of answer and correct solution
    for index, (grid, actual_sol) in enumerate(zip(answers, actual_solutions)):
        try:
            # Check if the actual solution is a valid 5x5 grid
            if len(actual_sol) != 5 or any(len(row) != 5 for row in actual_sol):
                print(
                    f"Skipping: Correct solution at index {index} is not a 5x5 grid.")
                continue

            # Ensure the current grid is a valid 5x5 grid
            if len(grid) != 5 or any(len(row) != 5 for row in grid):
                print(f"Skipping: Grid at index {index} is not a 5x5 grid.")
                continue

            # Calculate correct letters
            correct_letters = sum(
                grid[i][j] == actual_sol[i][j] for i in range(5) for j in range(5)
            )
            correct_letters_percentage = (correct_letters / 25) * 100
            correct_letters_percentages.append(correct_letters_percentage)

            # Calculate correct words (5 horizontal + 5 vertical)
            correct_words = 0

            # Check horizontal words
            for i in range(5):
                # Compare entire row (horizontal word)
                if grid[i] == actual_sol[i]:
                    correct_words += 1

            # Check vertical words
            for j in range(5):
                if [grid[i][j] for i in range(5)] == [
                    actual_sol[i][j] for i in range(5)
                ]:  # Compare entire column (vertical word)
                    correct_words += 1

            correct_words_percentage = (correct_words / 10) * 100
            correct_words_percentages.append(correct_words_percentage)

            # Calculate correct games
            correct_games = 1 if correct_letters == 25 else 0
            correct_games_percentage = (
                correct_games / 1) * 100  # Either 0% or 100%
            correct_games_percentages.append(correct_games_percentage)

        except Exception as e:
            # Print error message and skip to the next answer
            print(f"Error processing grid at index {index}: {e}")
            continue

    # Return a single dictionary with lists of percentages
    return {
        "Correct Letters Percentage": correct_letters_percentages,
        "Correct Words Percentage": correct_words_percentages,
        "Correct Games Percentage": correct_games_percentages,
    }


class PuzzleAnswer(BaseModel):
    reasoning: str = Field(..., description="Explanation of the solution")
    crossword_solution: List[List[str]] = Field(
        ...,
        description="5 horizontal and 5 vertical words each in 5x5 array of characters",
    )


async def main(n: int = 5):

    # Load the JSON file and parse the data
    with open("./results/mini0505_0_100_5.json", "r") as file:
        data = json.load(file)

    # Create a list of Crossword objects
    crosswords = [Crossword(clues=item[0], solution=item[1]) for item in data]

    # Number of crosswords to sample

    # Define the task format function
    task = (
        lambda clues: f"""Solve 5x5 mini crosswords. Given an input of 5 horizontal (h1-h5) clues and 5 vertical clues (v1-v5) for the 5x5 grid, generate an output of 25 letters for 5 rows and 5 columns. Each row and column of this 5x5 is a crossword that should form a valid word for the corresponding clue.

Inputs:
{clues}"""
    )

    # Select random crosswords and create tasks and solutions
    all_indices = list(range(len(crosswords)))
    # Randomly sample 'n' indices from the list
    selected_indices = random.sample(all_indices, n)

    selected_crosswords = [crosswords[i] for i in selected_indices]
    tasks = [task(crossword.clues()) for crossword in selected_crosswords]
    correct_sol = [
        [cs.solution[i * 5: (i + 1) * 5] for i in range(5)]
        for cs in selected_crosswords
    ]

    # Initialize the list to store futures
    result_futures = []

    for i in tasks:
        future = generate_cot(i, schema=PuzzleAnswer)
        result_futures.append(future)

    # Run the tasks asynchronously and gather the results
    results = await asyncio.gather(*result_futures)

    # Extract the results from the Future objects
    llm_sol = [r.crossword_solution for r in results]

    # Calculate metrics for the solutions
    metrics = calculate_crossword_metrics(llm_sol, correct_sol)
    print(metrics)

    class MetaData(BaseModel):
        indices: List[int]
        metrics: dict

    results.extend([MetaData(indices=selected_indices, metrics=metrics)])
    save_models_to_json(
        results,
        f"./results/cross_word_COT_n_{n}_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json",
    )


if __name__ == "__main__":
    random.seed(1993)
    asyncio.run(main(n=20))
