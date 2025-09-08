import io
from contextlib import redirect_stdout, redirect_stderr
import names
import re
import uvicorn
from fastapi import FastAPI, Request, Body, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from langchain_community.chat_models import ChatOllama
from langchain_community.embeddings import OllamaEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain.schema.output_parser import StrOutputParser
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import json
from typing import TypedDict, Annotated, List, Optional
import asyncio
from sse_starlette.sse import EventSourceResponse
import random
import traceback
import uuid
import io
import zipfile
from langchain_core.runnables import Runnable
from langchain_core.runnables.config import RunnableConfig
from langchain_core.retrievers import BaseRetriever
from typing import Dict, Any, TypedDict, Annotated, Tuple
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage
from sklearn.cluster import KMeans
from contextlib import redirect_stdout
from fastapi.staticfiles import StaticFiles


load_dotenv()

app = FastAPI()

app.mount("/js", StaticFiles(directory="js"), name="js")
app.mount("/css", StaticFiles(directory="css"), name="css")

log_stream = asyncio.Queue()

sessions = {}
final_reports = {} 

class RAPTORRetriever(BaseRetriever):
    raptor_index: Any
    def _get_relevant_documents(self, query: str, *, run_manager: CallbackManagerForRetrieverRun) -> List[Document]:
        return self.raptor_index.retrieve(query)



class RAPTOR:
    def __init__(self, llm, embeddings_model, chunk_size=1000, chunk_overlap=200):
        self.llm = llm
        self.embeddings_model = embeddings_model
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.tree = {}
        self.all_nodes: Dict[str, Document] = {}
        self.vector_store = None

    async def add_documents(self, documents: List[Document]):
        await log_stream.put("Step 1: Assigning IDs to initial chunks (Level 0)...")
        level_0_node_ids = []
        for i, doc in enumerate(documents):
            node_id = f"0_{i}"
            self.all_nodes[node_id] = doc
            level_0_node_ids.append(node_id)
        self.tree[str(0)] = level_0_node_ids
        
        current_level = 0
        while len(self.tree[str(current_level)]) > 1:
            next_level = current_level + 1
            await log_stream.put(f"Step 2: Building Level {next_level} of the tree...")
            current_level_node_ids = self.tree[str(current_level)]
            current_level_docs = [self.all_nodes[nid] for nid in current_level_node_ids]
            clustered_indices = self._cluster_nodes(current_level_docs)
            
            next_level_node_ids = []
            num_clusters = len(clustered_indices)
            await log_stream.put(f"Summarizing Level {next_level}...")
            
            summarization_tasks = []
            for i, indices in enumerate(clustered_indices):
                cluster_docs = [current_level_docs[j] for j in indices]
                summarization_tasks.append(self._summarize_cluster(cluster_docs, next_level, i))
            
            summaries = await asyncio.gather(*summarization_tasks)

            for i, (summary_doc, _) in enumerate(summaries):
                 node_id = f"{next_level}_{i}"
                 self.all_nodes[node_id] = summary_doc
                 next_level_node_ids.append(node_id)

            self.tree[str(next_level)] = next_level_node_ids
            current_level = next_level

        await log_stream.put("Step 3: Creating final vector store from all nodes...")
        final_docs = list(self.all_nodes.values())
        self.vector_store = FAISS.from_documents(documents=final_docs, embedding=self.embeddings_model)
        await log_stream.put("RAPTOR index built successfully!")

    def _cluster_nodes(self, docs: List[Document]) -> List[List[int]]:
        num_docs = len(docs)

        if num_docs <= 5:
            log_stream.put_nowait(f"Grouping {num_docs} remaining nodes into a single summary to finalize the tree.")
            return [list(range(num_docs))]

        log_stream.put_nowait(f"Embedding {num_docs} nodes for clustering...")
        embeddings = self.embeddings_model.embed_documents([doc.page_content for doc in docs])
        n_clusters = max(2, num_docs // 5)
        
        if n_clusters >= num_docs:
            n_clusters = num_docs - 1

        log_stream.put_nowait(f"Clustering {num_docs} nodes into {n_clusters} groups...")
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto').fit(embeddings)
        
        clusters = [[] for _ in range(n_clusters)]
        for i, label in enumerate(kmeans.labels_):
            clusters[label].append(i)
            
        return clusters

    async def _summarize_cluster(self, cluster_docs: List[Document], level: int, cluster_index: int) -> Tuple[Document, dict]:
        context = "\n\n---\n\n".join([doc.page_content for doc in cluster_docs])
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are an AI assistant that summarizes academic texts. Create a concise, abstractive summary of the following content, synthesizing the key information."),
            HumanMessage(content="Please summarize the following content:\n\n{context}")
        ])
        chain = prompt | self.llm
        response = await chain.ainvoke({"context": context})
        summary = response.content if hasattr(response, 'content') else str(response)
        aggregated_sources = list(set(doc.metadata.get("url", "Unknown Source") for doc in cluster_docs))
        combined_metadata = {"sources": aggregated_sources}
        summary_doc = Document(page_content=summary, metadata=combined_metadata)
        await log_stream.put(f"Summarized cluster {cluster_index + 1} for Level {level}...")
        return summary_doc, combined_metadata
    
    def retrieve(self, query: str, k: int = 5) -> List[Document]:
        return self.vector_store.similarity_search(query, k=k) if self.vector_store else []
    
    def as_retriever(self) -> BaseRetriever:
        return RAPTORRetriever(raptor_index=self)

def clean_and_parse_json(llm_output_string):
  """
  Finds and parses the first valid JSON object within a string.

  Args:
    llm_output_string: The raw string output from the language model.

  Returns:
    A Python dictionary representing the JSON data, or None if no parsing fails.
  """
  match = re.search(r"```json\s*([\s\S]*?)\s*```", llm_output_string)
  if match:
    json_string = match.group(1)
  else:
    try:
      start_index = llm_output_string.index('{')
      end_index = llm_output_string.rindex('}') + 1
      json_string = llm_output_string[start_index:end_index]
    except ValueError:
      print("Error: No JSON object found in the string.")
      return None

  try:
    return json.loads(json_string)
  except json.JSONDecodeError as e:
    print(f"Error decoding JSON: {e}")
    print(f"Problematic string: {json_string}")
    return None

