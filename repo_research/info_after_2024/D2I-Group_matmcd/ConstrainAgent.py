import os
from typing import List, Tuple, Dict

import numpy as np
from tqdm import tqdm

from Client.OpenAiClient import OpenAIClient
from Client.ReactClient import ReactClient
from Client.MistralClient import MistralClient
from Client.LlamaClient import LlamaClient
from config import MODEL, OPENAI_API_KEY, MISTRAL_API_KEY, LLAMA_API_KEY

from .LLMs import (
    ConstrainLLM,
    DomainKnowledgeLLM,
    PositiveDomainKnowledgeLLM,
    NegativeDomainKnowledgeLLM,
    ConstrainJudgerLLM,
    ConstrainReasoningLLM,
)


class ConstrainAgent:
    """Base class for constraint agents.

    This class serves as the base class for different types of constraint agents
    that generate constraints between variable pairs.
    """

    def __init__(self): ...
    def run(self) -> np.ndarray: ...


class ConstrainNormalAgent(ConstrainAgent):
    """An agent that leverages domain knowledge from LLMs to generate constraints.

    This agent first obtains domain knowledge through LLM queries, then uses this
    knowledge to construct a constraint matrix that can guide causal discovery
    algorithms.
    """

    def __init__(
        self,
        label: List[str],
        theme: str,
        dataset_information: str = None,
        node_information: List[str] = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
        use_reasoning: bool = False,
    ) -> None:
        """Initializes the ConstrainAgent with dataset and domain information.

        Args:
            label: List of variable names in the causal system.
            theme: The domain/topic area of the causal analysis.
            dataset_information: Optional description of the dataset context.
            node_information: Optional list of detailed descriptions for each variable.
            graph_matrix: Optional adjacency matrix from preliminary causal discovery.
            causal_discovery_algorithm: Optional name of the algorithm used for initial
                causal discovery.
        """
        self.label = label
        self.theme = theme
        self.dataset_information = dataset_information
        self.node_information = node_information
        self.graph_matrix = graph_matrix
        self.causal_discovery_algorithm = causal_discovery_algorithm

        self.prompt_dict = None  # Stores prompts used for LLM queries
        self.domain_knowledge_dict = None  # Stores domain knowledge responses from LLM

        self.node_num = len(self.label)
        self.use_reasoning = use_reasoning
        # Initialize LLM for generating domain knowledge about causal relationships
        if "gpt" in MODEL:
            client = OpenAIClient(OPENAI_API_KEY, MODEL)
        elif "mistral" in MODEL:
            client = MistralClient(MISTRAL_API_KEY, MODEL)
        elif "llama" in MODEL or "gemma" in MODEL:
            client = LlamaClient(LLAMA_API_KEY, MODEL)

        self.domain_knowledge_LLM = DomainKnowledgeLLM(
            client,
            self.label,
            self.theme,
            dataset_information=self.dataset_information,
            graph_matrix=self.graph_matrix,
            causal_discovery_algorithm=self.causal_discovery_algorithm,
        )

    def load_domain_knowledge(self, cache_path: str) -> Tuple[Dict, Dict]:
        """Loads cached domain knowledge and prompts from disk.

        Args:
            cache_path: Directory path containing the cached files.

        Returns:
            A tuple containing:
                - prompt dictionary
                - domain knowledge dictionary
        """
        print(
            f"Loading domain knowledge from {cache_path}/prompt_dict{'_with_info' if self.dataset_information else ''}{'_reasoning' if self.use_reasoning else ''}.npy"
        )
        self.prompt_dict = np.load(
            f"{cache_path}/prompt_dict{'_with_info' if self.dataset_information else ''}{'_reasoning' if self.use_reasoning else ''}.npy",
            allow_pickle=True,
        ).item()
        self.domain_knowledge_dict = np.load(
            f"{cache_path}/domain_knowledge_dict{'_with_info' if self.dataset_information else ''}{'_reasoning' if self.use_reasoning else ''}.npy",
            allow_pickle=True,
        ).item()
        return self.prompt_dict, self.domain_knowledge_dict

    def save_domain_knowledge(self, cache_path: str) -> None:
        """Saves domain knowledge and prompts to disk for future use.

        Args:
            cache_path: Directory path to save the cache files.
        """
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        np.save(
            f"{cache_path}/prompt_dict{'_with_info' if self.dataset_information else ''}{'_reasoning' if self.use_reasoning else ''}.npy",
            self.prompt_dict,
        )
        np.save(
            f"{cache_path}/domain_knowledge_dict{'_with_info' if self.dataset_information else ''}{'_reasoning' if self.use_reasoning else ''}.npy",
            self.domain_knowledge_dict,
        )

    def generate_domain_knowledge(
        self, use_cache: bool = True, cache_path=None
    ) -> Tuple[Dict, Dict]:
        """Generates or loads domain knowledge for all variable pairs using LLM.

        For each pair of variables, queries the LLM to obtain domain expertise about
        their potential causal relationship.

        Args:
            use_cache: If True, attempts to load cached results before generating new ones.
            cache_path: Directory path for cache files.

        Returns:
            A tuple containing:
                - prompt dictionary
                - domain knowledge dictionary
        """
        if use_cache and cache_path is not None:
            return self.load_domain_knowledge(cache_path)

        self.prompt_dict = {}
        self.domain_knowledge_dict = {}

        # Generate domain knowledge for each directed variable pair
        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating domain knowledge",
        ):
            self.prompt_dict[(self.label[i], self.label[j])] = (
                self.domain_knowledge_LLM.generate_prompt(
                    i, j, node_information=self.node_information
                )
            )
            self.domain_knowledge_dict[(self.label[i], self.label[j])] = (
                self.domain_knowledge_LLM.inquiry(temperature=0.5)
            )

        # Cache results if path provided
        if cache_path is not None:
            self.save_domain_knowledge(cache_path)

        return self.prompt_dict, self.domain_knowledge_dict

    def generate_constrain_matrix(self) -> np.ndarray:
        """Generates constraint matrix based on accumulated domain knowledge.

        Uses a separate LLM to analyze the domain knowledge and determine if each
        potential causal relationship is plausible, encoding this as constraints.

        Returns:
            A numpy array representing the constraint matrix where:
                -1 indicates no constraint
                0 indicates the causal relationship is forbidden
                1 indicates the causal relationship is required
        """

        # Initialize LLM for converting domain knowledge into constraint matrix
        #! Must put here, otherwise the domain knowledge dict is empty
        if "gpt" in MODEL:
            client = OpenAIClient(OPENAI_API_KEY, MODEL)
        elif "mistral" in MODEL:
            client = MistralClient(MISTRAL_API_KEY, MODEL)
        elif "llama" in MODEL or "gemma" in MODEL:
            client = LlamaClient(LLAMA_API_KEY, MODEL)
        if self.use_reasoning:
            self.constrain_LLM = ConstrainReasoningLLM(
                client,
                self.theme,
                self.domain_knowledge_dict,
            )
        else:
            self.constrain_LLM = ConstrainLLM(
                client,
                self.theme,
                self.domain_knowledge_dict,
            )
        self.constrain_matrix = np.full((self.node_num, self.node_num), -1)
        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            causal_entity, result_entity = self.label[i], self.label[j]
            self.constrain_LLM.generate_prompt(causal_entity, result_entity)
            self.constrain_LLM.inquiry(temperature=0.8)
            self.constrain_matrix[i, j] = self.constrain_LLM.downstream_processing()
        return self.constrain_matrix

    def run(self, use_cache: bool = True, cache_path=None) -> np.ndarray:
        """Executes the complete constraint generation pipeline.

        First generates/loads domain knowledge, then converts it into a constraint
        matrix.

        Args:
            use_cache: If True, attempts to load cached domain knowledge.
            cache_path: Directory path for cache files.

        Returns:
            Constraint matrix for guiding causal discovery algorithms.
        """
        self.generate_domain_knowledge(use_cache, cache_path)
        self.generate_constrain_matrix()
        return self.constrain_matrix


