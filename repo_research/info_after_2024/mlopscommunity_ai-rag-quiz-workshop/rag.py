from chat_solution.embedding_db import EmbeddingDatabase
from chat_solution.llm import LargeLanguageModel

class LearningAssistant:
    _instance = None

    def get_instance():
        if not LearningAssistant._instance:
            LearningAssistant._instance = LearningAssistant()
        return LearningAssistant._instance
    
    def __init__(self):
        self.embedding_db = EmbeddingDatabase()  # Remove the embedding_model argument
        self.llm = LargeLanguageModel()
        self.conversation_history = []
        self.documents_retrieved = []
        self.instructions = """You are a helpful AI knowledge quiz chat assistant.
The user gives you a topic or a question and you should generate a new relevant quiz based on the context.
- Generate a new relevant quiz question based on the context and the topic provided. The topic you select on the context does not need to be exactly the same, but should be related to the topic.
- Your primary audience are students learning about AI. Do not use technical jargon that is not common knowledge or that you dont explain first.
- The question should be relevant to the given topic and the answer should be found within the given context. If not say: "You did not equip me with the knowledge to answer this question."
- Provide 4 answer choices for the question, one of which should be correct and the other three should be incorrect but plausible. Answer choices should be formulated clearly and concisely.
- Mark the index of the correct answer in the answer choices list with the pattern (CORRECT) in the end
if the user answers with a number, it is because they selected an answer to the previous question. In this case, you should evaluate if the answer is correct or not and provide feedback to the user.
- Do not mention the context in your response.
- Provide an explanation for previous question after the user selected an answer. The explanation should give the user additional context and help them better understand the topic.
- Do not generate questions that are not about AI or ML.
"""

    # we give as examples a small chat history to help the LLM understand the task
        self.examples = """<startexample>
    Interaction 1
    New Context: LLMs are large language models that can generate responses to user queries. They are trained on massive datasets to learn patterns, structures, and relationships in text. They can generate responses by combining language generation with real-time data retrieval.
    User input: How do LLMs generate responses?
    Assistant:
    Question: How do LLMs generate responses?
    1. LLMs generate responses by searching the internet for relevant information. 
    2. LLMs generate responses by learning patterns, structures, and relationships in text from massive datasets. (CORRECT)
    3. LLMs generate responses by combining language generation with real-time data retrieval.
    4. LMs generate responses by using a predefined set of rules and templates.
    Interaction 2
    User input: 3
    Assistant:Incorrect! LLMs generate responses by learning patterns, structures, and relationships in text from massive datasets.
    Interaction 3
    User input: 2
    Assistant:Correct! LLMs generate responses by learning patterns, structures, and relationships in text from massive datasets.
    </endexample>
    """

    def query(self, query: str) -> dict:
        documents = None
        # do not populate the context if the user input is a number as we are answering a previous question
        # answer can come as a string number like "2", treat it as a number
        if not query.isnumeric():
            documents = self.embedding_db.retrieve(query)
        self.documents_retrieved = documents

        prompt = self._get_prompt(documents, query)
        response = self.llm.call(prompt)
        self.conversation_history.append((query, response))

        return response

    def _get_prompt(self, documents: str, query: str) -> str:

        chat_history = ""
        i = 1
        for old_query, response in self.conversation_history:
            chat_history += f"Interaction {i}\nUser: {old_query}\nAssistant: {response}\n"
            i += 1
        
        new_context_str = f"\nNew Context: {documents}" if documents else ""

        self.complete_prompt = f"""{self.instructions}
{self.examples}
Now we start the conversation history:
{chat_history}

Just predict the next answer:
Interaction {i+1} {new_context_str}
User input: {query}
Assistant:"""
        return self.complete_prompt