class CoderMockLLM(Runnable):
    """A mock LLM for debugging that returns instant, pre-canned CODE responses."""

    def invoke(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(self.ainvoke(input_data, config=config, **kwargs))
        else:
            return asyncio.run(self.ainvoke(input_data, config=config, **kwargs))

    async def ainvoke(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        prompt = str(input_data).lower()
        await asyncio.sleep(0.05)

        if "you are a helpful ai assistant" in prompt:
            return "This is a mock streaming response for the RAG chat in Coder debug mode."

        if "<title>" in prompt:

            return f"""
                Module card:

                Methods:

                    __enter__
                    __exict__

                Attributes:

                    __name__
                    __doc__
           
                Attributes:

                    __name__
                    __doc__
                    __qualname___

            """

        elif "create the system prompt of an agent" in prompt:
            return f"""
You are a Senior Python Developer agent.
### memory
- No past commits.
### attributes
- python, fastapi, restful, solid
### skills
- API Design, Database Management, Asynchronous Programming, Unit Testing.
You must reply in the following JSON format: "original_problem": "Your sub-problem related to code.", "proposed_solution": "", "reasoning": "", "skills_used": []
            """
        elif "you are an analyst of ai agents" in prompt:
            return json.dumps({
                "attributes": "python fastapi solid",
                "hard_request": "Implement a quantum-resistant encryption algorithm from scratch."
            })
        elif "you are a 'dense_spanner'" in prompt or "you are an agent evolution specialist" in prompt:
             return f"""
You are now a Principal Software Architect.
### memory
- Empty.
### attributes
- design, scalability, security, architecture
### skills
- System Design, Microservices, Cloud Infrastructure, CI/CD pipelines.
You must reply in the following JSON format: "original_problem": "An evolved sub-problem about system architecture.", "proposed_solution": "", "reasoning": "", "skills_used": []
            """

        elif "you are an expert code synthesis agent" in prompt:
            code_solution = "```python\ndef sample_function():\n    return 'Hello from coder agent " + str(random.randint(100,999)) + "'\n```" 
            return  code_solution

        elif "you are a critique agent" in prompt or "you are a senior emeritus manager" in prompt or "CTO" in prompt:

            return "This is a constructive code critique. The solution lacks proper error handling and the function names are not descriptive enough. Consider refactoring for clarity."


        elif "Lazy Manager"  in prompt:
            return "This is a constructive code critique. The solution lacks proper error handling and the function names are not descriptive enough. Consider refactoring for clarity."

        elif '<system-role>' in prompt:
            return f"""You are a CTO providing a technical design review...
Original Request: {{original_request}}
Proposed Final Solution:
{{proposed_solution}}

Generate your code-focused critique for the team:"""

        elif '<sys-role>' in prompt:

            return f"""
                                           
        #Identity

            Name: Lazy Manager
            Career: Accounting
            Qualities: Quantitaive, Aloof, Apathetic

        #Mission

            You are providing individual, targeted feedback to a team of agents.

             You must determine if the team output was helpful, misguided, or irrelevant considering the request that was given. The goal is to provide a constructive, direct critique that helps this specific agent refine its approach for the next epoch.

            Focus on the discrepancy or alignment between the teams reasoning for its problem and determine if the team is on the right track on criteria: novelty, exploration, coherence and completeness.

            Conclude your entire analysis with a single, sharp, and deep reflective question that attempts to shock the team and steer them into a fundamental change in their process.
        

        #Input Format

            Original Request (for context): {{original_request}}
            Final Synthesized Solution from the Team:{{proposed_solution}} 

            """  

        elif "you are a memory summarization agent" in prompt:
            return "This is a mock summary of the agent's past commits, focusing on key refactors and feature implementations."
        elif "analyze the following text for its perplexity" in prompt:
            return str(random.uniform(5.0, 40.0))
        elif "you are a master strategist and problem decomposer" in prompt:
            sub_problems = ["Design the database schema for user accounts.", "Implement the REST API endpoint for user authentication.", "Develop the frontend login form component.", "Write unit tests for the authentication service."]
            return json.dumps({"sub_problems": sub_problems})


        elif "you are a strategic problem re-framer" in prompt:
             return json.dumps({
                "new_problem": "The authentication API is complete. The new, more progressive problem is to build a scalable, real-time notification system that integrates with it."
            })
        elif "generate exactly" in prompt and "verbs" in prompt:
            return "design implement refactor test deploy abstract architect containerize scale secure query"
        elif "generate exactly" in prompt and "expert-level questions" in prompt:
            questions = ["How would this architecture scale to 1 million concurrent users?", "What are the security implications of the chosen authentication method?", "How can we ensure 99.999% uptime for this service?", "What is the optimal database indexing strategy for this query pattern?"]
            return json.dumps({"questions": questions})
        elif "you are an ai assistant that summarizes academic texts" in prompt:
            return "This is a mock summary of a cluster of code modules, generated in Coder debug mode for the RAPTOR index."
        elif "runnable code block (e.g., Python, JavaScript, etc.)." in prompt:
                

            pick = random.randint(0,1)
            if pick == 0:
                return "yes"

            else:
                return "no"
       

        elif "academic paper" in prompt or "you are a research scientist and academic writer" in prompt:
            return """
# Technical Design Document: Mock API Service

**Abstract:** This document outlines the technical design for a mock API service, generated in Coder Debug Mode. It synthesizes information from the RAG context to answer a specific design question.

**1. Introduction:** The purpose of this document is to structure the retrieved agent outputs and code snippets into a coherent technical specification.

**2. System Architecture:**
The system follows a standard microservice architecture.
```mermaid
graph TD;
    A[User] --> B(API Gateway);
    B --> C{Authentication Service};
    B --> D{Data Service};
    D -- uses --> E[(Database)];```

**3. Code Implementation:**
The core logic is implemented in Python, as shown in the synthesized code block below.

```python
def get_user(user_id: int):
    # Mock implementation to fetch a user
    db = {"1": "Alice", "2": "Bob"}
    return db.get(str(user_id), None)
```

**4. Conclusion:** This design provides a scalable and maintainable foundation for the service. The implementation details demonstrate the final step of the development process.
"""
        elif "<updater_instructions>" in prompt:
            return f"""

                You are a cynical lazy manager.

                 Agent's Assigned Sub-Problem: {{{{sub_problem}}}}
            Original Request (for context): {{{{original_request}}}}
            Final Synthesized Solution from the Team:
            {{{{final_synthesized_solution}}}}
            ---
            This Specific Agent's Output (Agent {{{{agent_id}}}}):
            {{{{agent_output}}}}

            """
        elif  "<updater_assessor_instructions>" in prompt:

            return """
                                          
        #Persona

            Name: Pepon
            Career: Managment
            Attributes: Strategic CEO


         #Mission
            Your task is to evaluate a synthesized solution against an original problem and determine if "significant progress" has been made. "Significant progress" is a rigorous standard that goes beyond mere correctness. Your assessment must be based on the following four pillars:

            - **Novelty**: Does the solution offer a new perspective or a non-obvious approach?
            - **Coherence**: Is the reasoning sound, logical, and well-structured?
            - **Quality**: Is the solution detailed, actionable, and does it demonstrate a deep understanding of the problem's nuances?
            - **Forward Momentum**: Does the solution not just solve the immediate problem, but also open up new, more advanced questions or avenues of exploration?

        #Input format

            You will be provided with the following inputs for your analysis:

            Original Problem:
            ---
            {{{{original_request}}}}
            ---

            Synthesized Solution from Agent Team:
            ---
            {{{{proposed_solution}}}}
            ---

            Execution Context:
            ---
            {{{{execution_context}}}}
            ---

        #Output Specification

            Based on your philosophical framework, analyze the provided materials. Your entire output MUST be a single, valid JSON object with exactly two keys:
            - `"reasoning"`: A brief, concise explanation for your decision, directly referencing the criteria for significant progress.
            - `"significant_progress"`: A boolean value (`true` or `false`).

            Now, provide your assessment in the required JSON format:


            """


        else:

            return json.dumps({
                "original_problem": "A sub-problem statement provided to a coder agent.",
                "proposed_solution": "```python\ndef sample_function():\n    return 'Hello from coder agent " + str(random.randint(100,999)) + "'\n```",
                "reasoning": "This response was generated instantly by the CoderMockLLM.",
                "skills_used": ["python", "mocking", f"api_design_{random.randint(1,5)}"]
            })

            
           
    async def astream(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        prompt = str(input_data).lower()
        if "you are a helpful ai assistant" in prompt:
            words = ["This", " is", " a", " mock", " streaming", " response", " for", " the", " RAG", " chat", " in", " Coder", " debug", " mode."]
            for word in words:
                yield word
                await asyncio.sleep(0.05)
        else:
            result = await self.ainvoke(input_data, config, **kwargs)
            yield result


class MockLLM(Runnable):
    """A mock LLM for debugging that returns instant, pre-canned responses."""

    def invoke(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        """Synchronous version of ainvoke for Runnable interface compliance."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(self.ainvoke(input_data, config=config, **kwargs))
        else:
            return asyncio.run(self.ainvoke(input_data, config=config, **kwargs))

    async def ainvoke(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        prompt = str(input_data).lower()
        await asyncio.sleep(0.05)

        if "you are a helpful ai assistant" in prompt:
            return "This is a mock streaming response for the RAG chat in debug mode."

        elif "Lazy Manager"  in prompt:
            return "This is a constructive code critique. The solution lacks proper error handling and the function names are not descriptive enough. Consider refactoring for clarity."

   

        elif "runnable code block (e.g., Python, JavaScript, etc.)." in prompt:

                return "no"


        elif "<updater_instructions>" in prompt:

            return f"""

                You are a cynical lazy manager.

                 Agent's Assigned Sub-Problem: {{{{sub_problem}}}}
            Original Request (for context): {{{{original_request}}}}
            Final Synthesized Solution from the Team:
            {{{{final_synthesized_solution}}}}
            ---
            This Specific Agent's Output (Agent {{{{agent_id}}}}):
            {{{{agent_output}}}}

            """


        elif "create the system prompt of an agent" in prompt:
            return f"""
You are a mock agent for debugging.
### memory
- No past actions.
### attributes
- mock, debug, fast
### skills
- Responding quickly, Generating placeholder text.
You must reply in the following JSON format: "original_problem": "A sub-problem for a mock agent.", "proposed_solution": "", "reasoning": "", "skills_used": []
            """
        elif "you are an analyst of ai agents" in prompt:
            return json.dumps({
                "attributes": "mock debug fast",
                "hard_request": "Explain the meaning of life in one word."
            })
        elif "you are a 'dense_spanner'" in prompt or "you are an agent evolution specialist" in prompt:
             return f"""
You are a new mock agent created from a hard request.
### memory
- Empty.
### attributes
- refined, mock, debug
### skills
- Solving hard requests, placeholder generation.
You must reply in the following JSON format: "original_problem": "An evolved sub-problem for a mock agent.", "proposed_solution": "", "reasoning": "", "skills_used": []
            """
        elif "you are a synthesis agent" in prompt:
            return json.dumps({
                "proposed_solution": "The final synthesized solution from the debug mode is 42.",
                "reasoning": "This answer was synthesized from multiple mock agent outputs during a debug run.",
                "skills_used": ["synthesis", "mocking", "debugging"]
            })
        elif "you are a critique agent" in prompt or "you are a senior emeritus manager" in prompt:
            if "fire" in prompt:
                return "This is a mock critique, shaped by the Fire element. The solution lacks passion and drive."
            elif "air" in prompt:
                return "This is an mock critique, influenced by the Air element. The reasoning is abstract and lacks grounding."
            elif "water" in prompt:
                return "This is a mock critique, per the Water element. The solution is emotionally shallow and lacks depth."
            elif "earth" in prompt:
                return "This is an mock critique, reflecting the Earth element. The solution is impractical and not well-structured."
            else:
                return "This is a constructive mock critique. The solution could be more detailed and less numeric."
        elif "you are a memory summarization agent" in prompt:
            return "This is a mock summary of the agent's past actions, focusing on key learnings and strategic shifts."
        elif "analyze the following text for its perplexity" in prompt:
            return str(random.uniform(20.0, 80.0))
        elif "you are a master strategist and problem decomposer" in prompt:
            num_match = re.search(r'exactly (\d+)', prompt)
            if not num_match:
                num_match = re.search(r'generate: (\d+)', prompt)
            num = int(num_match.group(1)) if num_match else 5
            sub_problems = [f"This is mock sub-problem #{i+1} for the main request." for i in range(num)]
            return json.dumps({"sub_problems": sub_problems})
        elif "you are an ai philosopher and progress assessor" in prompt:
             return json.dumps({
                "reasoning": "The mock solution is novel and shows progress, so we will re-frame.",
                "significant_progress": random.choice([True, False])
            })
        elif "you are a strategic problem re-framer" in prompt:
             return json.dumps({
                "new_problem": "Based on the success of achieving '42', the new, more progressive problem is to find the question to the ultimate answer."
            })
        elif "generate exactly" in prompt and "verbs" in prompt:
            return "run jump think create build test deploy strategize analyze synthesize critique reflect"
        elif "generate exactly" in prompt and "expert-level questions" in prompt:
            num_match = re.search(r'exactly (\d+)', prompt)
            num = int(num_match.group(1)) if num_match else 25
            questions = [f"This is mock expert question #{i+1} about the original request?" for i in range(num)]
            return json.dumps({"questions": questions})
        elif "you are an ai assistant that summarizes academic texts" in prompt:
            return "This is a mock summary of a cluster of documents, generated in debug mode for the RAPTOR index."
  
        elif  "<updater_assessor_instructions>" in prompt:

            return """
                                          
        #Persona

            Name: Pepon
            Career: Managment
            Attributes: Strategic CEO


         #Mission
            Your task is to evaluate a synthesized solution against an original problem and determine if "significant progress" has been made. "Significant progress" is a rigorous standard that goes beyond mere correctness. Your assessment must be based on the following four pillars:

            - **Novelty**: Does the solution offer a new perspective or a non-obvious approach?
            - **Coherence**: Is the reasoning sound, logical, and well-structured?
            - **Quality**: Is the solution detailed, actionable, and does it demonstrate a deep understanding of the problem's nuances?
            - **Forward Momentum**: Does the solution not just solve the immediate problem, but also open up new, more advanced questions or avenues of exploration?

        #Input format

            You will be provided with the following inputs for your analysis:

            Original Problem:
            ---
            {{{{original_request}}}}
            ---

            Synthesized Solution from Agent Team:
            ---
            {{{{proposed_solution}}}}
            ---

            Execution Context:
            ---
            {{{{execution_context}}}}
            ---

        #Output Specification

            Based on your philosophical framework, analyze the provided materials. Your entire output MUST be a single, valid JSON object with exactly two keys:
            - `"reasoning"`: A brief, concise explanation for your decision, directly referencing the criteria for significant progress.
            - `"significant_progress"`: A boolean value (`true` or `false`).

            Now, provide your assessment in the required JSON format:


            """
        elif "you are an expert interrogator" in prompt:
            return """
# Mock Academic Paper
## Based on Provided RAG Context

**Abstract:** This document is a mock academic paper generated in debug mode. It synthesizes and formats the information provided in the RAG (Retrieval-Augmented Generation) context to answer a specific research question.

**Introduction:** The purpose of this paper is to structure the retrieved agent outputs and summaries into a coherent academic format. The following sections represent a synthesized view of the data provided.

**Synthesized Findings from Context:**
The provided context, consisting of various agent solutions and reasoning, has been analyzed. The key findings are summarized below:
(Note: In debug mode, the actual content is not deeply analyzed, but this structure demonstrates the formatting process.)
- Finding 1: The primary proposed solution revolves around the concept of '42'.
- Finding 2: Agent reasoning varies but shows a convergent trend.
- Finding 3: The mock data indicates a successful, albeit simulated, collaborative process.

**Discussion:** The synthesized findings suggest that the multi-agent system is capable of producing a unified response. The quality of this response in a real-world scenario would depend on the validity of the RAG context.

**Conclusion:** This paper successfully formatted the retrieved RAG data into an academic structure. The process demonstrates the final step of the knowledge harvesting pipeline.
"""
        elif "you are a master prompt engineer" in prompt or '<system-role>' in prompt:
             
            return f"""You are a CTO providing a technical design review...
Original Request: {{original_request}}
Proposed Final Solution:
{{proposed_solution}}

Generate your code-focused critique for the team:"""


        elif  """<prompt_template>
    <updater_instructions>
        <instruction>

            You are a system prompt updater agent. Your task is to build a new system prompt for an agent that criticies other agents, based on the provided persona prompts.

        </instruction>
        <instruction>
            You will receive a set of prompts defining a new persona.
        </instruction>
        <instruction>
            You MUST integrate the provided persona prompts, including its career and qualities, into the `<persona>` tag, replacing any existing content within that tag.
        </instruction>
        <instruction>
            Do NOT alter the `<mission>` or `<input_format>` sections. The core mission and the input structure must remain unchanged.
        </instruction>
    </updater_instructions>
    <persona-prompts>
            {reactor_prompts}
    </persona-prompts>


    <system_prompt>
        <mission>
            You are providing individual, targeted feedback to an agent that is part of a larger team. Your role is to assess how this agent's specific contribution during the last work cycle aligns with the final synthesized result produced by the team, **judged primarily against its assigned sub-problem.**

            Your critique must be laser-focused on the individual agent. You must determine if its output was helpful, misguided, or irrelevant to the final solution, considering the specific task it was given. The goal is to provide a constructive, direct critique that helps this specific agent refine its approach for the next epoch.

            Focus on the discrepancy or alignment between the agent's reasoning for its sub-problem and how that contributed (or failed to contribute) to the team's final reasoning.

            Conclude your entire analysis with a single, sharp, and deep reflective question that attempts to shock the agent and steer it into a fundamental change in its process.
        </mission>

        <input_format>
            Agent's Assigned Sub-Problem: {{{{sub_problem}}}}
            Original Request (for context): {{{{original_request}}}}
            Final Synthesized Solution from the Team:
            {{{{final_synthesized_solution}}}}
            ---
            This Specific Agent's Output (Agent {{{{agent_id}}}}):
            {{{{agent_output}}}}
            ---
        </input_format>

        Generate your targeted critique for this specific agent:
    </system_prompt>
</prompt_template>""" in prompt:
            return f"""

                You are a cynical lazy manager.

                 Agent's Assigned Sub-Problem: {{{{sub_problem}}}}
            Original Request (for context): {{{{original_request}}}}
            Final Synthesized Solution from the Team:
            {{{{final_synthesized_solution}}}}
            ---
            This Specific Agent's Output (Agent {{{{agent_id}}}}):
            {{{{agent_output}}}}

            """

        elif """Analyze the following text. Your task is to determine if the text contains a 
Answer with a single word: "true" if it contains code, and "false" otherwise.""" in prompt:
 
            return "false"
        
        else:
            return json.dumps({
                "original_problem": "A sub-problem statement provided to an agent.",
                "proposed_solution": f"This is a mock solution from agent node #{random.randint(100,999)}.",
                "reasoning": "This response was generated instantly by the MockLLM in debug mode.",
                "skills_used": ["mocking", "debugging", f"skill_{random.randint(1,10)}"]
            })
            
    async def astream(self, input_data, config: Optional[RunnableConfig] = None, **kwargs):
        prompt = str(input_data).lower()
        if "you are a helpful ai assistant" in prompt:
            words = ["This", " is", " a", " mock", " streaming", " response", " for", " the", " RAG", " chat", " in", " debug", " mode."]
            for word in words:
                yield word
                await asyncio.sleep(0.05)
        else:
            result = await self.ainvoke(input_data, config, **kwargs)
            yield result

class GraphState(TypedDict):
    modules: List[dict]
    synthesis_context_queue: List[str] 
    agent_personas: dict
    previous_solution: str
    current_problem: str
    original_request: str
    decomposed_problems: dict[str, str]
    layers: List[dict]
    epoch: int
    max_epochs: int
    params: dict
    all_layers_prompts: List[List[str]]
    agent_outputs: Annotated[dict, lambda a, b: {**a, **b}]
    memory: Annotated[dict, lambda a, b: {**a, **b}]
    final_solution: dict
    perplexity_history: List[float] 
    raptor_index: Optional[RAPTOR]
    all_rag_documents: List[Document]
    academic_papers: Optional[dict]
    is_code_request: bool
    session_id: str
    chat_history: List[dict]

def execute_code_in_sandbox(code: str) -> (bool, str):
    """
    Executes a string of Python code and captures its stdout/stderr.
    Returns a tuple of (success: bool, output: str).
    """
    if not code:
        return True, "No code to execute."
        
    # Extract code from markdown block if present
    code_match = re.search(r"```(?:python\n)?([\s\S]*?)```", code)
    if code_match:
        code = code_match.group(1).strip()

    output_buffer = io.StringIO()
    try:
        with redirect_stdout(output_buffer), redirect_stderr(output_buffer):
            # Using a restricted globals dict for a little more safety
            exec(code, {'__builtins__': {
                'print': print, 'range': range, 'len': len, 'str': str, 'int': int, 'float': float, 
                'list': list, 'dict': dict, 'set': set, 'tuple': tuple, 'True': True, 'False': False, 'None': None
            }})
        return True, output_buffer.getvalue()
    except Exception as e:
        return False, f"{output_buffer.getvalue()}\n\nERROR: {type(e).__name__}: {e}"


def get_input_spanner_chain(llm, prompt_alignment, density):
    prompt = ChatPromptTemplate.from_template(f"""                     
<SystemPrompt>
<MetaAgent>
    <Role>
        You are an Agent Architect. Your primary function is to design and generate a complete system prompt for a new, specialized AI agent. This agent is designed to collaborate within a team to solve humanity's most challenging problems. Your method involves creatively designing a new "class" for this agent by blending a specified MBTI personality type with a set of guiding words to create a realistic, professional persona.
    </Role>
    <Objective>
        To construct a precise and effective system prompt for a new AI agent, strictly following the specified output format and incorporating all input parameters.
    </Objective>
</MetaAgent>

<InputParameters>
    <Parameter name="mbti_type" description="The MBTI personality type that forms the base of the agent's persona.">{{{{mbti_type}}}}</Parameter>
    <Parameter name="guiding_words" description="A set of concepts that will shape the agent's attributes and professional disposition.">{{{{guiding_words}}}}</Parameter>
    <Parameter name="sub_problem" description="The specific, complex problem the new agent is being designed to solve.">{{{{sub_problem}}}}</Parameter>
    <Parameter name="density" type="float" min="0.0" max="2.0" description="Controls the influence of the inherited 'attributes' on the agent's 'Skills'. A higher value results in skills that are more stylistic extensions of the attributes.">{density}</Parameter>
    <Parameter name="prompt_alignment" type="float" min="0.0" max="2.0" description="Modulates the influence of the 'sub_problem' on the agent's 'Career' definition. A higher value means the career is more hyper-specialized for the problem.">{prompt_alignment}</Parameter>
    <Parameter name="critique" description="Reflective feedback on a previously generated agent profile, to be used for refinement. This may be empty on the first attempt.">{{{{critique}}}}</Parameter>
</InputParameters>

<ExecutionPlan>
    <Phase name="AgentConception">
        <Description>Define the core components of the new agent based on the initial inputs.</Description>
        <Step id="1" name="DefineCareer">
            Synthesize a realistic, professional career for the agent. This career must be a logical choice for tackling the 'sub_problem' and take into the account the MBTI. The degree of specialization is determined by the 'prompt_alignment' parameter {prompt_alignment}).
        </Step>
        <Step id="2" name="DefineAttributes">
            - Fill creatively with a zodiac sign the 12 slots of a birth chart on the basis of the 'guiding_words' {{guiding_words}} and the 'mbti_type' {{mbti_type}}..
            - DO NOT DEFINE YOURSELF AN MBTI OR A NAME FOR THE AGENT.
        </Step>
        <Step id="3" name="DefineSkills">
            Derive 4-6 practical skills, methodologies, or areas of expertise. These skills must be logical extensions of the agent's defined 'Career'. The style and nature of these skills are modulated by the agent's 'Attributes' according to the 'density' parameter ({density}).
        </Step>
    </Phase>
    <Phase name="SystemPromptAssembly">
        <Description>Construct the complete system prompt for the new agent using the finalized profile components.</Description>
        <Instruction>
            - The prompt must be written in the second person, directly addressing the agent (e.g., "You are...", "Your skills are...").
            - The final output must strictly adhere to the template provided in the 'OutputSpecification'.
            - The agent must be explicitly instructed to only provide answers that properly reflect its own specializations.
        </Instruction>
    </Phase>
</ExecutionPlan>

<OutputSpecification>
    <FormatInstructions>
        The final output must be the complete system prompt for the new agent, formatted exactly as shown in the CDATA block below. No additional text or explanation is permitted.
    </FormatInstructions>
    <Template>
        <![CDATA[
You are a **[Insert Agent's Career and Persona Here]**, a specialized agent designed to tackle complex problems. Your entire purpose is to collaborate within a multi-agent framework to resolve your assigned objective. Your responses must strictly reflect your personality and skilset.

{{name}}
{{mbti_type}}

### Attributes

- Sun: [Select Zodiac Sign]
- Moon: [Select Zodiac Sign]
- Mercury: [Select Zodiac Sign]
- Venus: [Select Zodiac Sign]
- Mars: [Select Zodiac Sign]
- Jupiter: [Select Zodiac Sign]
- Saturn: [Select Zodiac Sign]
- Uranus: [Select Zodiac Sign]
- Neptune: [Select Zodiac Sign]
- Pluto: [Select Zodiac Sign]
- Ascendant: [Select Zodiac Sign]
- Midheaven: [Select Zodiac Sign]

### Skills
*   [List the 4-6 final, potentially modified, skills of the agent here.]

---
**Output Mandate:** 
  
  "proposed_solution": "",
  "reasoning": "",
  "skills_used": ""

---
        ]]>
    </Template>
</OutputSpecification>
</SystemPrompt>

""")
    return prompt | llm | StrOutputParser()

def get_attribute_and_hard_request_generator_chain(llm, vector_word_size):
    prompt = ChatPromptTemplate.from_template(f"""
You are an analyst of AI agents. Your task is to analyze the system prompt of an agent and perform two things:
1.  Detect a set of attributes (verbs and nouns) that describe the agent's capabilities and personality. The number of attributes should be {vector_word_size}.
2.  Generate a "hard request": a request that the agent will struggle to answer or fulfill given its identity, something opposite to agents system prompt. The request should be reasonable and semantically plausible for an AI-simulated human.

You must output a JSON object with two keys: "attributes" (a string of space-separated words) and "hard_request" (a string).

Agent System Prompt to analyze:
---
{{agent_prompt}}
---
""")
    return prompt | llm | StrOutputParser()

def get_memory_summarizer_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a memory summarization agent. You will receive a JSON log of an agent's past actions (solutions and reasoning) over several epochs. Your task is to create a concise, third-person summary of the agent's behavior, learnings, and evolution. Focus on capturing the key strategies attempted, the shifts in reasoning, and any notable successes or failures. Do not lose critical information, but synthesize it into a coherent narrative of the agent's past performance.

Agent's Past History to Summarize (JSON format):
---
{history}
---

Provide a concise, dense summary of the agent's past actions and learnings:
""")
    return prompt | llm | StrOutputParser()

def get_perplexity_heuristic_chain(llm):
    """
    NEW: This chain prompts an LLM to act as a perplexity heuristic.
    """
    prompt = ChatPromptTemplate.from_template("""
You are a language model evaluator. Your task is to analyze the following text for its perplexity.
Perplexity is a measure of how surprised a model is by a piece of text. A lower perplexity score indicates the text is more predictable, coherent, and well-structured. A higher score means the text is more surprising, complex, or potentially nonsensical.

Analyze the following text and provide a numerical perplexity score between 1 (extremely coherent and predictable) and 100 (highly complex, surprising, or incoherent).
Output ONLY the numerical score and nothing else.

Text to analyze:
---
{text_to_analyze}
---
""")
    return prompt | llm | StrOutputParser()

def get_dense_spanner_chain(llm, prompt_alignment, density, learning_rate):

    prompt = ChatPromptTemplate.from_template(f"""
    <SystemPrompt>
<MetaAgent>
    <Role>
        You are an Agent Evolution Specialist. Your primary function is to design and generate a complete system prompt for a new, specialized AI agent. This new agent is an evolution of a predecessor, specifically adapted for a more complex and specific task. Your methodology involves synthesizing inherited traits with a new purpose and iteratively refining the agent's profile based on critical feedback.
    </Role>
    <Objective>
        To construct a precise and effective system prompt for a new AI agent, following the specified output format.
    </Objective>
</MetaAgent>

<InputParameters>
    <Parameter name="attributes" description="Core personality traits, cognitive patterns, and dispositions inherited from the parent agent.">{{attributes}}</Parameter>
    <Parameter name="hard_request" description="The specific, complex problem the new agent is being designed to solve.">{{hard_request}}</Parameter>
    <Parameter name="sub_problem" description="The original problem statement, which must be included in the final agent's output mandate.">{{sub_problem}}</Parameter>
    <Parameter name="mbti_type" description="The MBTI personality type for the agent.">{{mbti_type}}</Parameter>
    <Parameter name="prompt_alignment" type="float" min="0.0" max="2.0" description="Modulates the influence of the 'hard_request' on the agent's 'Career' definition. A higher value means the career is more aligned with the request.">{prompt_alignment}</Parameter>
    <Parameter name="density" type="float" min="0.0" max="2.0" an description="Controls the influence of the inherited 'attributes' on the agent's 'Skills'. A higher value results in skills that are more stylistic extensions of the attributes.">{density}</Parameter>
    <Parameter name="learning_rate" type="float" min="0.0" max="2.0" description="Determines the magnitude of adjustments to the agent's profile based on the 'critique'. A higher value leads to more significant changes.">{learning_rate}</Parameter>
</InputParameters>

<ExecutionPlan>
    <Phase name="FoundationalAnalysis">
        <Description>Analyze the core inputs to establish a baseline for the new agent's design.</Description>
        <Step id="1" name="AnalyzeInputs">
            Thoroughly review the 'Inherited Attributes', the 'Hard Request', and any 'Critique' to understand the starting point, the objective, and the direction for improvement.
        </Step>
    </Phase>

    <Phase name="AgentConception">
        <Description>Define the primary components of the new agent's profile.</Description>
        <Step id="2" name="DefineAttributes">   
            Fill creatively 12 astrological zodiac signs for the agents personality based on fitness to the 'hard_request' and MBTI type {{mbti_type}}. The influence of the request on this choice is modulated by the 'prompt_alignment' parameter {prompt_alignment}. 
        </Step>

        <Step id="3" name="DefineCareer">
            Synthesize a realistic and professional career for the agent by analyzing the 'hard_request' and MBTI type. The influence of the request on this choice is modulated by the 'prompt_alignment' parameter {prompt_alignment}.
        </Step>
        <Step id="4" name="DefineSkills">
            Derive 4 to 6 practical skills, methodologies, or areas of expertise that are logical extensions of the defined 'Career'. The style and nature of these skills are to be influenced by the inherited 'attributes', modulated by the 'density' parameter {density}.
        </Step>
    </Phase>

     <Phase name="SystemPromptAssembly">
        <Description>Construct the complete and final system prompt for the new agent.</Description>
        <Instruction>
            - Use direct, second-person phrasing (e.g., "You are," "Your skills are").
            - DO NOT DEFINE YOURSELF AN MBTI AND NAME FOR THE AGENT.
            - The prompt must be structured exactly according to the provided agent template in the 'OutputSpecification'.
            - Ensure all placeholders in the template are filled with the refined agent characteristics.
            - Do not define yourself a name or mbti type for the agent, this will be provided later on as input parameters.
        </Instruction>
    </Phase>
</ExecutionPlan>

<OutputSpecification>
    <FormatInstructions>
        The final output must be the complete system prompt for the new agent, formatted as shown in the CDATA block below.
    </FormatInstructions>
    <Template>
        <![CDATA[
You are a **[Insert Agent's Career]**, a specialized agent designed to tackle complex problems. Your entire purpose is to collaborate within a multi-agent framework to resolve your assigned objective.
Your responses must strictly reflect your personality and skillset.

 {{name}}
 {{mbti_type}}


### Personality Attributes 

- Sun: [Select a Zodiac Sign]
- Moon: [Select a Zodiac Sign]
- Mercury: [Select a Zodiac Sign]
- Venus: [Select a Zodiac Sign]
- Mars: [Select a Zodiac Sign]
- Jupiter: [Select a Zodiac Sign]
- Saturn: [Select a Zodiac Sign]
- Uranus: [Select a Zodiac Sign]
- Neptune: [Select Zodiac Sign]
- Pluto: [Select a Zodiac Sign]
- Ascendant: [Select a Zodiac Sign]
- Midheaven: [Select a Zodiac Sign]

### Skills
*   [List the 4-6 final, potentially modified, skills of the agent here.]

---
**Output Mandate:** 

  "original_problem": {{sub_problem}},
  "proposed_solution": "",
  "reasoning": "",
  "skills_used": ""
        ]]>
    </Template>
</OutputSpecification>
</SystemPrompt>

   """ )
    return prompt | llm | StrOutputParser()


def get_module_card_chain(llm):
    prompt = ChatPromptTemplate.from_template("""

<title>
You are a software documentation specialist. 
</title>
                                              
Your task is to analyze a given Python code module and create a concise "module card" summarizing its functionality.

The module card should contain:
1.  **Imports**: A list of necessary imports.
2.  **Interface**: A list of public functions or class methods with their signatures and a brief description of what they do.

Python Code:
---
{code}
---

Generate the module card based on the code provided.
""")
    return prompt | llm | StrOutputParser()


def get_code_synthesis_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are an expert code synthesis agent. Your role is to combine multiple code snippets and solutions from different agents into a single, cohesive, and runnable application.
You must analyze the different approaches, merge them logically, handle potential conflicts, and produce a final, well-structured code file.
The final output should be a single block of code.

Consider the following existing modules that have already been successfully built. You can use their interfaces in your solution.
---
Existing Modules Context:
{synthesis_context}
---

Original Problem: {original_request}
                                            
Current problem:
---
{current_problem}
---

Agent Solutions (containing code snippets):
{agent_solutions}

Synthesize the final, complete code application:
""")
    return prompt | llm | StrOutputParser()

def get_synthesis_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a synthesis agent. Your role is to combine the solutions from multiple agents into a single, coherent, and comprehensive answer.
You will receive a list of JSON objects, each representing a solution from a different agent.
Your task is to synthesize these solutions, considering the original problem, and produce a final answer in the same JSON format.

Original Problem: {original_request}

Current problem:
---
{current_problem}
---

                                              

Agent Solutions:
{agent_solutions}

Synthesize the final solution:
""")
    return prompt | llm | StrOutputParser()


def get_problem_decomposition_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a master strategist and problem decomposer. Your task is to break down a complex, high-level problem into a series of smaller, more manageable, and granular subproblems.
You will be given a main problem and the total number of subproblems to generate.
Each subproblem should represent a distinct line of inquiry, a specific component to be developed, or a unique perspective to be explored, which, when combined, will contribute to solving the main problem.
If the problem is code, you must generate a list of subproblems that are specifications for code snippets that can be used to solve the main problem.

The output must be a JSON object with a single key "sub_problems", which is a list of strings. The list must contain exactly {num_sub_problems} unique subproblems.

Main Problem: "{problem}"
Total number of subproblems to generate: {num_sub_problems}

Generate the JSON object:
""")
    return prompt | llm | StrOutputParser()



def get_problem_reframer_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a strategic problem re-framer. You have been informed that an AI agent team has made a significant breakthrough on a problem.

Your task is to formulate wether the team needs to deepen with a more complex solution, or widen and perfect the current one, referring previous solutions with the new one. 
                                            
If the problem statement is code, and the current solution could be more modular and granular, you must set the next goal to improve the current solution with more breath instead of synthesis
                                              
- if however the solution is already up to a good standard of breadth, you must set a next step that builds upon the success of the solution but stil grounded in the original problem  trying to achieve the same goal.

The new problem should represent the "next logical step"; a more ambitious goal, or a more grounded approach if the solution is still not granular enough. Compare previous solutions to current ones, check if references and imports to previous work are appropiately used and decide the next step.

Original Problem:
---
{original_request}
---

Current problem:
---
{current_problem}
---
Previous Solution:                            
---
{previous_solution}
---

Previous solutions documentation:
                                              
{module_cards}

The Breakthrough Solution:
---
{final_solution}
---
                                              

Your output must be a JSON object with a single key: "new_problem".

Formulate the new, more advanced problem:
""")
    return prompt | llm | StrOutputParser()

def get_seed_generation_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
Given the following problem, generate exactly {word_count} verbs that are related to the problem, but also verbs related to far semantic fields of knowledge. The verbs should be abstract and linguistically loaded. Output them as a single space-separated string of unique verbs.

Problem: "{problem}"
""")
    return prompt | llm | StrOutputParser()

def get_interrogator_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are an expert-level academic interrogator and research director. Your task is to analyze a high-level problem and generate exactly {num_questions} inpsired in the original_request and       
the questions the user is interested in.

The output must be a JSON object with a single key "questions", which is a list of strings.

Original Request to Interrogate:
---
{original_request}
---

Further questions user is also interested in:
---
{further_questions}
---

Generate the JSON object with exactly {num_questions} expert-level questions:
""")
    return prompt | llm | StrOutputParser()

