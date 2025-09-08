__import__('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.
import sys 
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3') # This is a workaround to fix the error "sqlite3 module is not found" on live streamlit.

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import TypedDict, List, Literal, Dict, Any
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from pdf_writer import generate_pdf

from crew import CrewClass, Essay

class GraphState(TypedDict):
    topic: str
    response: str
    documents: List[str]
    essay: Dict[str, Any]
    pdf_name: str


class RouteQuery(BaseModel):
    """Route a user query to direct answer or research."""

    way: Literal["edit_essay","write_essay", "answer"] = Field(
        ...,
        description="Given a user question choose to route it to write_essay, edit_essay or answer",
    )


class EssayWriter:
    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o-mini-2024-07-18", temperature=0)
        self.crew = CrewClass(llm=ChatOpenAI(model="gpt-4o-mini-2024-07-18", temperature=0.5))

        self.memory = ConversationBufferMemory()
        self.essay = {}
        self.router_prompt = """
                            You are a router and your duty is to route the user to the correct expert.
                            Always check conversation history and consider your move based on it.
                            If topic is something about memory, or daily talk route the user to the answer expert.
                            If topic starts something like can u write, or user request you write an article or essay, route the user to the write_essay expert.
                            If topic is user wants to edit anything in the essay, route the user to the edit_essay expert.
                            
                            \nConservation History: {memory}
                            \nTopic: {topic}
                            """

        self.simple_answer_prompt = """
                            You are an expert and you are providing a simple answer to the user's question.
                            
                            \nConversation History: {memory}
                            \nTopic: {topic}
                            """


        builder = StateGraph(GraphState)

        builder.add_node("answer", self.answer)
        builder.add_node("write_essay", self.write_essay)
        builder.add_node("edit_essay", self.edit_essay)


        builder.set_conditional_entry_point(self.router_query,
                                      {"write_essay": "write_essay",
                                                "answer": "answer",
                                                "edit_essay": "edit_essay"})
        builder.add_edge("write_essay", END)
        builder.add_edge("edit_essay", END)
        builder.add_edge("answer", END)

        self.graph = builder.compile()
        self.graph.get_graph().draw_mermaid_png(output_file_path="graph.png")


    def router_query(self, state: GraphState):
        print("**ROUTER**")
        prompt = PromptTemplate.from_template(self.router_prompt)
        memory = self.memory.load_memory_variables({})

        router_query = self.model.with_structured_output(RouteQuery)
        chain = prompt | router_query
        result:  RouteQuery = chain.invoke({"topic": state["topic"], "memory": memory})

        print("Router Result: ", result.way)
        return result.way

    def answer(self, state: GraphState):
        print("**ANSWER**")
        prompt = PromptTemplate.from_template(self.simple_answer_prompt)
        memory = self.memory.load_memory_variables({})
        chain = prompt | self.model | StrOutputParser()
        result = chain.invoke({"topic": state["topic"], "memory": memory})

        self.memory.save_context(inputs={"input": state["topic"]}, outputs={"output": result})
        return {"response": result}

    def write_essay(self, state: GraphState):
        print("**ESSAY COMPLETION**")

        self.essay = self.crew.kickoff({"topic": state["topic"]})

        self.memory.save_context(inputs={"input": state["topic"]}, outputs={"output": str(self.essay)})

        pdf_name = generate_pdf(self.essay)
        return {"response": "Here is your essay! ",  "pdf_name": f"{pdf_name}"}

    def edit_essay(self, state: GraphState):
        print("**ESSAY EDIT**")
        memory = self.memory.load_memory_variables({})

        user_request = state["topic"]
        parser = JsonOutputParser(pydantic_object=Essay)
        prompt = PromptTemplate(
            template=("Edit the Json file as user requested, and return the new Json file."
                     "\n Request:{user_request} "
                     "\n Conservation History: {memory}"
                     "\n Json File: {essay}"
                     " \n{format_instructions}"),
            input_variables=["memory","user_request","essay"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        chain = prompt | self.model | parser

        self.essay = chain.invoke({"user_request": user_request, "memory": memory, "essay": self.essay})


        self.memory.save_context(inputs={"input": state["topic"]}, outputs={"output": str(self.essay)})
        pdf_name = generate_pdf(self.essay)
        return {"response": "Here is your edited essay! ", "essay": self.essay, "pdf_name": f"{pdf_name}"}
