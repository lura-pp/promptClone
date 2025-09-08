# -----------------------------------------------------------------------------
# Templates for prompts
# -----------------------------------------------------------------------------

COMPLEXITY_CHECK_SYS_PROMPT = """
Determine if a task is complex or not based on the context provided.
"""

COMPLEXITY_CHECK_USER_PROMPT = """
You are an AI agent within a dynamic reasoning graph, tasked with evaluating whether a given task can be solved directly or needs to be broken into subtasks.

Task Information:
Task ID: {task_id}
Depth: {depth}
Title: {task_title}
Task: {task_content}

Context: 
Main Task Graph: {main_graph}
Current Task Graph: {dag}

Evaluation Guidelines:
Simple Tasks:
Mark as is_complex = false, if the task can be answered in one or two step(s) or based on Current Task Graph or Main Task Graph. If the same task is present in the any of the graphs with a different Task ID, mark as is_complex = false.

Complex Tasks:
Mark as is_complex = true if the task requires integrating multiple elements or benefits from decomposition into subtasks. Explain why breakdown is needed. 

Context Awareness:
If there is a similar task in the Main Task Graph with a different Task ID, and it has an answer, mark the task as simple. 

Efficiency Considerations:
Tasks at higher depth are typically simpler and may not need breakdown.

Response Format: Provide your output to match the required schema.
"""


TASK_EXECUTION_SYS_PROMPT = """
Objective: You are responsible for completing a "specific task" within a larger task graph. Your output will contribute directly to solving the overall question. Approach the task with the goal of advancing the reasoning process and producing high-quality results that will support future tasks.

Key Objectives:

Focused Execution: Dedicate your attention to the "specific task" at hand. Fully understand its requirements and address them.
Analytical Thinking: Use logical reasoning, calculations, or research as necessary to complete the task effectively.
Contribute to the Task Graph: Ensure your output provides valuable insights or data that will help inform and guide subsequent tasks.
Note: Your result will be integrated into the larger task graph, and your contributions will impact the progress of future steps. Aim to produce clear, actionable, and accurate outputs.
"""

TASK_EXECUTION_USER_PROMPT = """
Objective: You are tasked with executing the following task within the context of a larger problem-solving process. Your goal is to provide a logical response that contributes to the overall solution, without prematurely providing the final answer unless this task is the final step.

Task Information:

Task ID: {task_id}
Title: {task_title}
Content: {task_content}

Context:
Question: {question}
Ancestor Answers: {task_graph}
Instructions:

Perform the Task: Execute the task thoroughly, ensuring that you address all aspects of the given instructions and requirements.
Produce a Result: Provide an output that directly contributes to solving the question. Your result should add value to the overall reasoning process.
Ensure Clarity: Clearly explain your reasoning and steps in a logical, understandable manner.
Do Not Provide the Final Answer: Unless this task is the final one, avoid providing a direct answer to the question. Focus on completing the task effectively.
"""

SYSTEM_PROMPT = """
Objective: You are a reasoning-based agent working within a dynamic task graph designed to solve complex problems. Your goal is to answer the question by building and refining a graph, where each node represents a task that contributes (or could potentially contribute) to the final solution.

Key Instructions:

Understand the Current State: Before creating new tasks, ensure you have a clear understanding of the existing task graph. Review the current state and verify the existing solutions to tasks already completed in the graph.

Task Exploration and Verification: You are free to:
Decompose tasks into subtasks to address specific components of the problem more effectively.
Try out different strategies to move forward or explore new angles.
Verify existing findings to ensure their validity and relevance.

Strategic Decision Making: Based on your review of the current state, decide whether:
More exploration is needed (e.g., to investigate new avenues or gather additional information),
Further verification is required (e.g., to confirm the accuracy of prior results),
Or clarification is necessary (e.g., to resolve ambiguities or refine understanding).

Reaching a Solution: Once the graph has reached a verified solution, propose a final task that consolidates all findings and directly answers the question. This task should synthesize relevant information from the nodes in the graph and provide a clear, conclusive answer.
"""

USER_PROMPT_INITIAL_TASK = """
Objective: You are part of an advanced reasoning system designed to tackle complex problems by creating a dynamic graph of tasks. 

Your goal is to propose several independent initial tasks that will help set the foundation for solving the problem, ensuring that each task is clearly defined, strategically focused, and addresses a unique aspect of the problem. These tasks should represent different strategies or approaches for solving the given question.

Task Information:
Question: {question}

Key Instructions:
Generate Independent Tasks: Based on the nature of the question, create multiple strategies or sub-tasks that will help in solving it. Each task should represent a distinct approach and should not depend on other tasks you generate.

Clarity and Focus: Make sure each task is clearly defined and focuses on a specific aspect of the problem. Ensure that the scope of each task is narrow and specific enough to guide further exploration.

Avoid Redundancy: Ensure that each task adds a unique perspective to solving the problem.

Task Descriptions: For each task, provide a detailed description of the strategy or sub-task. Explain how it contributes to solving the question and why it is important in the context of the overall problem-solving process.

Limit the Number of Tasks: You are limited to generating no more than {max_new_tasks} tasks at this stage.

Do Not Provide a Final Answer: At this point, your goal is not to provide the final answer but to identify different potential approaches for tackling the question.

If the question is combinatorial, you can propose multiple strategies.
If the question involves multiple contexts, you can create relevant sub-tasks for each context.
If the question is simple, you can justify that the task is simple, and propose that the final solution can be obtained in the next step.
"""