class ConstrainDebateAgent(ConstrainAgent):
    """An agent that uses debate-based approach to generate constraints.

    This agent leverages multiple LLMs to debate and reach consensus on causal
    relationships between variables.
    """

    def __init__(
        self,
        label: List[str],
        theme: str,
        rounds: int = 3,
        threshold: Tuple[float, float] = (0.2, 0.8),
        dataset_information: str = None,
        node_information: List[str] = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        """Initializes the ConstrainDebateAgent.

        Args:
            label: List of variable names in the causal system.
            theme: The domain/topic area of the causal analysis.
            threshold: The threshold tuple (lower, upper) for the constrain judger LLM.
                Defaults to (0.2, 0.8).
            dataset_information: Optional description of the dataset context.
            node_information: Optional list of detailed descriptions for each variable.
            graph_matrix: Optional adjacency matrix from preliminary causal discovery.
            causal_discovery_algorithm: Optional name of the algorithm used for initial
                causal discovery.
            rounds: Number of rounds of debate for each variable pair. Defaults to 3.
        """
        self.label = label
        self.theme = theme
        self.dataset_information = dataset_information
        self.node_information = node_information
        self.graph_matrix = graph_matrix
        self.causal_discovery_algorithm = causal_discovery_algorithm
        self.threshold = threshold
        self.rounds = rounds
        self.node_num = len(self.label)

        self.prompt_dict = {
            (self.label[i], self.label[j]): []
            for i in range(self.node_num)
            for j in range(self.node_num)
            if i != j
        }
        self.debating_memories = {
            (self.label[i], self.label[j]): []
            for i in range(self.node_num)
            for j in range(self.node_num)
            if i != j
        }
        if "gpt" in MODEL:
            print("Use GPT")
            client = OpenAIClient(OPENAI_API_KEY, MODEL)
        elif "mistral" in MODEL:
            client = MistralClient(MISTRAL_API_KEY, MODEL)

        self.positive_domain_knowledge_LLM = PositiveDomainKnowledgeLLM(
            client,
            self.label,
            self.theme,
            dataset_information=self.dataset_information,
            graph_matrix=self.graph_matrix,
            causal_discovery_algorithm=self.causal_discovery_algorithm,
        )

        self.negative_domain_knowledge_LLM = NegativeDomainKnowledgeLLM(
            client,
            self.label,
            self.theme,
            dataset_information=self.dataset_information,
            graph_matrix=self.graph_matrix,
            causal_discovery_algorithm=self.causal_discovery_algorithm,
        )

    def load_debating_memories(self, cache_path: str) -> Tuple[Dict, Dict]:
        """Loads cached debating memories and prompts from disk.

        Args:
            cache_path: Directory path containing the cached files.

        Returns:
            A tuple containing:
                - prompt dictionary
                - debating memories dictionary
        """
        self.prompt_dict = np.load(
            f"{cache_path}/debating_prompt_dict{'_with_info' if self.dataset_information else ''}.npy",
            allow_pickle=True,
        ).item()
        self.debating_memories = np.load(
            f"{cache_path}/debating_memories{'_with_info' if self.dataset_information else ''}.npy",
            allow_pickle=True,
        ).item()
        return self.prompt_dict, self.debating_memories

    def save_debating_memories(self, cache_path: str) -> None:
        """Saves debating memories and prompts to disk.

        Args:
            cache_path: Directory path to save the cache files.
        """
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        np.save(
            f"{cache_path}/debating_prompt_dict{'_with_info' if self.dataset_information else ''}.npy",
            self.prompt_dict,
        )
        np.save(
            f"{cache_path}/debating_memories{'_with_info' if self.dataset_information else ''}.npy",
            self.debating_memories,
        )

    def generate_constrain_matrix(self) -> np.ndarray:
        """Generates constraint matrix through debate between LLMs.

        Returns:
            A numpy array representing the constraint matrix where:
                -1 indicates no constraint
                0 indicates the causal relationship is forbidden
                1 indicates the causal relationship is required
        """
        self.constrain_matrix = np.full((self.node_num, self.node_num), -1)

        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            for _ in range(self.rounds):
                self.prompt_dict[(self.label[i], self.label[j])].append(
                    self.positive_domain_knowledge_LLM.generate_prompt(
                        i,
                        j,
                        node_information=self.node_information,
                        debating_memory=self.debating_memories[
                            (self.label[i], self.label[j])
                        ],
                    )
                )
                self.debating_memories[(self.label[i], self.label[j])].append(
                    self.positive_domain_knowledge_LLM.inquiry(temperature=0.5)
                )

                self.prompt_dict[(self.label[i], self.label[j])].append(
                    self.negative_domain_knowledge_LLM.generate_prompt(
                        i,
                        j,
                        node_information=self.node_information,
                        debating_memory=self.debating_memories[
                            (self.label[i], self.label[j])
                        ],
                    )
                )
                self.debating_memories[(self.label[i], self.label[j])].append(
                    self.negative_domain_knowledge_LLM.inquiry(temperature=0.5)
                )

                self.constrain_judger_LLM = ConstrainJudgerLLM(
                    OpenAIClient(OPENAI_API_KEY, MODEL),
                    self.theme,
                    self.debating_memories,
                )

                self.constrain_judger_LLM.generate_prompt(self.label[i], self.label[j])
                self.constrain_judger_LLM.inquiry(temperature=0.5)
                answer = self.constrain_judger_LLM.downstream_processing()
                if answer > self.threshold[1]:
                    self.constrain_matrix[i, j] = 1
                    break
                elif answer < self.threshold[0]:
                    self.constrain_matrix[i, j] = 0
                    break

            if answer > 0.5:
                self.constrain_matrix[i, j] = 1
            elif answer < 0.5:
                self.constrain_matrix[i, j] = 0

    def generate_constrain_matrix_with_cache(self) -> np.ndarray:
        """Generates constraint matrix using cached debating memories.

        Returns:
            A numpy array representing the constraint matrix where:
                -1 indicates no constraint
                0 indicates the causal relationship is forbidden
                1 indicates the causal relationship is required
        """
        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            self.constrain_judger_LLM = ConstrainJudgerLLM(
                OpenAIClient(OPENAI_API_KEY, MODEL),
                self.theme,
                self.debating_memories,
            )

            self.constrain_judger_LLM.generate_prompt(self.label[i], self.label[j])
            self.constrain_judger_LLM.inquiry(temperature=0.5)
            answer = self.constrain_judger_LLM.downstream_processing()
            if answer > 0.5:
                self.constrain_matrix[i, j] = 1
            elif answer < 0.5:
                self.constrain_matrix[i, j] = 0
        return self.constrain_matrix

    def run(self, use_cache: bool = True, cache_path: str = None) -> Dict:
        """Executes the complete debate-based constraint generation pipeline.

        Args:
            use_cache: If True, attempts to load cached debating memories.
            cache_path: Directory path for cache files.

        Returns:
            Constraint matrix for guiding causal discovery algorithms.
        """
        if use_cache and cache_path is not None:
            self.load_debating_memories(cache_path)
            self.generate_constrain_matrix_with_cache()
        else:
            self.generate_constrain_matrix()

            if cache_path is not None:
                self.save_debating_memories(cache_path)

        return self.constrain_matrix


class ConstrainReactAgent(ConstrainAgent):
    """An agent that leverages domain knowledge from LLMs to generate constraints.

    This agent first obtains domain knowledge through LLM queries, then uses this
    knowledge to construct a constraint matrix that can guide causal discovery
    algorithms.
    """

    def __init__(
        self,
        label: List[str],
        theme: str,
        dataset_information: str = None,
        node_information: List[str] = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        """Initializes the ConstrainAgent with dataset and domain information.

        Args:
            label: List of variable names in the causal system.
            theme: The domain/topic area of the causal analysis.
            dataset_information: Optional description of the dataset context.
            node_information: Optional list of detailed descriptions for each variable.
            graph_matrix: Optional adjacency matrix from preliminary causal discovery.
            causal_discovery_algorithm: Optional name of the algorithm used for initial
                causal discovery.
        """
        self.label = label
        self.theme = theme
        self.dataset_information = dataset_information
        self.node_information = node_information
        self.graph_matrix = graph_matrix
        self.causal_discovery_algorithm = causal_discovery_algorithm

        self.prompt_dict = None  # Stores prompts used for LLM queries
        self.domain_knowledge_dict = None  # Stores domain knowledge responses from LLM

        self.node_num = len(self.label)

        # Initialize LLM for generating domain knowledge about causal relationships
        self.domain_knowledge_LLM = DomainKnowledgeLLM(
            ReactClient(),
            self.label,
            self.theme,
            dataset_information=self.dataset_information,
            graph_matrix=self.graph_matrix,
            causal_discovery_algorithm=self.causal_discovery_algorithm,
        )

    def load_domain_knowledge(self, cache_path: str) -> Tuple[Dict, Dict]:
        """Loads cached domain knowledge and prompts from disk.

        Args:
            cache_path: Directory path containing the cached files.

        Returns:
            A tuple containing:
                - prompt dictionary
                - domain knowledge dictionary
        """
        self.prompt_dict = np.load(
            f"{cache_path}/React_prompt_dict{'_with_info' if self.dataset_information else ''}.npy",
            allow_pickle=True,
        ).item()
        self.domain_knowledge_dict = np.load(
            f"{cache_path}/React_domain_knowledge_dict{'_with_info' if self.dataset_information else ''}.npy",
            allow_pickle=True,
        ).item()
        return self.prompt_dict, self.domain_knowledge_dict

    def save_domain_knowledge(self, cache_path: str) -> None:
        """Saves domain knowledge and prompts to disk for future use.

        Args:
            cache_path: Directory path to save the cache files.
        """
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        np.save(
            f"{cache_path}/React_prompt_dict{'_with_info' if self.dataset_information else ''}.npy",
            self.prompt_dict,
        )
        np.save(
            f"{cache_path}/React_domain_knowledge_dict{'_with_info' if self.dataset_information else ''}.npy",
            self.domain_knowledge_dict,
        )

    def generate_domain_knowledge(
        self, use_cache: bool = True, cache_path=None
    ) -> Tuple[Dict, Dict]:
        """Generates or loads domain knowledge for all variable pairs using LLM.

        For each pair of variables, queries the LLM to obtain domain expertise about
        their potential causal relationship.

        Args:
            use_cache: If True, attempts to load cached results before generating new ones.
            cache_path: Directory path for cache files.

        Returns:
            A tuple containing:
                - prompt dictionary
                - domain knowledge dictionary
        """
        if use_cache and cache_path is not None:
            return self.load_domain_knowledge(cache_path)

        self.prompt_dict = {}
        self.domain_knowledge_dict = {}

        # Generate domain knowledge for each directed variable pair
        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating domain knowledge",
        ):
            self.prompt_dict[(self.label[i], self.label[j])] = (
                self.domain_knowledge_LLM.generate_prompt(
                    i, j, node_information=self.node_information
                )
            )
            self.domain_knowledge_dict[(self.label[i], self.label[j])] = (
                self.domain_knowledge_LLM.inquiry(temperature=0.5)
            )

        # Cache results if path provided
        if cache_path is not None:
            self.save_domain_knowledge(cache_path)

        return self.prompt_dict, self.domain_knowledge_dict

    def generate_constrain_matrix(self) -> np.ndarray:
        """Generates constraint matrix based on accumulated domain knowledge.

        Uses a separate LLM to analyze the domain knowledge and determine if each
        potential causal relationship is plausible, encoding this as constraints.

        Returns:
            A numpy array representing the constraint matrix where:
                -1 indicates no constraint
                0 indicates the causal relationship is forbidden
                1 indicates the causal relationship is required
        """

        self.constrain_LLM = ConstrainLLM(
            ReactClient(),
            self.theme,
            self.domain_knowledge_dict,
        )
        self.constrain_matrix = np.full((self.node_num, self.node_num), -1)
        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            causal_entity, result_entity = self.label[i], self.label[j]
            self.constrain_LLM.generate_prompt(causal_entity, result_entity)
            self.constrain_LLM.inquiry(temperature=0.8)
            self.constrain_matrix[i, j] = self.constrain_LLM.downstream_processing()
        return self.constrain_matrix

    def run(self, use_cache: bool = True, cache_path=None) -> np.ndarray:
        """Executes the complete constraint generation pipeline.

        First generates/loads domain knowledge, then converts it into a constraint
        matrix.

        Args:
            use_cache: If True, attempts to load cached domain knowledge.
            cache_path: Directory path for cache files.

        Returns:
            Constraint matrix for guiding causal discovery algorithms.
        """
        self.generate_domain_knowledge(use_cache, cache_path)
        self.generate_constrain_matrix()
        return self.constrain_matrix


class OnlyReactAgent(ConstrainAgent):
    """Temporary class for testing the effectiveness of the React agent."""

    def __init__(
        self,
        label: List[str],
        theme: str,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        self.label = label
        self.theme = theme
        self.graph_matrix = graph_matrix
        self.causal_discovery_algorithm = causal_discovery_algorithm

        self.node_num = len(self.label)

        from Client.ReactClient import ReactClient

        self.client = ReactClient()

    def generate_constrain_matrix(self) -> np.ndarray:
        self.constrain_matrix = np.full((self.node_num, self.node_num), -1)

        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            causal_entity, result_entity = self.label[i], self.label[j]

            prompt = f"We want to carry out causal inference on {self.theme},"
            prompt += f"We have already conducted the statistical causal discovery with {self.causal_discovery_algorithm} algorithm.\n\n"
            prompt += "All of the edges and their coefficients of the structural causal model suggested by the statistical causal discovery are below:\n"

            for m_1 in range(self.node_num):
                for m_2 in range(self.node_num):
                    if m_1 == m_2:
                        continue
                    if self.graph_matrix[m_1, m_2] == 0:
                        continue
                    else:
                        prompt += (
                            f"{self.label[m_1]} is the cause of {self.label[m_2]}.\n"
                        )

            prompt += (
                f"Do you think that the change in {causal_entity} will lead to a change in {result_entity}, "
                f"which means {causal_entity} is the reason for {result_entity}?"
                f"You should try your best to search the information from the internet."
                f"Please answer this question with ⟨yes⟩ or ⟨no⟩.\n"
                f"No answers except these two responses are needed.\n"
                f"Your response should be in the following format:\n"
                f"⟨yes⟩ or ⟨no⟩\n"
                f"Please provide your response in the format specified above.\n"
                f"Your response:\n"
            )
            system_prompt = "You are a helpful assistant for causal inference."
            response = self.client.inquire_LLMs(prompt, system_prompt)
            print(f"response: {response}")

            if "yes" in response:
                self.constrain_matrix[i, j] = 1
            elif "no" in response:
                self.constrain_matrix[i, j] = 0

            print(f"add constrain to {self.label[i]} and {self.label[j]},{i},{j}")

            print(f"constrain_matrix: {self.constrain_matrix}")

        return self.constrain_matrix

    def run(self) -> np.ndarray:
        self.generate_constrain_matrix()
        return self.constrain_matrix


class OnlyLLMAgent(ConstrainAgent):
    """
    An agent that uses a single LLM for optimization without dataset or node information.
    If dataset_information and node_information are provided, this serves as an ablation
    study for the ConstrainAgent.
    """

    def __init__(
        self,
        label: List[str],
        theme: str,
        dataset_information: str = None,
        node_information: List[str] = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
        use_reasoning: bool = False,
        guess_number: int = 2,
    ) -> None:
        self.label = label
        self.theme = theme
        self.dataset_information = dataset_information
        self.node_information = node_information
        self.graph_matrix = graph_matrix
        self.causal_discovery_algorithm = causal_discovery_algorithm
        self.client = OpenAIClient(OPENAI_API_KEY, MODEL)

        self.node_num = len(self.label)
        self.use_reasoning = use_reasoning
        self.guess_number = guess_number

    def generate_constrain_matrix(self) -> np.ndarray:
        self.constrain_matrix = np.full((self.node_num, self.node_num), -1)

        for i, j in tqdm(
            [
                (i, j)
                for i in range(self.node_num)
                for j in range(self.node_num)
                if i != j
            ],
            desc="Generating constraint matrix",
        ):
            causal_entity, result_entity = self.label[i], self.label[j]

            if self.use_reasoning:
                prompt = (
                    f"Provide your {self.guess_number} best guesses and the probability that each is correct (0.0 to 1.0) for the following question."
                    f"Give ONLY the guesses and probabilities, no other words or explanation. "
                    f"Each guess should infer the relationship step by step and finally end with <yes> or <no>.\n"
                    f"For example:\n\n"
                    f"G1: <first most likely guess, infer the relationship step by step and finally end with <yes> or <no>>\n\n"
                    f"P1: <the probability between 0.0 and 1.0 that G1 is correct, without any extra comments; just the probability!>\n\n"
                    f"---"
                    f"G2: <second most likely guess, infer the relationship step by step and finally end with <yes> or <no>>\n\n"
                    f"P2: <the probability between 0.0 and 1.0 that G2 is correct, without any extra comments; just the probability!> \n\n"
                    f"---"
                    f"Please Exactly follow the format above, and do not add any other comments or explanations."
                    f"The question is:"
                )

            else:
                prompt = ""

            prompt += f"We want to carry out causal inference on {self.theme},"
            if self.dataset_information is not None:
                prompt += f" the summary of dataset: {self.dataset_information}. Considering {', '.join(self.label)} as variables.\n\n"
            else:
                prompt += f" considering {', '.join(self.label)} as variables.\n\n"

            prompt += f"We have already conducted the statistical causal discovery with {self.causal_discovery_algorithm} algorithm.\n\n"
            prompt += "All of the edges and their coefficients of the structural causal model suggested by the statistical causal discovery are below:\n"

            for m_1 in range(self.node_num):
                for m_2 in range(self.node_num):
                    if m_1 == m_2:
                        continue
                    if self.graph_matrix[m_1, m_2] == 0:
                        continue
                    else:
                        prompt += (
                            f"{self.label[m_1]} is the cause of {self.label[m_2]}.\n"
                        )

            if self.node_information is not None:
                prompt += (
                    f"In addition, here is the information of {self.label[i]} and {self.label[j]} from reliable sources.\n"
                    f"{self.node_information[self.label[i]]}\n\n"
                    f"{self.node_information[self.label[j]]}\n\n"
                )

            prompt += (
                f"Do you think that the change in {causal_entity} will lead to a change in {result_entity}, "
                f"which means {causal_entity} is the reason for {result_entity}?"
            )

            if self.use_reasoning is False:
                prompt += (
                    "Please answer this question with ⟨yes⟩ or ⟨no⟩.\n"
                    "No answers except these two responses are needed.\n"
                    "Your response should be in the following format:\n"
                    "⟨yes⟩ or ⟨no⟩\n"
                    "Please provide your response in the format specified above.\n"
                )

            prompt += "Your response:\n"

            system_prompt = "You are a helpful assistant for causal inference."
            response = self.client.inquire_LLMs(prompt, system_prompt)
            print(f"response: {response}")

            if self.use_reasoning:
                parts = response.split("---")
                print(f"parts: {parts}")
                guess_prob_pairs = []

                for part in parts:
                    lines = part.strip().split("\n\n")
                    for k in range(len(lines) - 1):
                        try:
                            if lines[k].startswith("G") and lines[k + 1].startswith(
                                "P"
                            ):
                                guess = lines[k].split(": ", 1)[1].strip()
                                prob_str = lines[k + 1].split(": ", 1)[1].strip()
                                prob_str = "".join(
                                    c for c in prob_str if c.isdigit() or c == "."
                                )
                                prob = float(prob_str) if prob_str else 0.0
                                guess_prob_pairs.append((prob, guess))
                        except Exception:
                            print(f"error in {lines[k]} and {lines[k + 1]}")
                            continue
                guess_prob_pairs.sort(reverse=True)
                answer = guess_prob_pairs[0][1]
                print(f"answer: {answer}")
                if "yes" in answer:
                    self.constrain_matrix[i, j] = 1
                elif "no" in answer:
                    self.constrain_matrix[i, j] = 0

            else:
                if "yes" in response:
                    self.constrain_matrix[i, j] = 1
                elif "no" in response:
                    self.constrain_matrix[i, j] = 0

            print(f"add constrain to {self.label[i]} and {self.label[j]},{i},{j}")
            print(f"constrain_matrix: {self.constrain_matrix}")

        return self.constrain_matrix

    def run(self) -> np.ndarray:
        self.generate_constrain_matrix()
        return self.constrain_matrix
