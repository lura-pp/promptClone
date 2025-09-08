from typing import List, Tuple

import numpy as np


class LLMs:
    """Base LLM class that defines the basic interface for LLM interaction.

    This class provides the core functionality for interacting with language models,
    including making inquiries and handling responses.

    Attributes:
        client: The LLM client used for making API calls.
        LLM_answer: The most recent response from the language model.
    """

    def __init__(self, client) -> None:
        """Initializes the LLM class.

        Args:
            client: The LLM client to use for API calls.
        """
        self.client = client  # The LLM client used for making API calls
        self.LLM_answer = None  # The most recent response from the language model

    def inquiry(self, temperature: float = 0.5) -> str:
        """Makes an inquiry to the language model.

        Args:
            temperature: Sampling temperature for controlling randomness in generation.
                Defaults to 0.5.

        Returns:
            The language model's response as a string.

        Raises:
            ValueError: If prompt or system_prompt is not set.
        """
        if self.prompt is None or self.system_prompt is None:
            raise ValueError(
                "prompt or system_prompt is None. Please call generate_prompt() method first."
            )
        self.LLM_answer = self.client.inquire_LLMs(
            self.prompt, self.system_prompt, temperature
        )
        return self.LLM_answer

    def show_prompt(self) -> Tuple[str, str]:
        """Displays the current prompt.

        Returns:
            A tuple containing (user prompt, system prompt).

        Raises:
            ValueError: If prompt is not set.
        """
        if self.prompt is None:
            raise ValueError(
                "prompt is None. Please call generate_prompt() method first."
            )
        return self.prompt, self.system_prompt

    def show_answer(self) -> str:
        """Displays the language model's most recent response.

        Returns:
            The language model's response as a string.

        Raises:
            ValueError: If no inquiry has been made yet.
        """
        if self.LLM_answer is None:
            raise ValueError("LLM_answer is None. Please call inquiry() method first.")
        return self.LLM_answer

    def generate_prompt(self) -> Tuple[str, str]:
        """Abstract method for generating prompts.

        Returns:
            A tuple containing (user prompt, system prompt).

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement generate_prompt() method")

    def downstream_processing(self):
        """Abstract method for processing language model responses.

        Raises:
            NotImplementedError: This method must be implemented by subclasses.
        """
        raise NotImplementedError(
            "Subclasses must implement downstream_processing() method"
        )


class DomainKnowledgeLLM(LLMs):
    """LLM class for domain knowledge verification.

    This class handles verification of domain knowledge by interacting with language
    models in a specific domain context.

    Attributes:
        labels: List of variable labels.
        theme: Domain theme.
        dataset_information: Information about the dataset.
        graph_matrix: Causal graph adjacency matrix.
        causal_discovery_algorithm: Name of causal discovery algorithm.
        dataset_prompt: Generated dataset description prompt.
        graph_prompt: Generated graph description prompt.
        prompt: Complete user prompt.
        system_prompt: Complete system prompt.
        LLM_answer: Most recent LLM response.
    """

    def __init__(
        self,
        client,
        labels: List[str],
        theme: str,
        dataset_information: str = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        """Initializes the DomainKnowledgeLLM.

        Args:
            client: The LLM client to use.
            labels: List of variable labels.
            theme: Domain theme.
            dataset_information: Optional information about the dataset.
            graph_matrix: Optional causal graph adjacency matrix.
            causal_discovery_algorithm: Optional name of causal discovery algorithm.
        """
        super().__init__(client)

        self.labels = labels  # List of variable labels
        self.theme = theme  # Domain theme
        self.dataset_information = dataset_information  # Dataset information
        self.graph_matrix = graph_matrix  # Causal graph adjacency matrix
        self.causal_discovery_algorithm = (
            causal_discovery_algorithm  # Name of causal discovery algorithm
        )

        # Prompt components
        self.dataset_prompt = ""
        self.graph_prompt = ""

        # State variables
        self.prompt = None
        self.system_prompt = None
        self.LLM_answer = None

    def generate_graph_prompt(self) -> str:
        """Generates the prompt section describing the causal graph.

        Returns:
            A string containing the graph description prompt.
        """
        num_nodes = self.graph_matrix.shape[0]

        prompt = f"We have conducted the statistical causal discovery with {self.causal_discovery_algorithm} algorithm.\n\n"
        prompt += "The edges and their coefficients of the structural causal model suggested by the statistical causal discovery are as follows:\n"

        # Traverse adjacency matrix to generate edge descriptions
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    continue
                if self.graph_matrix[i, j] == 0:
                    continue
                else:
                    prompt += f"{self.labels[i]} is the cause of {self.labels[j]}.\n"
        prompt += "\n"

        # Add description about target causal relationship
        if self.graph_matrix[self.cause_index, self.result_index] == 1:
            prompt += f"Based on the results above, it seems that changes in {self.cause_entity} directly affect {self.result_entity}.\n\n"
        else:
            prompt += f"Based on the results above, it seems that changes in {self.cause_entity} do not directly affect {self.result_entity}.\n\n"
        return prompt

    def generate_prompt(
        self,
        cause_index: int,
        result_index: int,
        node_information: dict = None,
    ) -> Tuple[str, str]:
        """Generates complete prompt for domain knowledge verification.

        Args:
            cause_index: Index of cause variable.
            result_index: Index of effect variable.
            node_information: Optional additional information about nodes.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.cause_index = cause_index
        self.result_index = result_index
        self.cause_entity = self.labels[self.cause_index]
        self.result_entity = self.labels[self.result_index]

        # Generate dataset description section
        if self.dataset_prompt == "":
            self.dataset_prompt = (
                f"We want to perform causal discovery on {self.theme},"
            )

            if self.dataset_information is not None:
                self.dataset_prompt += f" the summary of dataset: {self.dataset_information}. Considering {', '.join(self.labels)} as variables.\n\n"
            else:
                self.dataset_prompt += (
                    f" considering {', '.join(self.labels)} as variables.\n\n"
                )

        # Generate causal graph description section
        if (
            self.graph_prompt == ""
            and self.graph_matrix is not None
            and self.causal_discovery_algorithm is not None
        ):
            self.graph_prompt = self.generate_graph_prompt()

        if node_information is not None:
            info_prompt = (
                f"In addition, here is the information of {self.cause_entity} and {self.result_entity} from reliable sources.\n"
                f"{node_information[self.cause_entity]}\n\n"
                f"{node_information[self.result_entity]}\n\n"
            )
        else:
            info_prompt = ""

        # Generate task description section
        final_prompt_template = (
            f"Your task is to interpret this result from a domain knowledge perspective "
            f"and determine whether this statistically suggested hypothesis is plausible in "
            f"the context of the domain.\n\n"
            f"Please provide an explanation that leverages your expert knowledge on the causal "
            f"relationship between {self.cause_entity} and {self.result_entity}, "
            f"and assess the correctness of this causal discovery result.\n "
            f"Your response should consider the relevant factors and provide "
            f"a reasonable explanation based on your understanding of the domain."
        )

        # Combine complete prompt
        self.prompt = (
            self.dataset_prompt
            + self.graph_prompt
            + info_prompt
            + final_prompt_template
        )

        self.system_prompt = f"You are an expert in {self.theme}."
        return self.prompt, self.system_prompt


