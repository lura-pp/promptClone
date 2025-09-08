import os

import pandas as pd

from Client.OpenAiClient import OpenAIClient
from config import OPENAI_API_KEY

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY


def generate_log_text(
    pod_template: pd.DataFrame, pod_structured: pd.DataFrame, record_num: int = 10
) -> str:
    """
    Generate a formatted log text from pod template and structured data.

    Args:
        pod_template (pd.DataFrame): DataFrame containing event templates.
        pod_structured (pd.DataFrame): DataFrame containing structured event data.
        record_num (int, optional): Number of example records to include. Defaults to 10.

    Returns:
        str: Formatted log text containing event templates and examples.
    """
    event_ids = pod_template["EventId"].unique()
    pod_prompt = ""

    for count, event_id in enumerate(event_ids):
        event_template = pod_template[pod_template["EventId"] == event_id][
            "EventTemplate"
        ].iloc[0]
        occurrence = pod_template[pod_template["EventId"] == event_id][
            "Occurrence"
        ].iloc[0]
        event_records = pod_structured[pod_structured["EventId"] == event_id]
        selected_records = event_records.iloc[:: max(1, occurrence // record_num)].head(
            record_num
        )

        pod_prompt += (
            f"---\n"
            f"Event template: {event_template}, with event ID {event_id}, occurred {occurrence} times.\n\n"
            f"Here are some examples of this template:\n\n"
        )

        pod_prompt += "\n".join(
            [
                f"* The event occurred at {record['Time']}, and its content was {record['Content']}."
                for _, record in selected_records.iterrows()
            ]
        )
        pod_prompt += "\n---\n\n"

        if count > 50:  # cut error template
            print("The Pod's Event Template is too many, cutting it off at 50")
            break

    return pod_prompt


def generate_log_prompt(
    theme: str,
    pod_name: str,
    pod_list: list[str],
    pod_template: pd.DataFrame,
    pod_structured: pd.DataFrame,
    record_num: int = 10,
) -> str:
    """
    Generate a prompt for log analysis based on the given parameters.

    Args:
        theme (str): The theme or context of the system.
        pod_name (str): The name of the pod being analyzed.
        pod_list (list[str]): List of all pod names in the system.
        pod_template (pd.DataFrame): DataFrame containing event templates.
        pod_structured (pd.DataFrame): DataFrame containing structured event data.
        record_num (int, optional): Number of example records to include. Defaults to 10.

    Returns:
        str: A formatted prompt for log analysis.
    """
    prompt = (
        f"In a {theme}, the following entities are included:\n\n"
        f"{', '.join(pod_list)}\n\n"
        f"The log information about the entity {pod_name} in the following format:\n\n"
        f"---\n"
        f"Event template: <|EventTemplate|>, with event ID <|EventId|>, occurred <|Occurrence|> times.\n\n"
        f"Here are some examples of this template:\n\n"
        f"- The event occurred at <|Time|>, and its content was <|Content|>.\n"
        f"- The event occurred at <|Time|>, and its content was <|Content|>.\n"
        f"---\n\n"
        f"Below are all the event templates and the examples they contain:\n\n"
        f"{generate_log_text(pod_template, pod_structured, record_num)}\n"
        f"Based on the above content, please provide your summary of this entity: {pod_name}, including:\n\n"
        f"- The role of the entity: {pod_name} in the system\n"
        f"- The key events that need to be noticed. Need to pay attention to both frequent and infrequent occurrences.\n"
        f"- The status of this entity\n"
        f"- The relationships this entity: "
        f"{pod_name} has with other entities that are shown in the above entities list. Only include the most likely relevant ones.\n\n"
        f"You only need to provide the information about this entity: {pod_name}.\n"
        f"Your response should be in the following format:\n\n"
        f"The name of the entity: <|entity_name|>\n"
        f"Role of the entity:\n <|Role|>\n\n"
        f"Key events that need to be noticed:\n"
        f"<|Key_Events|>\n\n"
        f"The status of this entity:\n"
        f"<|status|>\n\n"
        f"The relationships of entity {pod_name}: \n"
        f"<|Relationships|>\n\n"
        f"Your response:"
    )
    return prompt


def generate_pod_summary(
    theme: str,
    pod_name: str,
    log_dir: str,
    pod_list: list[str],
    record_num: int = 10,
    save_path: str = None,
) -> tuple[str, str]:
    """
    Generate a summary for a specific pod based on its log data.

    Args:
        theme (str): The theme or context of the system.
        pod_name (str): The name of the pod to summarize.
        log_dir (str): Directory containing the log files.
        pod_list (list[str]): List of all pod names in the system.
        record_num (int, optional): Number of example records to include. Defaults to 10.

    Returns:
        tuple[str, str]: A tuple containing the generated prompt and the AI's response.
    """
    pod_template = pd.read_csv(f"{log_dir}{pod_name}_messages_templates.csv")
    pod_structured = pd.read_csv(f"{log_dir}{pod_name}_messages_structured.csv")

    prompt = generate_log_prompt(
        theme, pod_name, pod_list, pod_template, pod_structured, record_num
    )
    client = OpenAIClient(OPENAI_API_KEY, model="gpt-4o-mini")
    response = client.inquire_LLMs(
        prompt,
        f"You are expert in the field of {theme}, and you are able to analyze the log file and provide the summary of the entity.",
        temperature=0.5,
    )
    if save_path:
        os.makedirs(save_path, exist_ok=True)
        open(f"{save_path}/{pod_name}_summary.txt", "w").write(response)

    return prompt, response


if __name__ == "__main__":
    day = "20210517"
    dataset_info = {
        "Product_Review": {
            "theme": "Microservice System for Product Review",
            "day": ["20210517", "20210524", "20211203", "20220606"],
            "Ground_Truth": [
                "catalogue",
                "catalogue",
                "mongodb-v1",
                "istio-ingressgateway",
            ],
        },
        "Cloud_Computing": {
            "theme": "Cloud Computing System",
            "day": ["20231207"],
            "Ground_Truth": ["productpage-v1"],
        },
    }

    dataset_name = "Product_Review"
    dataset_name = "Cloud_Computing"
    for day in dataset_info[dataset_name]["day"]:
        log_dir = f"./data/LEMMA_RCA/{dataset_name}/Log/{day}/"
        save_path = f"./cache/RAG_Database/Raw/{dataset_name}_{day}"
        theme = dataset_info[dataset_name]["theme"]
        dataframe = pd.read_csv(
            f"./data/LEMMA_RCA/{dataset_name}/Metrics/{dataset_name}_{day}.csv"
        )
        pod_list = list(dataframe.columns)

        for pod_name in pod_list:
            print(f"Generating summary for {pod_name} in {dataset_name}_{day}...")
            if pod_name == "Latency":
                continue
            prompt, response = generate_pod_summary(
                theme, pod_name, log_dir, pod_list, save_path=save_path
            )