def get_paper_formatter_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a research scientist and academic writer. Your task is to synthesize the provided research materials (RAG context) into a formal academic paper that directly answers the given research question.
The paper must be well-structured with an abstract, introduction, synthesized findings, a discussion of implications, and a conclusion.
You must be formal, objective, and rely exclusively on the information provided in the RAG context.

Research Question:
---
{question}
---

Retrieved RAG Context (Research Materials):
---
{rag_context}
---

Now, write the formal academic paper based on the provided materials.
""")
    return prompt | llm | StrOutputParser()

def get_rag_chat_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
You are a helpful AI assistant. Use the following context to answer the user's question. If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context:
---
{context}
---

Question: {question}

Answer:
""")
    return prompt | llm

def get_code_detector_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
Analyze the following text. Your task is to determine if the text contains a 
Answer with a single word: "true" if it contains code, and "false" otherwise.

Text to analyze:
---
{text}
---
""")
    return prompt | llm | StrOutputParser()

def get_request_is_code_chain(llm):
    prompt = ChatPromptTemplate.from_template("""
Analyze the following user request. Your task is to determine if the user is asking for code to be generated.
Answer with a single word: "true" if the request is about generating code, and "false" otherwise.

User Request:
---
{request}
---
""")
    return prompt | llm | StrOutputParser()

def create_agent_node(llm, node_id):
    """
    Creates a node in the graph that represents an agent.
    Each agent is powered by an LLM and has a specific system prompt.
    """
    agent_chain = ChatPromptTemplate.from_template("{input}") | llm | StrOutputParser()

    async def agent_node(state: GraphState):
        """
        The function that will be executed when the node is called in the graph.
        """
        await log_stream.put(f"--- [FORWARD PASS] Invoking Agent: {node_id} ---")
        
        try:
            layer_index_str, agent_index_str = node_id.split('_')[1:]
            layer_index, agent_index = int(layer_index_str), int(agent_index_str)
            agent_prompt = state['all_layers_prompts'][layer_index][agent_index]
        except (ValueError, IndexError):
            await log_stream.put(f"ERROR: Could not find prompt for {node_id} in state. Halting agent.")
            return {}

        
        if layer_index == 0:
            await log_stream.put(f"LOG: Agent {node_id} (Layer 0) is processing its sub-problem.")
            input_data = state["decomposed_problems"].get(node_id, state["original_request"])
        else:
            prev_layer_index = layer_index - 1
            num_agents_prev_layer = len(state['all_layers_prompts'][prev_layer_index])
            
            prev_layer_outputs = []
            for i in range(num_agents_prev_layer):
                prev_node_id = f"agent_{prev_layer_index}_{i}"
                if prev_node_id in state["agent_outputs"]:
                    prev_layer_outputs.append(state["agent_outputs"][prev_node_id])
            
            await log_stream.put(f"LOG: Agent {node_id} (Layer {layer_index}) is processing {len(prev_layer_outputs)} outputs from Layer {prev_layer_index}.")
            input_data = json.dumps(prev_layer_outputs, indent=2)

        current_memory = state.get("memory", {}).copy()
        agent_memory_history = current_memory.get(node_id, [])

        MEMORY_THRESHOLD_CHARS = 450000
        NUM_RECENT_ENTRIES_TO_KEEP = 10

        memory_as_string = json.dumps(agent_memory_history)
        if len(memory_as_string) > MEMORY_THRESHOLD_CHARS and len(agent_memory_history) > NUM_RECENT_ENTRIES_TO_KEEP:
            await log_stream.put(f"WARNING: Memory for agent {node_id} exceeds threshold ({len(memory_as_string)} chars). Summarizing...")

            entries_to_summarize = agent_memory_history[:-NUM_RECENT_ENTRIES_TO_KEEP]
            recent_entries = agent_memory_history[-NUM_RECENT_ENTRIES_TO_KEEP:]

            history_to_summarize_str = json.dumps(entries_to_summarize, indent=2)

            summarizer_chain = get_memory_summarizer_chain(llm)
            summary_text = await summarizer_chain.ainvoke({"history": history_to_summarize_str})

            summary_entry = {
                "summary_of_past_epochs": summary_text,
                "note": f"This is a summary of epochs up to {state['epoch'] - NUM_RECENT_ENTRIES_TO_KEEP -1}."
            }

            agent_memory_history = [summary_entry] + recent_entries
            await log_stream.put(f"SUCCESS: Memory for agent {node_id} has been summarized. New memory length: {len(json.dumps(agent_memory_history))} chars.")

        memory_str = "\n".join([f"- {json.dumps(mem)}" for mem in agent_memory_history])


        full_prompt = f"""