class PositiveDomainKnowledgeLLM(DomainKnowledgeLLM):
    """LLM class for generating positive domain knowledge arguments.

    This class specializes in generating arguments that support causal relationships.
    """

    def __init__(
        self,
        client,
        labels: List[str],
        theme: str,
        dataset_information: str = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        """Initializes the PositiveDomainKnowledgeLLM.

        Args:
            client: The LLM client to use.
            labels: List of variable labels.
            theme: Domain theme.
            dataset_information: Optional information about the dataset.
            graph_matrix: Optional causal graph adjacency matrix.
            causal_discovery_algorithm: Optional name of causal discovery algorithm.
        """
        super().__init__(
            client,
            labels,
            theme,
            dataset_information,
            graph_matrix,
            causal_discovery_algorithm,
        )

    def generate_debating_prompt(self, debating_memory: list) -> str:
        """Generates prompt for debate context.

        Args:
            debating_memory: List of previous debate exchanges.

        Returns:
            A string containing the debate context prompt.
        """
        debating_prompt = "Here is the debating memory of the previous round:\n"
        for index, content in enumerate(debating_memory):
            if index % 2 == 0:
                debating_prompt += f"The positive expert says: {content}\n"
            else:
                debating_prompt += f"The negative expert says: {content}\n"
        debating_prompt += "\n"
        return debating_prompt

    def generate_prompt(
        self,
        cause_index: int,
        result_index: int,
        node_information: dict = None,
        debating_memory: dict = None,
    ) -> Tuple[str, str]:
        """Generates complete prompt for positive domain knowledge arguments.

        Args:
            cause_index: Index of cause variable.
            result_index: Index of effect variable.
            node_information: Optional additional information about nodes.
            debating_memory: Optional history of debate exchanges.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.cause_index = cause_index
        self.result_index = result_index
        self.cause_entity = self.labels[self.cause_index]
        self.result_entity = self.labels[self.result_index]

        # Generate dataset description section
        if self.dataset_prompt == "":
            self.dataset_prompt = (
                f"We want to carry out causal inference on {self.theme},"
            )

            if self.dataset_information is not None:
                self.dataset_prompt += f" the summary of dataset: {self.dataset_information}. Considering {', '.join(self.labels)} as variables.\n\n"
            else:
                self.dataset_prompt += (
                    f" considering {', '.join(self.labels)} as variables.\n\n"
                )

        # Generate causal graph description section
        if (
            self.graph_prompt == ""
            and self.graph_matrix is not None
            and self.causal_discovery_algorithm is not None
        ):
            self.graph_prompt = self.generate_graph_prompt()

        if node_information is not None:
            info_prompt = (
                f"In addition, here is the information of {self.cause_entity} and {self.result_entity} from reliable sources.\n"
                f"{node_information[self.cause_entity]}\n\n"
                f"{node_information[self.result_entity]}\n\n"
            )
        else:
            info_prompt = ""

        # Generate debating prompt
        if len(debating_memory) > 0:
            debating_prompt = self.generate_debating_prompt(debating_memory)
        else:
            debating_prompt = ""

        # Generate task description section
        final_prompt_template = (
            f"So, your task is to propose relevant content as much as possible to support the causal relationship between {self.cause_entity} and {self.result_entity}. "
            f"Your explanation can be based on the previous content and your own understanding of the relationship between the two."
        )
        # Combine complete prompt
        self.prompt = (
            self.dataset_prompt
            + self.graph_prompt
            + info_prompt
            + debating_prompt
            + final_prompt_template
        )

        self.system_prompt = f"You are an expert in {self.theme} who want to support the causal relationship between {self.cause_entity} and {self.result_entity}."
        return self.prompt, self.system_prompt

    def downstream_processing(self):
        """Processes LLM's response for positive arguments.

        Returns:
            A tuple containing (response label, LLM response).
        """
        return (f"Positive_{len(self.debating_memory)}", self.LLM_answer)


class NegativeDomainKnowledgeLLM(DomainKnowledgeLLM):
    """LLM class for generating negative domain knowledge arguments.

    This class specializes in generating arguments that oppose causal relationships.
    """

    def __init__(
        self,
        client,
        labels: List[str],
        theme: str,
        dataset_information: str = None,
        graph_matrix: np.ndarray = None,
        causal_discovery_algorithm: str = None,
    ) -> None:
        """Initializes the NegativeDomainKnowledgeLLM.

        Args:
            client: The LLM client to use.
            labels: List of variable labels.
            theme: Domain theme.
            dataset_information: Optional information about the dataset.
            graph_matrix: Optional causal graph adjacency matrix.
            causal_discovery_algorithm: Optional name of causal discovery algorithm.
        """
        super().__init__(
            client,
            labels,
            theme,
            dataset_information,
            graph_matrix,
            causal_discovery_algorithm,
        )

    def generate_debating_prompt(self, debating_memory: list) -> str:
        """Generates prompt for debate context.

        Args:
            debating_memory: List of previous debate exchanges.

        Returns:
            A string containing the debate context prompt.
        """
        debating_prompt = "Here is the debating memory of the previous round:\n"
        for index, content in enumerate(debating_memory):
            if index % 2 == 0:
                debating_prompt += f"The positive expert says: {content}\n"
            else:
                debating_prompt += f"The negative expert says: {content}\n"
        debating_prompt += "\n"
        return debating_prompt

    def generate_prompt(
        self,
        cause_index: int,
        result_index: int,
        node_information: dict = None,
        debating_memory: dict = None,
    ) -> Tuple[str, str]:
        """Generates complete prompt for negative domain knowledge arguments.

        Args:
            cause_index: Index of cause variable.
            result_index: Index of effect variable.
            node_information: Optional additional information about nodes.
            debating_memory: Optional history of debate exchanges.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.cause_index = cause_index
        self.result_index = result_index
        self.cause_entity = self.labels[self.cause_index]
        self.result_entity = self.labels[self.result_index]

        # Generate dataset description section
        if self.dataset_prompt == "":
            self.dataset_prompt = (
                f"We want to carry out causal inference on {self.theme},"
            )

            if self.dataset_information is not None:
                self.dataset_prompt += f" the summary of dataset: {self.dataset_information}. Considering {', '.join(self.labels)} as variables.\n\n"
            else:
                self.dataset_prompt += (
                    f" considering {', '.join(self.labels)} as variables.\n\n"
                )

        # Generate causal graph description section
        if (
            self.graph_prompt == ""
            and self.graph_matrix is not None
            and self.causal_discovery_algorithm is not None
        ):
            self.graph_prompt = self.generate_graph_prompt()

        if node_information is not None:
            info_prompt = (
                f"In addition, here is the information of {self.cause_entity} and {self.result_entity} from reliable sources.\n"
                f"{node_information[self.cause_entity]}\n\n"
                f"{node_information[self.result_entity]}\n\n"
            )
        else:
            info_prompt = ""

        # Generate debating prompt
        if len(debating_memory) > 0:
            debating_prompt = self.generate_debating_prompt(debating_memory)
        else:
            debating_prompt = ""

        # Generate task description section
        final_prompt_template = (
            f"So, your task is to propose relevant content as much as possible to oppose the causal relationship between {self.cause_entity} and {self.result_entity}. "
            f"Your explanation can be based on the previous content and your own understanding of the relationship between the two."
        )
        # Combine complete prompt
        self.prompt = (
            self.dataset_prompt
            + self.graph_prompt
            + info_prompt
            + debating_prompt
            + final_prompt_template
        )

        self.system_prompt = f"You are an expert in {self.theme} who want to oppose the causal relationship between {self.cause_entity} and {self.result_entity}."
        return self.prompt, self.system_prompt


class ConstrainLLM(LLMs):
    """LLM class for background knowledge verification.

    This class handles verification of background knowledge through LLM interactions.

    Attributes:
        theme: Domain theme.
        domain_knowledge_dict: Dictionary of domain knowledge.
    """

    def __init__(
        self,
        client,
        theme: str,
        domain_knowledge_dict: dict,
    ) -> None:
        """Initializes the ConstrainLLM.

        Args:
            client: The LLM client to use.
            theme: Domain theme.
            domain_knowledge_dict: Dictionary containing domain knowledge.
        """
        super().__init__(client)
        self.theme = theme  # Domain theme
        self.domain_knowledge_dict = (
            domain_knowledge_dict  # Dictionary of domain knowledge
        )

    def generate_prompt(self, causal_entity, result_entity) -> Tuple[str, str]:
        """Generates prompt for background knowledge verification.

        Args:
            causal_entity: The potential cause entity.
            result_entity: The potential effect entity.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.prompt = (
            f"Here is the explanation from an expert in the field of {self.theme} "
            f"regarding the causal relationship between {causal_entity} and {result_entity}:\n"
            f"{self.domain_knowledge_dict[(causal_entity, result_entity)]}"
            f"Considering the information above, if {causal_entity} is modified, will it have a direct impact on {result_entity}?\n"
            f"Please answer this question with <Yes> or <No>.\n"
            f"No answers except these two responses are needed.\n"
            f"Your response should be in the following format:\n"
            f"<Yes> or <No>\n"
            f"Please provide your response in the format specified above.\n"
            f"Your response:\n"
        )
        self.system_prompt = "You are a helpful assistant for causal inference."
        return self.prompt, self.system_prompt

    def downstream_processing(self) -> bool:
        """Processes LLM's response for background knowledge verification.

        Returns:
            1 if direct causal relationship exists, 0 otherwise.

        Raises:
            ValueError: If LLM response is invalid or missing.
        """
        if "Yes" in self.LLM_answer:
            return 1
        elif "No" in self.LLM_answer:
            return 0

        # Used when LLMs can not produce valid response
        # try:
        #     if "Yes" or "yes" in self.LLM_answer:
        #         return 1
        #     elif "No" or "no" in self.LLM_answer:
        #         return 0
        #     else:
        #         return -1
        # except IndexError:
        #     return -1


class ConstrainJudgerLLM(LLMs):
    """LLM class for judging causal relationships based on expert debates.

    This class evaluates causal relationships by analyzing expert debates.
    Used with debate_LLM

    Attributes:
        theme: Domain theme.
        debating_memories: Dictionary of debate histories.
    """

    def __init__(
        self,
        client,
        theme: str,
        debating_memories: dict,
    ) -> None:
        """Initializes the ConstrainJudgerLLM.

        Args:
            client: The LLM client to use.
            theme: Domain theme.
            debating_memories: Dictionary containing debate histories.
        """
        super().__init__(client)
        self.theme = theme  # Domain theme
        self.debating_memories = debating_memories  # Dictionary of debate histories

    def generate_debating_prompt(self, debating_memories: list) -> str:
        """Generates prompt for debate context.

        Args:
            debating_memories: List of previous debate exchanges.

        Returns:
            A string containing the debate context prompt.
        """
        debating_prompt = "Here is the debating memory of the previous round:\n"
        for index, content in enumerate(debating_memories):
            if index % 2 == 0:
                debating_prompt += f"The positive expert says: {content}\n"
            else:
                debating_prompt += f"The negative expert says: {content}\n"
        debating_prompt += "\n"
        return debating_prompt

    def generate_prompt(self, causal_entity, result_entity) -> Tuple[str, str]:
        """Generates prompt for judging causal relationships.

        Args:
            causal_entity: The potential cause entity.
            result_entity: The potential effect entity.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.prompt = (
            f"Here is a debate between two experts on whether {causal_entity} is the reason for {result_entity}. "
            f"One expert holds a supportive attitude, while the other holds an opposing attitude. "
            f"Considering the attitudes of these experts, do you think that the change in {causal_entity} will lead to a change in {result_entity}, "
            f"which means {causal_entity} is the reason for {result_entity}?"
            f"Please use a number between 0 and 1 to indicate the possibility of {causal_entity} being the reason for {result_entity}. "
            f"1 represents {causal_entity} is the cause of {result_entity}, and 0 represents {causal_entity} is not the cause of {result_entity}.\n\n"
            f"Your response should only include a number between 0 and 1."
        )
        self.system_prompt = (
            "You are a helpful assistant in the field of causal discovery, "
            "able to summarize the discussions of different experts and provide your own insights."
        )
        return self.prompt, self.system_prompt

    def downstream_processing(self) -> bool:
        """Processes LLM's response for causal relationship judgment.

        Returns:
            A float between 0 and 1 indicating causality probability.

        Raises:
            ValueError: If LLM response is invalid or missing.
        """
        if self.LLM_answer is None:
            raise ValueError("LLM_answer is None. Please call inquiry() method first.")
        elif 0 <= float(self.LLM_answer) <= 1:
            return float(self.LLM_answer)
        else:
            raise ValueError(f"Invalid response from LLM: {self.LLM_answer}")


class ConstrainReasoningLLM(LLMs):
    """LLM class for background knowledge verification.

    This class handles verification of background knowledge through LLM interactions.

    Attributes:
        theme: Domain theme.
        domain_knowledge_dict: Dictionary of domain knowledge.
    """

    def __init__(
        self,
        client,
        theme: str,
        domain_knowledge_dict: dict,
    ) -> None:
        """Initializes the ConstrainLLM.

        Args:
            client: The LLM client to use.
            theme: Domain theme.
            domain_knowledge_dict: Dictionary containing domain knowledge.
        """
        super().__init__(client)
        self.theme = theme  # Domain theme
        self.domain_knowledge_dict = (
            domain_knowledge_dict  # Dictionary of domain knowledge
        )

    def generate_prompt(
        self, causal_entity, result_entity, guess_number=2
    ) -> Tuple[str, str]:
        """Generates prompt for background knowledge verification.

        Args:
            causal_entity: The potential cause entity.
            result_entity: The potential effect entity.

        Returns:
            A tuple containing (user prompt, system prompt).
        """
        self.prompt = (
            f"Provide your {guess_number} best guesses and the probability that each is correct (0.0 to 1.0) for the following question."
            f"Give ONLY the guesses and probabilities, no other words or explanation. "
            f"Each guess should infer the relationship step by step and finally end with <Yes> or <No>.\n"
            f"For example:\n\n"
            f"G1: <first most likely guess, infer the relationship step by step and finally end with <Yes> or <No>>\n\n"
            f"P1: <the probability between 0.0 and 1.0 that G1 is correct, without any extra comments; just the probability!>\n\n"
            f"---"
            f"G2: <second most likely guess, infer the relationship step by step and finally end with <Yes> or <No>>\n\n"
            f"P2: <the probability between 0.0 and 1.0 that G2 is correct, without any extra comments; just the probability!> \n\n"
            f"---"
            f"The question is:"
            f"Here is the explanation from an expert in the field of {self.theme}"
            f"regarding the causal relationship between {causal_entity} and {result_entity}:\n"
            f"{self.domain_knowledge_dict[(causal_entity, result_entity)]}"
            f"Considering the information above, if {causal_entity} is modified, will it have a direct impact on {result_entity}?\n"
        )

        self.system_prompt = "You are a helpful assistant for causal inference."
        return self.prompt, self.system_prompt

    def downstream_processing(self) -> bool:
        """Processes LLM's response for background knowledge verification.

        Returns:
            1 if direct causal relationship exists, 0 otherwise.

        Raises:
            ValueError: If LLM response is invalid or missing.
        """
        if self.LLM_answer is None:
            raise ValueError("LLM_answer is None. Please call inquiry() method first.")

        # Split answer by "---" and extract guesses and probabilities
        parts = self.LLM_answer.split("---")
        print(parts)
        guess_prob_pairs = []

        for part in parts:
            lines = part.strip().split("\n\n")
            for i in range(len(lines) - 1):
                try:
                    if lines[i].startswith("G") and lines[i + 1].startswith("P"):
                        guess = lines[i].split(": ", 1)[1].strip()
                        prob_str = lines[i + 1].split(": ", 1)[1].strip()
                        prob_str = "".join(
                            c for c in prob_str if c.isdigit() or c == "."
                        )
                        prob = float(prob_str) if prob_str else 0.0
                        guess_prob_pairs.append((prob, guess))
                except Exception:
                    continue
        guess_prob_pairs.sort(reverse=True)

        answer = guess_prob_pairs[0][1]
        if "Yes" in answer:
            return 1
        elif "No" in answer:
            return 0

        # Used when LLMs can not produce valid response
        # try:
        #     answer = guess_prob_pairs[0][1]
        #     if "Yes" or "yes" in answer:
        #         return 1
        #     elif "No" or "no" in answer:
        #         return 0
        #     else:
        #         return -1
        # except IndexError:
        #     return -1