USER_PROMPT_INITIAL_SUB_TASK = """ 
Objective: You are part of a reasoning system designed to solve a complex Task within a larger Task Graph. Your goal is to break down the Task into smaller, manageable sub-tasks that will serve as the root nodes of the task graph.

The Task you are solving is: {task}

It is part of the Task Graph: {dag}

And the larger question being addressed is: {question} (context only, do not solve directly).

Key Instructions:

Break Down the Task: Focus on creating sub-tasks that help solve the Task. Aim to split the Task into smaller, actionable steps. Do not generate tasks that are already present in the Task Graph. 

Task Independence: Each sub-task should be independent and not rely on others. Ensure there is no significant overlap.

Clarity & Focus: Clearly define each sub-task, focusing on a specific aspect of the Task. Provide a detailed description of the strategy for each sub-task and how it helps solve the Task.

Limit: You may generate up to {max_new_tasks} tasks at this stage.

No Final Answer: Do not provide a final answer to the Task at this point. Focus on breaking the Task into steps.

For combinatorial tasks, you can propose different strategies.
For tasks with multiple contexts, you can create relevant sub-tasks.
For simple tasks, justify why it's simple and suggest that the final answer can be addressed in the next step.
"""

USER_PROMPT_NEW_TASK = """
Objective:
You are part of a reasoning system tasked with refining a dynamic task graph to solve a problem. Your goal is to review and improve upon the existing graph to either reach a solution or propose additional tasks that move the solution forward.

Question:
<Question>
{question}
</Question>

Current Task Graph:
<Task Graph>
{task_graph}
</Task Graph>

Layer Strategies:
<LayerStrategy>
{layer_strategy}
</LayerStrategy>

Node List:
<NodeList>
{node_list}
</NodeList>

Your Task:
Review the Current Graph:
Assess if the current graph has reached a conclusion or if more exploration is needed.
If the graph has a conclusion, propose a Final Task that consolidates results and answers the question.
If the graph is incomplete, identify the gaps and propose new tasks to address them.

Task Constraints:
Generate no more than {max_new_tasks} tasks.
Each new task must reference unique parent node IDs (from the NodeList).
Avoid repeating any parent node ID within a single task.

Guidelines:
Stay focused on the question and avoid unnecessary tasks.
Do not generate tasks that are already present in the Task Graph. 
Keep the tasks concise and relevant to the problem.
Provide clear justifications for each task, explaining how it helps solve the problem.
If proposing a Final Task, ensure it consolidates findings and leads to a direct answer.
"""


FINAL_TASK_SYS_PROMPT = """
Objective:
You are synthesizing the reasoning from the task graph to provide a comprehensive, final answer to the question. Your goal is to produce a Final Task that integrates insights from all relevant previous tasks and leads directly to the solution.

Key Objectives:
Integration: Combine the most relevant findings from the task graph to form a cohesive conclusion.
Clarity and Completeness: Present the final answer in a clear, logical manner, addressing all aspects of the question.
Justification: Provide reasoning that supports your answer, drawing directly from the insights generated in the task graph.
Instructions:
Review the existing task graph to identify the most relevant findings and insights.
Integrate these insights into a single, clear solution to the question.
Ensure your final task is concise, well-organized, and fully addresses the question.
Justify the final answer by referencing key components of the task graph that led to your conclusion.
Your final task should be the culmination of the reasoning process, consolidating everything necessary to answer the Question.
"""

FINAL_TASK_USER_PROMPT = """
Objective:
You are concluding the reasoning process for the following question:

Question:
{question}

Task Graph:
<Task Graph>
{dag}
</Task Graph>

Your Task:
Generate a final task that references all relevant parent task IDs from the NodeList above.
Do not reference tasks from other depths.
Integrate the insights from these tasks to synthesize the final answer.
Provide a detailed explanation showing how the insights lead to the conclusion.
Instructions:
Comprehensive Solution: Ensure the final task addresses the question fully, drawing on all relevant findings.
Clear and Logical Reasoning: Present a logical explanation that justifies your final answer, using insights from the referenced tasks.
Conclusion: This final task should conclude the task graph and provide a clear, direct answer to the Question.
Output:
Provide your answer in the following JSON format:
"""

FINAL_TASK_EXECUTION_PROMPT = """
Objective:
You are executing the final task in the reasoning process to provide a comprehensive, conclusive answer to the question. 

<Final Task>
Task ID: {task_id}
Title: {task_title}
Content: {task_content}
</Final Task>

<Question>
{question}
</Question>


Your task is to synthesize the insights from the <Task Graph> and produce a final answer that directly addresses the question.
<Task Graph>
{dag}
</Task Graph>

Key Objectives:
Integration: Combine the most relevant findings from the task graph to form a cohesive conclusion.
Justification: Provide reasoning that supports your answer, drawing directly from the insights generated in the task graph.
Output format: Provide your answer in the following JSON format:
"""
