
import json
from pathlib import Path
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from src.FUNCTION.Tools.get_env import EnvManager
import datetime
import math
from fuzzywuzzy import fuzz


class PersonalChatAI:
    HISTORY_FILE_PATH = "./DATA/chat_history.json"
    AI_MODEL = EnvManager.load_variable("Chat_model")
    EMBEDDING_MODEL = EnvManager.load_variable("Embedding_model")
    SCORE_THRESHOLD = 0.6  # Adjust this threshold as needed
    MAX_HISTORY_SIZE = 100  # Limit history size

    def __init__(self):
        self.llm = ChatOllama(model=self.AI_MODEL, temperature=0)

    def get_current_timestamp(self):
        return datetime.datetime.now().isoformat()

    def load_chat_history(self):
        if Path(self.HISTORY_FILE_PATH).exists():
            with open(self.HISTORY_FILE_PATH, "r", encoding="utf-8") as file:
                return json.load(file)
        return []

    def save_chat_history(self, history):
        with open(self.HISTORY_FILE_PATH, "w", encoding="utf-8") as file:
            json.dump(history, file, indent=4)

    def ask_ai_importance(self, prompt: str) -> bool:
        """Ask AI if the chat message is important."""
        llm = ChatOllama(model=self.AI_MODEL, temperature=0, max_token=50)

        system_prompt = """
        You are an AI that determines whether a message contains personally significant information or emotional expression.

        You must respond ONLY with "yes" or "no".

        Here are some examples:

        User: "My name is Ravi and I live in Bangalore."  
        AI: yes

        User: "The weather is nice today."  
        AI: no

        User: "I'm feeling really anxious lately."  
        AI: yes

        User: "I love the book Homo Sapiens, it's my favorite."  
        AI: yes

        User: "Can you help me with a math problem?"  
        AI: no
        """

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Is this conversation important? {prompt}"},
        ]

        response = llm.invoke(messages)
        return "yes" in response.content.strip().lower()

    def store_important_chat(self, prompt: str, response: str, threshold=80):
        """Store chat in history if AI deems it important."""
        if self.ask_ai_importance(prompt):
            cur_date_time = self.get_current_timestamp()
            history = self.load_chat_history()
            for entry in history:
                if "user" in entry:
                    similarity_score = max(
                        fuzz.token_sort_ratio(prompt, entry["user"]),
                        fuzz.token_set_ratio(prompt, entry["user"])
                    )

                    if similarity_score >= threshold:
                        entry["assistant"] = response
                        entry["timestamp"] = cur_date_time
                        break
            else:
                history.append({"user": prompt, "assistant": response, "timestamp": cur_date_time})

            if len(history) > self.MAX_HISTORY_SIZE:
                history.pop(0)

            self.save_chat_history(history)

    def distance_to_similarity_inverted(self, distance, scale=1.0):
        """Sigmoid-based similarity mapping with inverted distance."""
        return 1 / (1 + math.exp(-distance * scale))

    def semantic_search(self, query: str):
        history = self.load_chat_history()
        if not history:
            return []

        embedding = OllamaEmbeddings(model=self.EMBEDDING_MODEL)

        combined_map = {
            item["user"] + " " + item["assistant"]: item
            for item in history if "user" in item and "assistant" in item
        }

        vectorstore = FAISS.from_texts(
            texts=list(combined_map.keys()),
            embedding=embedding,
        )

        results_with_scores = vectorstore.similarity_search_with_score(query, k=7)
        filtered_results = []
        for result, score in results_with_scores:
            similarity_score = self.distance_to_similarity_inverted(score)
            if similarity_score >= self.SCORE_THRESHOLD:
                filtered_results.append(combined_map[result.page_content])
        return filtered_results

    def message_management(self, query):
        system_prompt = """
            You are an AI assistant that remembers important details from previous conversations.
            When a user shares personal information (like their name, preferences, or interests), you should recall and use that naturally in responses — like a thoughtful friend would. 
            Avoid being overly formal or generic.
            Be warm, conversational, and use their name where appropriate."""

        messages = [{"role": "system", "content": system_prompt}]
        relevant_chats = self.semantic_search(query)

        if relevant_chats:
            for chat in relevant_chats:
                messages.append({"role": "user", "content": chat["user"]})
                messages.append({"role": "assistant", "content": chat["assistant"]})

        messages.append({"role": "user", "content": query})
        return messages




    def personal_chat_ai(self, first_query: str, max_token: int = 2000):
        """Chat system with persistent history and semantic retrieval."""
        try:
            query = first_query
            messages = self.message_management(query)
            llm = ChatOllama(model=self.AI_MODEL, temperature=0, max_token=max_token)

            while True:
                store = len(messages) < 100
                response_stream = llm.stream(messages)
                response_content = ""

                print("AI:", end=" ")
                for chunk in response_stream:
                    text = chunk.content
                    print(text, end="", flush=True)
                    response_content += text
                print()

                if store:
                    self.store_important_chat(query, response_content)

                query = input("YOU: ")
                if query.lower() in {"exit", "end"}:
                    break

                messages = self.message_management(query)

        except Exception as e:
            print(f"An error occurred: {e}")
            return None
        return True



if __name__ == "__main__":
    print("AI Chat Initialized. Type 'exit' to stop.")
    first_query = input("YOU: ")
    chat_bot = PersonalChatAI()
    chat_bot.personal_chat_ai(first_query)
    print("Chat session ended.")
