import os

from llama_index.core import (
    SimpleDirectoryReader,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from tavily import TavilyClient

from Client.OpenAiClient import OpenAIClient
from config import OPENAI_API_KEY, TAVILY_API_KEY
from Utils.data import load_data_from_csv
from web_utils.fetch_web_content import WebContentFetcher
from web_utils.llm_answer import GPTAnswer
from web_utils.retrieval import EmbeddingRetriever
import pandas as pd

os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY
# logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
# logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def search_web(query: str, output_format: str = "", profile: str = ""):
    print("Fetch web content based on the query")
    web_contents_fetcher = WebContentFetcher(query)
    web_contents, serper_response = web_contents_fetcher.fetch()

    print("Retrieve relevant documents using embeddings")
    retriever = EmbeddingRetriever()
    relevant_docs_list = retriever.retrieve_embeddings(
        web_contents, serper_response["links"], query
    )
    content_processor = GPTAnswer()
    formatted_relevant_docs = content_processor._format_reference(
        relevant_docs_list, serper_response["links"]
    )

    ai_message_obj = content_processor.get_answer(
        query,
        formatted_relevant_docs,
        serper_response["language"],
        output_format,
        profile,
    )
    answer = ai_message_obj.content + "\n"
    return answer


def collect_web_content(
    dataset_name: str, labels: list, loop_num: int = 3, use_tavily: bool = False
):
    previous_search_query = []
    for loop in range(loop_num):
        query_client = OpenAIClient(api_key=OPENAI_API_KEY)

        query_client_prompt = (
            f"Assume you have no prior knowledge about the {dataset_name} dataset and its nodes{','.join(labels)}. \n"
            f"You need to generate a queries for others"
            f"who can search web for information that will help you to summarize the dataset and nodes, and help you recognize the relationships between the nodes.\n"
            f"Split your query into multiple sub-questions. "
            f"Ensure each query is specific and clear, and easy to be used for search.\n"
            # f"Which question you will use to search for information?\n"
        )

        if len(previous_search_query) > 0:
            query_client_prompt += (
                f"You have inquired about this question before as follows:\n"
                f"{','.join(previous_search_query)}\n"
                f"Please try to avoid repeating these queries."
            )

        query_client_prompt += (
            "Generate a new query to get more information. Format your query as folows:\n"
            "Search Query: <new question>\n"
            "You should generate only one query at a time."
            "If you think no additional queries are needed, please return 'No question needed'."
        )

        print(query_client_prompt)

        query_system_prompt = "You are a helpful assistant who can generate a question to search for information."

        query_response = query_client.inquire_LLMs(
            query_client_prompt, query_system_prompt
        )

        print(query_response)
        if "Search Question" in query_response:
            search_query = (
                "Search Question: " + query_response.split("Search Question: ")[1]
            )
            previous_search_query.append(search_query)
            if use_tavily:
                tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
                web_content = tavily_client.qna_search(query=search_query)
            else:
                try:
                    web_content = search_web(search_query)
                except Exception as e:
                    print(f"Error: {e}, try to use Tavily to search")
                    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
                    web_content = tavily_client.qna_search(query=search_query)

            print(web_content)
            if not os.path.exists(f"./cache/RAG_Database/Raw/{dataset_name}"):
                os.makedirs(f"./cache/RAG_Database/Raw/{dataset_name}")

            open(
                f"./cache/RAG_Database/Raw/{dataset_name}/Search_{loop}.txt", "w"
            ).write(f"This text is searched by {search_query}\n" + web_content)
        else:
            return


def generate_dataset_summary(
    dataset_name: str,
    labels: list,
    database_path: str = "cache/RAG_Database/Raw",
    output_dir=None,
    embeddings_path: str = None,
    use_embeddings: bool = False,
    save_embeddings: bool = False,
):
    if use_embeddings:
        storage_context = StorageContext.from_defaults(
            persist_dir=embeddings_path + "/" + dataset_name
        )
        index = load_index_from_storage(storage_context)
    else:
        documents = SimpleDirectoryReader(f"{database_path}/{dataset_name}").load_data()
        index = VectorStoreIndex.from_documents(documents)

    query_engine = index.as_query_engine()

    summary_query = (
        f"Please provide a summary of the dataset {dataset_name} and their nodes including {','.join(labels)} using the knowledge from RAG Database."
        f"Your response should include detailed information on the dataset and each of its nodes."
        # f"If possible, please try to provide relationship between nodes after generate the summary of node."
        # f"Each Node should have their own summary. Your responce should include all the nodes."
        f"Follow the structured format below in your answer:\n"
        f"Dataset Summary: <summary of the dataset>\n"
        f"---\n"
        f"Summary of the <Node Name>: <summary of the nodes>\n"
        f"---\n"
        f"Summary of the <Node Name>: <summary of the nodes>\n"
        f"---\n"
        f"...\n"
        f"Additionally, try to include information on the relationships between the nodes"
        f"after you have summarized each one. Make sure to cover all the nodes mentioned."
    )
    summary_response = query_engine.query(summary_query).response

    if output_dir:
        open(f"{output_dir}/{dataset_name}_info.txt", "w").write(summary_response)
    if save_embeddings:
        index.storage_context.persist(persist_dir=embeddings_path + "/" + dataset_name)

    return summary_response


def split_summary_into_sub_questions(summary_response: str):
    dataset_summary = summary_response.split("---")[0].split("Dataset Summary: ")[1]
    node_summary_dict = {}
    for item in summary_response.split("---")[1:]:
        node_name = item.split("Summary of the ")[1].split(":")[0]
        node_summary = item.split("Summary of the ")[1].split(":")[1]
        node_summary_dict[node_name] = node_summary

    return dataset_summary, node_summary_dict


def request_web_information(dataset: str, labels: list, query_methods: str = "default"):
    if query_methods == "more_info":
        query = (
            f"Please provide detailed information of dataset {dataset} and its variables, including {', '.join(labels)}. "
            f"Try your best to search more web information if possible."
            "You should try your best to provide the information about each variable and their relationships with each other."
            "Then please provide more detailed information if possible."
        )
    elif query_methods == "default":
        query = f"Please provide detailed information of dataset {dataset} and its variables, including {', '.join(labels)}. "
    elif query_methods == "less_info":
        query = f"Please provide a summary of dataset {dataset} and its variables. "

    output_format = f"The summary of  dataset {dataset}:\n\n --- \n"
    for variable in labels:
        output_format += f"The summary of variable {variable}:\n\n --- \n"
    output_format += "---"
    profile = "You are a helpful assistant who can search the dataset information from the web and provide the detailed information of the dataset and its variables. You should exactly foolow the output format."

    answer = search_web(query, output_format, profile)
    open(f"./cache/{dataset}_data_info.txt", "w").write(answer)

    data_info = answer.split("---")[0]
    node_info = {}
    for index, variable in enumerate(labels):
        node_info[variable] = answer.split("---")[index + 1]
        if variable not in node_info[variable]:
            raise ValueError(f"Variable {variable} not found in node_info")

    return data_info, node_info


if __name__ == "__main__":
    data_theme = {
        "Auto_MPG": "Gasoline consumption",
        "DWD_climate": "Climate change",
        "Sachs": "Biology",
        "asia": "Lung Cancer",
        "child": "Infant Health Status",
    }

    for dataset_name in data_theme.keys():
        data, GTmatrix, labels = load_data_from_csv(dataset_name)
        # request_web_information(dataset_name, labels, query_methods="default")
        collect_web_content(dataset_name, labels, loop_num=5, use_tavily=False)
        print(
            split_summary_into_sub_questions(
                generate_dataset_summary(
                    dataset_name,
                    labels,
                    output_dir="./cache/Summarized_info",
                    embeddings_path="./cache/RAG_Database/Embeddings",
                    save_embeddings=True,
                )
            )
        )

    # !This part is used for LEMMA_RCA dataset
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

    # dataset_name = "Product_Review"
    dataset_name = "Cloud_Computing"
    for day in dataset_info[dataset_name]["day"]:
        log_dir = f"./data/LEMMA_RCA/{dataset_name}/Log/{day}/"
        save_path = f"./cache/RAG_Database/Raw/{dataset_name}_{day}"
        theme = f"Microservice System for {dataset_name}"
        dataframe = pd.read_csv(
            f"./data/LEMMA_RCA/{dataset_name}/Metrics/{dataset_name}_{day}.csv"
        )
        labels = list(dataframe.columns)

        # collect_web_content(
        #     f"{dataset_name}_{day}", labels, loop_num=5, use_tavily=False
        # )
        print(labels)
        print(
            split_summary_into_sub_questions(
                generate_dataset_summary(
                    f"{dataset_name}_{day}",
                    labels,
                    output_dir="./cache/Summarized_info",
                    embeddings_path="./cache/RAG_Database/Embeddings",
                    save_embeddings=True,
                )
            )
        )
