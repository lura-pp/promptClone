from airflow.sdk import chain, dag, task, Asset
from pendulum import datetime, duration

COLLECTION_NAME = "Books"
BOOK_DESCRIPTION_FOLDER = "include/data"
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"


def _my_callback_func(context):
    task_instance = context["task_instance"]
    dag_run = context["dag_run"]
    print(
        f"CALLBACK: Task {task_instance.task_id} "
        f"failed in DAG {dag_run.dag_id} at {dag_run.start_date}"
    )


@dag(
    start_date=datetime(2025, 6, 1),
    schedule="@hourly",
    default_args={
        "retries": 1,
        "retry_delay": duration(seconds=10),
        "on_failure_callback": _my_callback_func,
    },
    on_failure_callback=_my_callback_func,
)
def fetch_data():

    @task(retries=5, retry_delay=duration(seconds=2))
    def create_collection_if_not_exists() -> None:
        # print(10/0)
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook

        hook = WeaviateHook("my_weaviate_conn")
        client = hook.get_conn()

        existing_collections = client.collections.list_all()
        existing_collection_names = existing_collections.keys()

        if COLLECTION_NAME not in existing_collection_names:
            print(f"Collection {COLLECTION_NAME} does not exist yet. Creating it...")
            collection = client.collections.create(name=COLLECTION_NAME)
            print(f"Collection {COLLECTION_NAME} created successfully.")
            print(f"Collection details: {collection}")

    _create_collection_if_not_exists = create_collection_if_not_exists()

    @task
    def list_book_description_files() -> list:
        import os

        book_description_files = [
            f for f in os.listdir(BOOK_DESCRIPTION_FOLDER) if f.endswith(".txt")
        ]
        return book_description_files

    _list_book_description_files = list_book_description_files()

    @task
    def transform_book_description_files(book_description_file: str) -> str:
        import json
        import os

        with open(
            os.path.join(BOOK_DESCRIPTION_FOLDER, book_description_file), "r"
        ) as f:
            book_descriptions = f.readlines()

        titles = [
            book_description.split(":::")[1].strip()
            for book_description in book_descriptions
        ]
        authors = [
            book_description.split(":::")[2].strip()
            for book_description in book_descriptions
        ]
        book_description_text = [
            book_description.split(":::")[3].strip()
            for book_description in book_descriptions
        ]

        book_descriptions = [
            {
                "title": title,
                "author": author,
                "description": description,
            }
            for title, author, description in zip(
                titles, authors, book_description_text
            )
        ]

        return book_descriptions

    _transform_book_description_files = transform_book_description_files.expand(
        book_description_file=_list_book_description_files
    )

    @task
    def create_vector_embeddings(book_data: list) -> list:
        from fastembed import TextEmbedding

        embedding_model = TextEmbedding(EMBEDDING_MODEL_NAME)

        book_descriptions = [book["description"] for book in book_data]
        description_embeddings = [
            list(map(float, next(embedding_model.embed([desc]))))
            for desc in book_descriptions
        ]

        return description_embeddings

    _create_vector_embeddings = create_vector_embeddings.expand(
        book_data=_transform_book_description_files
    )

    @task(outlets=[Asset("my_book_vector_data")], trigger_rule="all_done")
    def load_embeddings_to_vector_db(
        list_of_book_data: list, list_of_description_embeddings: list
    ) -> None:
        from airflow.providers.weaviate.hooks.weaviate import WeaviateHook
        from weaviate.classes.data import DataObject

        hook = WeaviateHook("my_weaviate_conn")
        client = hook.get_conn()
        collection = client.collections.get(COLLECTION_NAME)

        for book_data_list, emb_list in zip(
            list_of_book_data, list_of_description_embeddings
        ):
            items = []

            for book_data, emb in zip(book_data_list, emb_list):
                item = DataObject(
                    properties={
                        "title": book_data["title"],
                        "author": book_data["author"],
                        "description": book_data["description"],
                    },
                    vector=emb,
                )
                items.append(item)

            collection.data.insert_many(items)

    _load_embeddings_to_vector_db = load_embeddings_to_vector_db(
        list_of_book_data=_transform_book_description_files,
        list_of_description_embeddings=_create_vector_embeddings,
    )

    chain(_create_collection_if_not_exists, _load_embeddings_to_vector_db)


fetch_data()