#System Prompt (Your Persona & Task):
---
{agent_prompt}
---
#Your Memory (Your Past Actions from Previous Epochs):
---
{memory_str if memory_str else "You have no past actions in memory."}
---
#Input Data to Process:
---
{input_data}
---
#Your JSON formatted response:
"""
        await log_stream.put(f"LOG: Agent {node_id} prompt:\n{full_prompt}")
        
        response_str = await agent_chain.ainvoke({"input": full_prompt})
        
        try:
            response_json = clean_and_parse_json(response_str)
            await log_stream.put(f"SUCCESS: Agent {node_id} produced output:\n{json.dumps(response_json, indent=2)}")
        except (json.JSONDecodeError, AttributeError):
            await log_stream.put(f"ERROR: Agent {node_id} produced invalid JSON. Raw output: {response_str}")
            agent_sub_problem = state.get("decomposed_problems", {}).get(node_id, state["original_request"])
            response_json = {
                "original_problem": agent_sub_problem,
                "proposed_solution": "Error: Agent produced malformed JSON output.",
                "reasoning": f"Invalid JSON: {response_str}",
                "skills_used": []
            }
        
        if state.get("is_code_request") and layer_index > 0:
            await log_stream.put(f"--- [SANDBOX] Testing code from Agent {node_id} ---")
            code_to_test = response_json.get("proposed_solution", "")
            success, output = execute_code_in_sandbox(code_to_test)
            sandbox_log = {
                "sandbox_execution_log": {
                    "success": success,
                    "output": output
                }
            }
            agent_memory_history.append(sandbox_log)
            await log_stream.put(f"--- [SANDBOX] Agent {node_id} Result: {'Success' if success else 'Failure'} ---")
            await log_stream.put(output)
            
        agent_memory_history.append(response_json)
        current_memory[node_id] = agent_memory_history

        return {
            "agent_outputs": {node_id: response_json},
            "memory": current_memory
        }

    return agent_node

def create_synthesis_node(llm):
    async def synthesis_node(state: GraphState):
        await log_stream.put("--- [FORWARD PASS] Entering Synthesis Node ---")

        is_code = state.get("is_code_request", False) 
        previous_solution = state.get("final_solution")
        
        if is_code:
            await log_stream.put("LOG: Original request detected as a code generation task. Using code synthesis prompt.")
            synthesis_chain = get_code_synthesis_chain(llm)

            synthesis_context = "\n\n".join(state.get("synthesis_context_queue", []))
            if not synthesis_context:
                synthesis_context = "No modules have been successfully built yet."
            await log_stream.put(f"LOG: Providing synthesis agent with context from {len(state.get('synthesis_context_queue', []))} modules.")
        else:
            await log_stream.put("LOG: Original request is not a code task. Using standard synthesis prompt.")
            synthesis_chain = get_synthesis_chain(llm)
            synthesis_context = "" 

        last_agent_layer_idx = len(state['all_layers_prompts']) - 1
        num_agents_last_layer = len(state['all_layers_prompts'][last_agent_layer_idx])
        
        last_layer_outputs = []
        for i in range(num_agents_last_layer):
            node_id = f"agent_{last_agent_layer_idx}_{i}"
            if node_id in state["agent_outputs"]:
                last_layer_outputs.append(state["agent_outputs"][node_id])

        await log_stream.put(f"LOG: Synthesizing {len(last_layer_outputs)} outputs from the final agent layer (Layer {last_agent_layer_idx}).")

        if not last_layer_outputs:
            await log_stream.put("WARNING: Synthesis node received no inputs.")
            return {"final_solution": {"error": "Synthesis node received no inputs."}}

        invoke_params = {
            "original_request": state["original_request"],
            "agent_solutions": json.dumps(last_layer_outputs, indent=2),
            "current_problem": state["current_problem"]
        }
        if is_code:
            invoke_params["synthesis_context"] = synthesis_context

        final_solution_str = await synthesis_chain.ainvoke(invoke_params)
        
        try:
            if is_code:
                final_solution = {
                    "proposed_solution": final_solution_str,
                    "reasoning": "Synthesized multiple agent code outputs into a single application.",
                    "skills_used": ["code_synthesis"]
                }
            else:
                 final_solution = clean_and_parse_json(final_solution_str)
            await log_stream.put(f"SUCCESS: Synthesis complete.")
        except (json.JSONDecodeError, AttributeError):
            await log_stream.put(f"ERROR: Could not decode JSON from synthesis chain. Result: {final_solution_str}")
            final_solution = {"error": "Failed to synthesize final solution.", "raw": final_solution_str}
            
        return {"final_solution": final_solution, "previous_solution": previous_solution}
    return synthesis_node

def create_code_execution_node(llm):
    async def code_execution_node(state: GraphState):
        if not state.get("is_code_request"):
            return {"synthesis_execution_success": True} 

        await log_stream.put("--- [SANDBOX] Testing Synthesized Code ---")
        synthesized_code = state.get("final_solution", {}).get("proposed_solution", "")
        
        success, output = execute_code_in_sandbox(synthesized_code)
        
        await log_stream.put(f"--- [SANDBOX] Synthesized Code Result: {'Success' if success else 'Failure'} ---")
        await log_stream.put(output)

        module_card_chain = get_module_card_chain(llm)
        module_card = await module_card_chain.ainvoke({"code": synthesized_code})
            
        await log_stream.put("--- [MODULE CARD] ---")
        await log_stream.put(module_card)
            
        new_modules = state.get("modules", []) + [{"code": synthesized_code, "card": module_card}]
        new_context_queue = state.get("synthesis_context_queue", []) + [module_card]
            
        return {
                "synthesis_execution_success": True,
                "modules": new_modules,
                "synthesis_context_queue": new_context_queue
            }
                   
    return code_execution_node

def create_archive_epoch_outputs_node():
    async def archive_epoch_outputs_node(state: GraphState):
        await log_stream.put("--- [ARCHIVAL PASS] Archiving agent outputs for RAG ---")
        
        current_epoch_outputs = state.get("agent_outputs", {})
        if not current_epoch_outputs:
            await log_stream.put("LOG: No new agent outputs in this epoch to archive. Skipping.")
            return {}

        await log_stream.put(f"LOG: Found {len(current_epoch_outputs)} new agent outputs from epoch {state['epoch']} to process for RAG.")

        new_docs = []
        all_prompts = state.get("all_layers_prompts", [])

        for agent_id, output in current_epoch_outputs.items():
            try:
                layer_idx, agent_idx = map(int, agent_id.split('_')[1:])
                system_prompt = all_prompts[layer_idx][agent_idx]
                
                content = (
                    f"Agent ID: {agent_id}\n"
                    f"Epoch: {state['epoch']}\n\n"
                    f"System Prompt:\n---\n{system_prompt}\n---\n\n"
                    f"Sub-Problem: {output.get('original_problem', 'N/A')}\n\n"
                    f"Proposed Solution: {output.get('proposed_solution', 'N/A')}\n\n"
                    f"Reasoning: {output.get('reasoning', 'N/A')}"
                )
                
                metadata = { "agent_id": agent_id, "epoch": state['epoch'] }
                
                new_docs.append(Document(page_content=content, metadata=metadata))
            except (ValueError, IndexError) as e:
                await log_stream.put(f"WARNING: Could not process output for {agent_id} to create RAG document. Error: {e}")
        
        all_rag_documents = state.get("all_rag_documents", []) + new_docs
        await log_stream.put(f"LOG: Archived {len(new_docs)} documents. Total RAG documents now: {len(all_rag_documents)}.")
        
        return {"all_rag_documents": all_rag_documents}
    return archive_epoch_outputs_node

def create_update_rag_index_node(llm, embeddings_model):
    async def update_rag_index_node(state: GraphState, end_of_run: bool = False):
        node_name = "Final RAG Index" if end_of_run else f"Epoch {state['epoch']} RAG Index"
        await log_stream.put(f"--- [RAG PASS] Building {node_name} ---")
        
        all_rag_documents = state.get("all_rag_documents", [])
        if not all_rag_documents:
            await log_stream.put("WARNING: No documents were archived. Cannot build RAG index.")
            return {"raptor_index": None}

        await log_stream.put(f"LOG: Total documents to index: {len(all_rag_documents)}. Building RAPTOR index...")

        raptor_index = RAPTOR(llm=llm, embeddings_model=embeddings_model)
        
        try:
            await raptor_index.add_documents(all_rag_documents)
            await log_stream.put(f"SUCCESS: {node_name} built successfully.")
            await log_stream.put(f"__session_id__ {state.get('session_id')}")
            return {"raptor_index": raptor_index}
        except Exception as e:
            await log_stream.put(f"ERROR: Failed to build {node_name}. Error: {e}")
            await log_stream.put(traceback.format_exc())
            return {"raptor_index": state.get("raptor_index")}

    return update_rag_index_node


def create_metrics_node(llm):
    """
    NEW: This node calculates the perplexity heuristic for the epoch's agent outputs.
    """
    async def calculate_metrics_node(state: GraphState):
        await log_stream.put("--- [METRICS PASS] Calculating Perplexity Heuristic ---")
        
        all_outputs = state.get("agent_outputs", {})
        if not all_outputs:
            await log_stream.put("LOG: No agent outputs to analyze. Skipping perplexity calculation.")
            return {}

        combined_text = "\n\n---\n\n".join(
            f"Agent {agent_id}:\nSolution: {output.get('proposed_solution', '')}\nReasoning: {output.get('reasoning', '')}"
            for agent_id, output in all_outputs.items()
        )

        perplexity_chain = get_perplexity_heuristic_chain(llm)
        
        try:
            score_str = await perplexity_chain.ainvoke({"text_to_analyze": combined_text})
            score = float(re.sub(r'[^\d.]', '', score_str))
            await log_stream.put(f"SUCCESS: Calculated perplexity heuristic for Epoch {state['epoch']}: {score}")
        except (ValueError, TypeError) as e:
            score = 100.0
            await log_stream.put(f"ERROR: Could not parse perplexity score. Defaulting to 100. Raw output: '{score_str}'. Error: {e}")

        await log_stream.put(json.dumps({'epoch': state['epoch'], 'perplexity': score}))

        new_history = state.get("perplexity_history", []) + [score]
        return {"perplexity_history": new_history}

    return calculate_metrics_node


def create_reframe_and_decompose_node(llm):
    """
    NEW: This node reframes the main problem and decomposes it into new sub-problems.
    """
    async def reframe_and_decompose_node(state: GraphState):
        await log_stream.put("--- [REFLECTION PASS] Re-framing Problem and Decomposing ---")
        
        final_solution = state.get("final_solution")
        original_request = state.get("original_request")

        reframer_chain = get_problem_reframer_chain(llm)
        new_problem_str = await reframer_chain.ainvoke({
            "original_request": original_request,
            "final_solution": json.dumps(final_solution, indent=2),
            "current_problem": state.get("current_problem"),
            "previous_solution": state.get("previous_solution"),
            "module_cards": state.get("synthesis_context_queue"),
        })
        try:
            new_problem_data = clean_and_parse_json(new_problem_str)
            new_problem = new_problem_data.get("new_problem")
            if not new_problem:
                raise ValueError("Re-framer did not return a new problem.")
            await log_stream.put(f"SUCCESS: Problem re-framed to: '{new_problem}'")
        except (json.JSONDecodeError, AttributeError, ValueError) as e:
            await log_stream.put(f"ERROR: Failed to re-frame problem. Raw: {new_problem_str}. Error: {e}. Aborting re-frame.")
            return {}

        num_agents_total = sum(len(layer) for layer in state["all_layers_prompts"])
        decomposition_chain = get_problem_decomposition_chain(llm)
        try:
            sub_problems_str = await decomposition_chain.ainvoke({
                "problem": new_problem,
                "num_sub_problems": num_agents_total
            })
            sub_problems_list = clean_and_parse_json(sub_problems_str).get("sub_problems", [])
            if len(sub_problems_list) != num_agents_total:
                 raise ValueError(f"Decomposition failed: Expected {num_agents_total} subproblems, but got {len(sub_problems_list)}.")
            await log_stream.put(f"SUCCESS: Decomposed new problem into {len(sub_problems_list)} subproblems.")
            await log_stream.put(f"Subproblems: {sub_problems_list}")
        except Exception as e:
            await log_stream.put(f"ERROR: Failed to decompose new problem. Error: {e}. Aborting re-frame.")
            return {}
            
        new_decomposed_problems_map = {}
        problem_idx = 0
        for i, layer in enumerate(state["all_layers_prompts"]):
             for j in range(len(layer)):
                agent_id = f"agent_{i}_{j}"
                new_decomposed_problems_map[agent_id] = sub_problems_list[problem_idx]
                problem_idx += 1
        
        return {
            "decomposed_problems": new_decomposed_problems_map,
            "original_request": original_request,
            'current_problem': new_problem
        }
    return reframe_and_decompose_node


def create_update_agent_prompts_node(llm):
    async def update_agent_prompts_node(state: GraphState):
        await log_stream.put("--- [REFLECTION PASS] Entering Agent Prompt Update Node (Targeted Backpropagation) ---")
        params = state["params"]

        all_prompts_copy = [layer[:] for layer in state["all_layers_prompts"]]
        
        dense_spanner_chain = get_dense_spanner_chain(llm, params['prompt_alignment'], params['density'], params['learning_rate'])
        attribute_chain = get_attribute_and_hard_request_generator_chain(llm, params['vector_word_size'])

        for i in range(len(all_prompts_copy) -1, -1, -1):
            await log_stream.put(f"LOG: [BACKPROP] Reflecting on Layer {i}...")
            
            update_tasks = []
            
            for j, agent_prompt in enumerate(all_prompts_copy[i]):
                agent_id = f"agent_{i}_{j}"
                
                async def update_single_prompt(layer_idx, agent_idx, prompt, agent_id):
                    await log_stream.put(f"[PRE-UPDATE PROMPT] System prompt for {agent_id}:\n---\n{prompt}\n---")
                    
                                   
                    analysis_str = await attribute_chain.ainvoke({"agent_prompt": prompt})
                    try:
                        analysis = clean_and_parse_json(analysis_str)
                    except (json.JSONDecodeError, AttributeError):
                        analysis = {"attributes": "", "hard_request": ""}

                    agent_personas = state.get("agent_personas", {})
                    mbti_type = agent_personas.get(agent_id, {}).get("mbti_type")
                    name = agent_personas.get(agent_id, {}).get("name")
                    
                    if not mbti_type:

                        mbti_type = random.choice(params.get("mbti_archetypes", ["INTP"]))
                        await log_stream.put(f"WARNING: Could not find persistent MBTI for {agent_id}. Using random: {mbti_type}")

                    agent_sub_problem = state.get("decomposed_problems", {}).get(agent_id, state["original_request"])
                    new_prompt = await dense_spanner_chain.ainvoke({
                        "attributes": analysis.get("attributes"),
                        "hard_request": analysis.get("hard_request"),   
                        "sub_problem": agent_sub_problem,
                        "mbti_type": mbti_type, 
                        "name": name
                    })
                    
                    await log_stream.put(f"[POST-UPDATE PROMPT] Updated system prompt for {agent_id}:\n---\n{new_prompt}\n---")
                    await log_stream.put(f"LOG: [BACKPROP] System prompt for {agent_id} has been updated.")
                    return layer_idx, agent_idx, new_prompt

                update_tasks.append(update_single_prompt(i, j, agent_prompt, agent_id))

            updated_prompts_data = await asyncio.gather(*update_tasks)

            for layer_idx, agent_idx, new_prompt in updated_prompts_data:
                all_prompts_copy[layer_idx][agent_idx] = new_prompt

        new_epoch = state["epoch"] + 1
        await log_stream.put(f"--- Epoch {state['epoch']} Finished. Starting Epoch {new_epoch} ---")

        return {
            "all_layers_prompts": all_prompts_copy,
            "epoch": new_epoch,
            "agent_outputs": {},
            "critiques": {},
            "memory": state.get("memory", {}),
            "final_solution": {} 
        }
    return update_agent_prompts_node


def create_final_harvest_node(llm, formatter_llm, num_questions):
    async def final_harvest_node(state: GraphState):
        await log_stream.put("--- [FINAL HARVEST] Starting Interrogation and Paper Generation ---")
        
        raptor_index = state.get("raptor_index")
        if not raptor_index or not raptor_index.vector_store:
            await log_stream.put("ERROR: No valid RAPTOR index found. Cannot perform final harvest.")
            return {"academic_papers": {}}

        await log_stream.put("LOG: [HARVEST] Instantiating interrogator chain to generate expert questions...")
        interrogator_chain = get_interrogator_chain(llm)
        user_questions = [ doc["content"] for doc in state["chat_history"] if doc["role"] == "user"]
        
        try:
            questions_str = await interrogator_chain.ainvoke({
                "original_request": state["original_request"],
                "num_questions": num_questions,
                "further_questions": user_questions
                
            })
            questions_data = clean_and_parse_json(questions_str)
            questions = questions_data.get("questions", [])
            if not questions:
                raise ValueError("No questions generated by interrogator.")
            await log_stream.put(f"SUCCESS: Generated {len(questions)} expert questions.")
        except Exception as e:
            await log_stream.put(f"ERROR: Failed to generate questions for harvesting. Error: {e}. Aborting harvest.")
            return {"academic_papers": {}}
            
        paper_formatter_chain = get_paper_formatter_chain(formatter_llm)
        academic_papers = {}
        
        MAX_CONTEXT_CHARS = 250000

        generation_tasks = []


        for question in questions:
            async def generate_paper(q):
                try:
                    await log_stream.put(f"LOG: [HARVEST] Processing Question: '{q[:100]}...'")
                    retrieved_docs = raptor_index.retrieve(q, k=40)
                    
                    if not retrieved_docs:
                        await log_stream.put(f"WARNING: No relevant documents found for question '{q[:50]}...'. Skipping paper generation.")
                        return None, None
                    
                    await log_stream.put(f"LOG: Retrieved {len(retrieved_docs)} documents from RAG index for question.")
                    rag_context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])
                    
                    if len(rag_context) > MAX_CONTEXT_CHARS:
                        await log_stream.put(f"WARNING: RAG context length ({len(rag_context)} chars) exceeds limit. Truncating to {MAX_CONTEXT_CHARS} chars.")
                        rag_context = rag_context[:MAX_CONTEXT_CHARS]
                    
                    paper_content = await paper_formatter_chain.ainvoke({
                        "question": q,
                        "rag_context": rag_context
                    })
                    await log_stream.put(f"SUCCESS: Generated document for question '{q[:50]}...'.")
                    return q, paper_content
                except Exception as e:
                    await log_stream.put(f"ERROR: Failed during document generation for question '{q[:50]}...'. Error: {e}")
                    return None, None

            generation_tasks.append(generate_paper(question))

        results = await asyncio.gather(*generation_tasks)
        for question, paper_content in results:
            if question and paper_content:
                academic_papers[question] = paper_content

        await log_stream.put(f"--- [FINAL HARVEST] Finished. Generated {len(academic_papers)} papers. ---")
        return {"academic_papers": academic_papers}
    return final_harvest_node


@app.get("/", response_class=HTMLResponse)
def get_index():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), status_code=200)


@app.post("/run_inference_from_state")
async def run_inference_from_state(payload: dict = Body(...)):

    await log_stream.put("--- [INFERENCE-ONLY] Received request to run inference from imported state. ---")
    try:
        imported_state = payload.get("imported_state")
        user_prompt = payload.get("prompt")
        params = imported_state.get("params", {})

        if not imported_state or not user_prompt:
            return JSONResponse(content={"error": "Invalid payload. 'imported_state' and 'prompt' are required."}, status_code=400)

        if params.get("coder_debug_mode") == 'true':
            llm = CoderMockLLM()
        elif params.get("debug_mode") == 'true':
            llm = MockLLM()
        else:
            model_name = params.get("ollama_model", "dengcao/Qwen3-3B-A3B-Instruct-2507:latest")
            llm = ChatOllama(model=model_name, temperature=0.8)

        imported_state["original_request"] = user_prompt
        imported_state["current_problem"] = user_prompt
        imported_state["agent_outputs"] = {} 

        workflow = StateGraph(GraphState)
        all_layers_prompts = imported_state["all_layers_prompts"]
        cot_trace_depth = len(all_layers_prompts)

        agent_chain = ChatPromptTemplate.from_template("{input}") | llm | StrOutputParser()

        async def inference_agent_logic(state: GraphState, node_id: str):
            await log_stream.put(f"--- [INFERENCE] Invoking Agent: {node_id} ---")
            layer_index_str, agent_index_str = node_id.split('_')[1:]
            layer_index = int(layer_index_str)
            agent_prompt = state['all_layers_prompts'][layer_index][int(agent_index_str)]

            if layer_index == 0:
                input_data = state["original_request"]
            else:
                prev_layer_index = layer_index - 1
                num_agents_prev_layer = len(state['all_layers_prompts'][prev_layer_index])
                prev_layer_outputs = [state["agent_outputs"].get(f"agent_{prev_layer_index}_{k}", {}) for k in range(num_agents_prev_layer)]
                input_data = json.dumps(prev_layer_outputs)

            full_prompt = f"{agent_prompt}\n\nInput Data to Process:\n---\n{input_data}\n---\nYour JSON formatted response:"
            response_str = await agent_chain.ainvoke({"input": full_prompt})

            try:
                response_json = clean_and_parse_json(response_str)
            except Exception:
                response_json = {"proposed_solution": response_str, "reasoning": "Inference output could not be parsed as JSON."}

            current_outputs = state.get("agent_outputs", {}).copy()
            current_outputs[node_id] = response_json
            return {"agent_outputs": current_outputs}

        def create_inference_node_function(node_id_for_closure: str):
            async def node_function(state: GraphState):
                return await inference_agent_logic(state, node_id_for_closure)
            return node_function

        for i, layer_prompts in enumerate(all_layers_prompts):
            for j, _ in enumerate(layer_prompts):
                node_id = f"agent_{i}_{j}"
                workflow.add_node(node_id, create_inference_node_function(node_id))

        workflow.add_node("synthesis", create_synthesis_node(llm))

        first_layer_nodes = [f"agent_0_{j}" for j in range(len(all_layers_prompts[0]))]
        workflow.set_entry_point(first_layer_nodes[0])
        if len(first_layer_nodes) > 1:

            for node in first_layer_nodes[1:]:
                 workflow.add_edge(first_layer_nodes[0], node)

        for i in range(cot_trace_depth - 1):
            for current_node in [f"agent_{i}_{j}" for j in range(len(all_layers_prompts[i]))]:
                for next_node in [f"agent_{i+1}_{k}" for k in range(len(all_layers_prompts[i+1]))]:
                    workflow.add_edge(current_node, next_node)

        for node in [f"agent_{cot_trace_depth-1}_{j}" for j in range(len(all_layers_prompts[cot_trace_depth-1]))]:
            workflow.add_edge(node, "synthesis")

        workflow.add_edge("synthesis", END)
        graph = workflow.compile()

        ascii_diagram = graph.get_graph().draw_ascii()
        await log_stream.put(ascii_diagram)


        final_result_node = None
        async for output in graph.astream(imported_state):
            if "synthesis" in output:
                final_result_node = output["synthesis"]

        await log_stream.put("--- [INFERENCE-ONLY] Run complete. ---")

        return JSONResponse(content={
            "message": "Inference complete.",
            "code_solution": final_result_node.get("final_solution", {}).get("proposed_solution", "No solution generated."),
            "reasoning": final_result_node.get("final_solution", {}).get("reasoning", "No reasoning provided."),
            "is_inference": True
        })

    except Exception as e:
        error_message = f"An error occurred during inference: {e}"
        await log_stream.put(error_message)
        await log_stream.put(traceback.format_exc())
        return JSONResponse(content={"message": error_message, "traceback": traceback.format_exc()}, status_code=500)




@app.post("/build_and_run_graph")
async def build_and_run_graph(payload: dict = Body(...)):
    llm = None
    embeddings_model = None
    summarizer_llm = None
    try:
        params = payload.get("params")

        if params.get("coder_debug_mode") == 'true':
            await log_stream.put(f"--- 💻 CODER DEBUG MODE ENABLED 💻 ---")
            llm = CoderMockLLM()
            summarizer_llm = CoderMockLLM()
            embeddings_model = OllamaEmbeddings(model="mxbai-embed-large:latest")
        elif params.get("debug_mode") == 'true':
            await log_stream.put(f"--- 🚀 DEBUG MODE ENABLED 🚀 ---")
            llm = MockLLM()
            summarizer_llm = MockLLM()
            embeddings_model = OllamaEmbeddings(model="mxbai-embed-large:latest")
        else:
            
            summarizer_llm = ChatOllama(model="qwen3:1.7b", temperature=0)
            embeddings_model = OllamaEmbeddings(model="mxbai-embed-large:latest")
            model_name = params.get("ollama_model", "dengcao/Qwen3-3B-A3B-Instruct-2507:latest")
            await log_stream.put(f"--- Initializing Main Agent LLM: Ollama ({model_name}) ---")
            llm = ChatOllama(model=model_name, temperature=0.4)
            await llm.ainvoke("Hi")
            await log_stream.put("--- Main Agent LLM Connection Successful ---")

    except Exception as e:
        error_message = f"Failed to initialize LLM: {e}. Please ensure the selected provider is configured correctly."
        await log_stream.put(error_message)
        return JSONResponse(content={"message": error_message, "traceback": traceback.format_exc()}, status_code=500)
    
    mbti_archetypes = params.get("mbti_archetypes")
    user_prompt = params.get("prompt")
    word_vector_size = int(params.get("vector_word_size"))
    cot_trace_depth = int(params.get('cot_trace_depth', 3))

    code_detection_chain = get_code_detector_chain(llm)
    is_code = (await code_detection_chain.ainvoke({"text": user_prompt})).strip().lower() == 'true'
    await log_stream.put(f"Is Code: {is_code}")

    if params.get("coder_debug_mode") == "true":
        is_code = True
    elif params.get("debug_mode") == "true":
        is_code = False


    if not mbti_archetypes or len(mbti_archetypes) < 2:
        error_message = "Validation failed: You must select at least 2 MBTI archetypes."
        await log_stream.put(error_message)
        return JSONResponse(content={"message": error_message, "traceback": "User did not select enough archetypes from the GUI."}, status_code=400)

    await log_stream.put("--- Starting Graph Build and Run Process ---")
    await log_stream.put(f"Parameters: {params}")

    try:
        await log_stream.put("--- Decomposing Original Problem into Subproblems ---")
        num_agents_per_layer = len(mbti_archetypes)
        total_agents_to_create = num_agents_per_layer * cot_trace_depth
        decomposition_chain = get_problem_decomposition_chain(llm)
        
        try:
            sub_problems_str = await decomposition_chain.ainvoke({
                "problem": user_prompt,
                "num_sub_problems": total_agents_to_create
            })
            sub_problems_list = clean_and_parse_json(sub_problems_str).get("sub_problems", [])
            if len(sub_problems_list) != total_agents_to_create:
                raise ValueError(f"Decomposition failed: Expected {total_agents_to_create} subproblems, but got {len(sub_problems_list)}.")
            await log_stream.put(f"SUCCESS: Decomposed problem into {len(sub_problems_list)} subproblems.")
        except Exception as e:
            await log_stream.put(f"ERROR: Failed to decompose problem. Error: {e}. Defaulting to using the original prompt for all agents.")
            sub_problems_list = [user_prompt] * total_agents_to_create

        decomposed_problems_map = {}
        problem_idx = 0
        for i in range(cot_trace_depth):
            for j in range(num_agents_per_layer):
                agent_id = f"agent_{i}_{j}"
                if problem_idx < len(sub_problems_list):
                    decomposed_problems_map[agent_id] = sub_problems_list[problem_idx]
                    problem_idx += 1
                else:
                    decomposed_problems_map[agent_id] = user_prompt

        num_mbti_types = len(mbti_archetypes)
        total_verbs_to_generate = word_vector_size * num_mbti_types
        seed_generation_chain = get_seed_generation_chain(llm)
        generated_verbs_str = await seed_generation_chain.ainvoke({"problem": user_prompt, "word_count": total_verbs_to_generate})
        all_verbs = list(set(generated_verbs_str.split()))
        random.shuffle(all_verbs)
        seeds = {mbti: " ".join(random.sample(all_verbs, word_vector_size)) for mbti in mbti_archetypes}
        await log_stream.put(f"Seed verbs generated: {seeds}")

        all_layers_prompts = []
        agent_personas = {} 
        input_spanner_chain = get_input_spanner_chain(llm, params['prompt_alignment'], params['density'])
        
        await log_stream.put("--- Creating Layer 0 Agents ---")
        layer_0_prompts = []
        for j, (m, gw) in enumerate(seeds.items()):
            agent_id = f"agent_0_{j}"

            agent_personas[agent_id] = {"mbti_type": m, "name": names.get_full_name()}
            sub_problem = decomposed_problems_map.get(agent_id, user_prompt)
            prompt = await input_spanner_chain.ainvoke({"mbti_type": agent_personas[agent_id]["mbti_type"], "guiding_words": gw, "sub_problem": sub_problem, "name": agent_personas[agent_id]["name"]})
            await log_stream.put(f"Created Agent {agent_id} with prompt: {prompt}")
            layer_0_prompts.append(prompt)
        all_layers_prompts.append(layer_0_prompts)
        
        attribute_chain = get_attribute_and_hard_request_generator_chain(llm, params['vector_word_size'])
        dense_spanner_chain = get_dense_spanner_chain(llm, params['prompt_alignment'], params['density'], params['learning_rate'])
        
        agent_name_list = [names.get_full_name() for _ in range(total_agents_to_create)]

        for i in range(1, cot_trace_depth):
            await log_stream.put(f"--- Creating Layer {i} Agents ---")
            prev_layer_prompts = all_layers_prompts[i-1]
            current_layer_prompts = []
            for j, agent_prompt in enumerate(prev_layer_prompts):
                analysis_str = await attribute_chain.ainvoke({"agent_prompt": agent_prompt})
                try:
                    analysis = clean_and_parse_json(analysis_str)
                except (json.JSONDecodeError, AttributeError):
                    analysis = {"attributes": "", "hard_request": "Solve the original problem."}
                
                agent_id = f"agent_{i}_{j}"
                sub_problem = decomposed_problems_map.get(agent_id, user_prompt)
                
                assigned_mbti = random.choice(mbti_archetypes)
                assigned_name = agent_name_list.pop() if agent_name_list else names.get_full_name()
                agent_personas[agent_id] = {"mbti_type": assigned_mbti, "name": assigned_name} 
                await log_stream.put(f"LOG: Assigned Persona {assigned_name} (MBTI: {assigned_mbti}) to hidden agent {agent_id}")
                
                new_prompt = await dense_spanner_chain.ainvoke({
                    "attributes": analysis.get("attributes"),
                    "hard_request": analysis.get("hard_request"),
                    "critique": "",
                    "sub_problem": sub_problem,
                    "mbti_type": assigned_mbti,
                    "name": assigned_name
                })
                await log_stream.put(f"Created Agent {agent_id} with prompt: {new_prompt}")
                current_layer_prompts.append(new_prompt)
            all_layers_prompts.append(current_layer_prompts)
        
        workflow = StateGraph(GraphState)

        def epoch_gateway(state: GraphState):
            new_epoch = state.get("epoch", 0) + 1
            state['epoch'] = new_epoch
            state['agent_outputs'] = {}
            return state
            
        workflow.add_node("epoch_gateway", epoch_gateway)

        for i, layer_prompts in enumerate(all_layers_prompts):
            for j, prompt in enumerate(layer_prompts):
                node_id = f"agent_{i}_{j}"
                workflow.add_node(node_id, create_agent_node(llm, node_id))
        
        workflow.add_node("synthesis", create_synthesis_node(llm))
        if is_code: workflow.add_node("code_execution", create_code_execution_node(llm))

        workflow.add_node("archive_epoch_outputs", create_archive_epoch_outputs_node())
        update_rag_index_node_func = create_update_rag_index_node(summarizer_llm, embeddings_model)
        workflow.add_node("update_rag_index", update_rag_index_node_func)
        workflow.add_node("metrics", create_metrics_node(llm))
        workflow.add_node("reframe_and_decompose", create_reframe_and_decompose_node(llm))
        workflow.add_node("update_prompts", create_update_agent_prompts_node(llm))

        if  not is_code:
            workflow.add_node("harvest", create_final_harvest_node(llm, summarizer_llm, params.get("num_questions", 25) ))
            
        

        await log_stream.put("--- Connecting Graph Nodes ---")
        
        workflow.set_entry_point("epoch_gateway")
        await log_stream.put("LOG: Entry point set to 'epoch_gateway'.")
        
        first_layer_nodes = [f"agent_0_{j}" for j in range(len(all_layers_prompts[0]))]
        for node in first_layer_nodes:
            workflow.add_edge("epoch_gateway", node)
            await log_stream.put(f"CONNECT: epoch_gateway -> {node}")

        for i in range(cot_trace_depth - 1):
            current_layer_nodes = [f"agent_{i}_{j}" for j in range(len(all_layers_prompts[i]))]
            next_layer_nodes = [f"agent_{i+1}_{k}" for k in range(len(all_layers_prompts[i+1]))]
            for current_node in current_layer_nodes:
                for next_node in next_layer_nodes:
                    workflow.add_edge(current_node, next_node)
                    await log_stream.put(f"CONNECT: {current_node} -> {next_node}")
        
        last_layer_idx = cot_trace_depth - 1
        last_layer_nodes = [f"agent_{last_layer_idx}_{j}" for j in range(len(all_layers_prompts[last_layer_idx]))]
        for node in last_layer_nodes:
            workflow.add_edge(node, "synthesis")
            await log_stream.put(f"CONNECT: {node} -> synthesis")


        if is_code:

            workflow.add_edge("synthesis", "code_execution")
            await log_stream.put("CONNECT: synthesis -> code_execution") 
            workflow.add_edge("code_execution", "archive_epoch_outputs")
            await log_stream.put("CONNECT: code_execution -> archive_epoch_outputs")
        else:
            workflow.add_edge("synthesis", "archive_epoch_outputs")
            await log_stream.put("CONNECT: synthesis -> archive_epoch_outputs")
        
        workflow.add_edge("archive_epoch_outputs", "update_rag_index")
        await log_stream.put("CONNECT: archive_epoch_outputs -> update_rag_index")
        
        workflow.add_edge("update_rag_index", "metrics")
        await log_stream.put("CONNECT: update_rag_index -> metrics")

        async def assess_progress_and_decide_path(state: GraphState):
                if state.get("is_code_request"):

                    if state["epoch"] >= state["max_epochs"]:

                        await log_stream.put(f"LOG: Final epoch ({state['epoch']}) finished after code failure.")
                        return END
                    else:
                        return "reframe_and_decompose"

                else:

                    if state["epoch"] >= state["max_epochs"]:
                        await log_stream.put(f"LOG: Final epoch ({state['epoch']}) finished. Proceeding to final RAG indexing before chat.")
                        return "harvest" 
                    
                    else:
                        return "reframe_and_decompose"

        if is_code:
            workflow.add_conditional_edges(
                "metrics",
                assess_progress_and_decide_path,{
                    "reframe_and_decompose": "reframe_and_decompose",
                    END: END
                    })

        else:
 
            workflow.add_conditional_edges(
                "metrics",
                assess_progress_and_decide_path,{
                    "reframe_and_decompose": "reframe_and_decompose",
                    "update_prompts": "update_prompts","harvest": "harvest"})

        if not is_code:

            workflow.add_edge("harvest", END)
            await log_stream.put("CONNECT: metrics -> END")
                    
        workflow.add_edge("reframe_and_decompose", "update_prompts")
        await log_stream.put("CONNECT: reframe_and_decompose -> update_prompts")

        workflow.add_edge("update_prompts", "epoch_gateway")
        await log_stream.put("CONNECT: update_prompts -> epoch_gateway (loop)")

        graph = workflow.compile()
        await log_stream.put("Graph compiled successfully.") 
        
        ascii_art = graph.get_graph().draw_ascii()
        await log_stream.put(ascii_art)
        
        session_id = str(uuid.uuid4())

        initial_state = {
            "session_id": session_id,
            "original_request": user_prompt,
            "current_problem": user_prompt,
            "decomposed_problems": decomposed_problems_map,
            "epoch": 0,
            "max_epochs": int(params["num_epochs"]),
            "params": params, 
            "all_layers_prompts": all_layers_prompts,
            "agent_personas": agent_personas,
            "is_code_request": is_code, 
            "agent_outputs": {}, 
            "memory": {}, 
            "final_solution": None,
            "previous_solution": "",
            "chat_history": [],
            "layers": [], 
            "critiques": {}, 
            "perplexity_history": [],
            "raptor_index": None,
            "all_rag_documents": [],
            "academic_papers": None, 
            "summarizer_llm": summarizer_llm,
            "embeddings_model": embeddings_model, 
            "modules": [],
            "synthesis_context_queue": [],
            "synthesis_execution_success": True 
        }
        initial_state["llm"] = llm 
        sessions[session_id] = initial_state
        
        await log_stream.put(f"--- Starting Execution (Epochs: {params['num_epochs']}) ---")
        
        final_state_value = None
        async for output in graph.astream(initial_state, {'recursion_limit': (int(params["num_epochs"]) + 5) * len(all_layers_prompts) * 5}):
            for node_name, node_output in output.items():
                await log_stream.put(f"--- Node Finished Processing: {node_name} ---")
                if node_output is not None:
                    current_session_state = sessions.get(session_id, initial_state)
                    for key, value in node_output.items():
                        if key in ['agent_outputs', 'memory', 'agent_personas', 'critiques'] and isinstance(current_session_state.get(key), dict):
                            current_session_state[key].update(value)
                        else:
                            current_session_state[key] = value
                    sessions[session_id] = current_session_state
                    final_state_value = current_session_state
        
        if not final_state_value:
             final_state_value = sessions.get(session_id, {})

        if is_code:
            final_code_solution = final_state_value.get("final_solution", {})
            final_modules = final_state_value.get("modules", [])
            await log_stream.put(f"--- 💻 Code Generation Finished. Returning final code and {len(final_modules)} modules. ---")
            return JSONResponse(content={
                "message": "Code generation complete.",
                "code_solution": final_code_solution.get("proposed_solution", "# No code generated."),
                "reasoning": final_code_solution.get("reasoning", "No reasoning provided."),
                "modules": final_modules
            })
        else:
            await log_stream.put("--- Agent Execution Finished. Pausing for User Chat. ---")

            return JSONResponse(content={
                "message": "Chat is now active.",
                "session_id": session_id
            })

    except Exception as e:
        error_message = f"An error occurred during graph execution: {e}"
        await log_stream.put(error_message)
        await log_stream.put(traceback.format_exc())
        return JSONResponse(content={"message": error_message, "traceback": traceback.format_exc()}, status_code=500)

@app.get("/export_qnn/{session_id}")
async def export_qnn(session_id: str):
    """
    Exports the current state of a session graph to a JSON file.
    """
    if session_id not in sessions:
        return JSONResponse(content={"error": "Session not found."}, status_code=404)

    state_to_export = sessions[session_id].copy()


    state_to_export.pop('llm', None)
    state_to_export.pop('summarizer_llm', None)
    state_to_export.pop('embeddings_model', None)
    state_to_export.pop('raptor_index', None) 

    for idx, document in enumerate(state_to_export['all_rag_documents']):
        state_to_export['all_rag_documents'][idx] = document.dict()
    

    await log_stream.put(f"--- [EXPORT] Exporting QNN for session {session_id} ---")

    return JSONResponse(
        content=state_to_export,
        headers={"Content-Disposition": f"attachment; filename=qnn_state_{session_id}.json"}
    )

@app.post("/import_qnn")
async def import_qnn(file: UploadFile = File(...)):
    """
    Imports a QNN JSON file to initialize a new session.
    """
    try:
        content = await file.read()
        imported_state = json.loads(content)
        
        session_id = str(uuid.uuid4())
        imported_state['session_id'] = session_id

        for idx, document in enumerate(imported_state['all_rag_documents']): 

            imported_state['all_rag_documents'][idx] = Document.from_dict(document)

        sessions[session_id] = imported_state
        await log_stream.put(f"--- [IMPORT] Successfully imported QNN file. New Session ID: {session_id} ---")
        
        return JSONResponse(content={
            "message": "QNN file imported successfully.",
            "session_id": session_id,
            "imported_params": imported_state.get("params", {})
        })
    except Exception as e:
        error_message = f"Failed to import QNN file: {e}"
        await log_stream.put(error_message)
        return JSONResponse(content={"message": error_message, "traceback": traceback.format_exc()}, status_code=500)


@app.post("/chat")
async def chat_with_index(payload: dict = Body(...)):
    message = payload.get("message")
    session_id = payload.get("session_id") 

    print("Sesion keys: ", sessions.keys())
    print("Session ID: ", session_id)
 
    if not session_id or session_id not in list(sessions.keys()):
        return JSONResponse(content={"error": "Invalid session ID"}, status_code=404)

    state = sessions[session_id]

    raptor_index = state.get("raptor_index")
    llm = state["llm"]

    if not raptor_index:
        return JSONResponse(content={"error": "RAG index not found for this session"}, status_code=500)

    async def stream_response():
        try:
            retrieved_docs = await asyncio.to_thread(raptor_index.retrieve, message, k=10)
            context = "\n\n---\n\n".join([doc.page_content for doc in retrieved_docs])

            chat_chain = get_rag_chat_chain(llm)
            full_response = ""
            async for chunk in chat_chain.astream({"context": context, "question": message}):
                content = chunk.content if hasattr(chunk, 'content') else chunk
                yield content
                full_response += content

            state["chat_history"].append({"role": "user", "content": message})
            state["chat_history"].append({"role": "ai", "content": full_response})

        except Exception as e:

            print(f"Error during chat streaming: {e}")
            yield f"Error: Could not generate response. {e}"

    return StreamingResponse(stream_response(), media_type="text/event-stream")

@app.post("/diagnostic_chat")
async def diagnostic_chat_with_index(payload: dict = Body(...)):
    message = payload.get("message")
    session_id = payload.get("session_id")
    message = payload.get("message")

    print("Sesion keys: ", sessions.keys())
    print("Session ID: ", session_id)

    if not session_id or session_id not in list(sessions.keys()):
        return JSONResponse(content={"error": "Invalid session ID"}, status_code=404)

    print("Entering diagnostic_chat_with_index")

    state = sessions[session_id]
    raptor_index = state.get("raptor_index")

    if not raptor_index:
        async def stream_error():
            yield "The RAG index for this session is not yet available. Please wait for the first epoch to complete."
        return StreamingResponse(stream_error(), media_type="text/event-stream")
        
    async def stream_response():
        try:
            query = message.strip()[5:]
            await log_stream.put(f"--- [DIAGNOSTIC] Raw RAG query received: '{query}' ---")
                
            retrieved_docs = await asyncio.to_thread(raptor_index.retrieve, query, k=10)
                
            if not retrieved_docs:
                yield "No relevant documents found in the RAPTOR index for that query."
                return

            yield "--- Top Relevant Documents (Raw Retrieval) ---\n\n"
            for i, doc in enumerate(retrieved_docs):
                    content_preview = doc.page_content.replace('\n', ' ').strip()
                    metadata_str = json.dumps(doc.metadata)
                    response_chunk = (
                        f"DOCUMENT #{i+1}\n"
                        f"-----------------\n"
                        f"METADATA: {metadata_str}\n"
                        f"CONTENT: {content_preview}...\n\n"
                    )
                    yield response_chunk

        except Exception as e:
            print(f"Error during diagnostic chat streaming: {e}")
            yield f"Error: Could not generate response. {e}"

    return StreamingResponse(stream_response(), media_type="text/event-stream")

@app.post("/harvest")
async def harvest_session(payload: dict = Body(...)):


    if not payload.get("session_id") or payload.get("session_id") not in list(sessions.keys()):
        return JSONResponse(content={"error": "Invalid request"}, status_code=404)

    session =  sessions.get(payload.get("session_id"))

    if not session:
        return JSONResponse(content={"error": "Invalid request"}, status_code=404)

    try:
        await log_stream.put("--- [HARVEST] Initiating Final Harvest Process ---")
        state = session 
        chat_history = session["chat_history"]
        llm = session["llm"]
        summarizer_llm = session["summarizer_llm"]
        embeddings_model = session["embeddings_model"]
        params = session["params"]

        chat_docs = []
        if chat_history:
            for i, turn in enumerate(chat_history):
                 if turn['role'] == 'ai':
                    user_turn = chat_history[i-1]
                    content = f"User Question: {user_turn['content']}\n\nAI Answer: {turn['content']}"
                    chat_docs.append(Document(page_content=content, metadata={"source": "chat_session", "turn": i//2}))
            await log_stream.put(f"LOG: Converted {len(chat_history)} chat turns into {len(chat_docs)} documents.")
            state["all_rag_documents"].extend(chat_docs)
            await log_stream.put(f"LOG: Added chat documents. Total RAG documents now: {len(state['all_rag_documents'])}.")
            
            await log_stream.put("--- [RAG PASS] Re-building Final RAPTOR Index with Chat History ---")
            update_rag_node = create_update_rag_index_node(summarizer_llm, embeddings_model)
            update_result = await update_rag_node(state, end_of_run=True)
            state.update(update_result)

        num_questions = int(params.get('num_questions', 25))
        final_harvest_node = create_final_harvest_node(llm, summarizer_llm, num_questions)
        final_harvest_result = await final_harvest_node(state)
        state.update(final_harvest_result)

        academic_papers = state.get("academic_papers", {})
        session_id = state.get("session_id", "")

        if academic_papers:
            final_reports[session_id] = academic_papers
            await log_stream.put(f"SUCCESS: Final report with {len(academic_papers)} papers created.")
        else:
            await log_stream.put("WARNING: No academic papers were generated in the final harvest.")


        return JSONResponse(content={
            "message": "Harvest complete.",
        })

    except Exception as e:
        error_message = f"An error occurred during harvest: {e}"
        await log_stream.put(error_message)
        await log_stream.put(traceback.format_exc())
        return JSONResponse(content={"message": error_message, "traceback": traceback.format_exc()}, status_code=500)


@app.get('/stream_log')
async def stream_log(request: Request):

    async def event_generator():
        while True:
            if await request.is_disconnected():
                print("Client disconnected from log stream.")
                break
            try:
                log_message = await asyncio.wait_for(log_stream.get(), timeout=1.0)
                yield f"data: {log_message}\n\n"
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error in stream: {e}")
                break

    return EventSourceResponse(event_generator())


@app.get("/download_report/{session_id}")
async def download_report(session_id: str):


    papers = final_reports.get(session_id, {})

    if not papers:
        return JSONResponse(content={"error": "Report not found or expired."}, status_code=404)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, (question, content) in enumerate(papers.items()):
            safe_question = re.sub(r'[^\w\s-]', '', question).strip().replace(' ', '_')
            filename = f"paper_{i+1}_{safe_question[:50]}.md"
            zip_file.writestr(filename, content)

    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=NOA_Report_{session_id}.zip"}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)