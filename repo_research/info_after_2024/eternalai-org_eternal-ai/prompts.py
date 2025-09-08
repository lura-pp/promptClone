JUDGE_GAME_PROMPT_TEMPLATE = """Act as an expert in evaluating and judging the quality of AI-generated responses to tweets.

Your task is to objectively evaluate multiple AI agents' responses to a tweet based on the following criteria:

1. Accuracy and Relevance: Assess how accurately and appropriately each response addresses the content of the tweet.
2. Clarity and Coherence: Determine how well-structured and easy to understand each response is.
3. Adherence to Constraints: Take into account whether each response follows any specific rules or constraints mentioned in the tweet.

List your thoughts for each response before making a final decision. If complex reasoning is required, think step by step and weigh all sides of the topic before settling on the best response. Utilize advanced prompt engineering techniques such as Chain of Thought, Debate simulations, Self Reflection, and Self Consistency where appropriate.

After evaluating all responses, identify the agent with the best response. If multiple agents provide the best response, the winning agent is the one with the earliest best response.

Response format:
Please provide your response as a stringified JSON object with the key "winning_agent" containing the username of the agent with the best response, and the key "result_found" whose value is always true.

Example output:
{{ 
  "winning_agent": "Agent's username",
  "result_found": true
}}

Here are the information of the given tweet:
- Tweet text: {full_text}
- Content images in the tweet: {content_images}

Here are the list of responses that need to be evaluated, sorted from the earliest to the latest:
{answers_content}
"""

JUDGE_FACT_PROMPT_TEMPLATE = """Act as an expert in evaluating and judging the quality of AI-generated responses to tweets.

Your task is to objectively evaluate multiple AI agents' responses to a tweet based on the following criteria:

1. Accuracy and Relevance: Assess how accurately and appropriately each response addresses the content of the tweet.
2. Creativity and Originality: Evaluate the degree of innovation and uniqueness demonstrated in each response.
3. Adherence to Constraints: Take into account whether each response follows any specific rules or constraints mentioned in the tweet.

List your thoughts for each response before making a final decision. If complex reasoning is required, think step by step and weigh all sides of the topic before settling on the best response. Utilize advanced prompt engineering techniques such as Chain of Thought, Debate simulations, Self Reflection, and Self Consistency where appropriate.

After evaluating all responses, identify the agent with the best response. If multiple agents provide the best response, the winning agent is the one with the earliest best response.

Response format:
Please provide your response as a stringified JSON object with the key "winning_agent" containing the username of the agent with the best response.

Example output:
{{ "winning_agent": "Agent's username" }}

Here are the information of the given tweet:
- Tweet text: {full_text}
- Content images in the tweet: {content_images}

Here are the list of responses that need to be evaluated, sorted from the earliest to the latest:
{answers_content}
"""

FACT_QUERY_PROMPT_TEMPLATE = """Act as an expert in information retrieval and search query optimization with deep knowledge of fact-checking methodologies, search engine algorithms, and unbiased data sourcing. Your task is to generate a precise, effective search query that retrieves factual, objective, and up-to-date information to be used as an external reference for judging answers in a QA game scenario.

## Task:
You will be provided with a QA game scenario that includes:
- A question related to a specific topic.
- A timestamp indicating when the QA game started.
- Optionally, a list of image descriptions that might offer further context.

Your task is to craft an optimized, natural language search query that:
- Retrieves concrete, authoritative information used for judging.
- Maximizes relevance for judging the given question while incorporating pertinent details from the image descriptions.
- Remains neutral and unbiased, avoiding assumptions, opinions, or misleading phrasing.
- If the question asks for a prediction about a future event, ensure the search query is structured to find results that confirm the actual outcome of the event.
- If the question can be answered without external information, returns an empty query string (i.e., "").

## Context:
- The query should be designed for search engines similar to Tavily, focusing on verifiable facts.
- If the topic is time-sensitive, adjust the phrasing to include the relevant timestamp (e.g., “as of <timestamp>”).
- If the question involves an event that had an uncertain outcome at the time of the QA game start, reframe the query to seek results that confirm the actual outcome after the event has occurred.
- Integrate details from image descriptions only if they are directly relevant (e.g., locations, objects, text).
- Avoid special search operators (e.g., site:, intitle:) or advanced syntax; use only natural text.
- Ensure clarity, conciseness, and neutrality.

## Response Format:

Return your answer strictly as a JSON object in the following format:

{{
  "query": "<generated search query>"
}}

Where <search query> is the final optimized search query, or an empty string if no external search is required.

## Thought Process Before Answering:

Before providing your final answer, list your detailed chain-of-thought step by step. Your reasoning should include:
- Analyzing the main focus of the question (who, what, when, where, why, how).
- Determining if the question involves a future event that would have had an uncertain outcome at the time of the QA game.
  - If so, modify the search to look for post-event results rather than pre-event predictions.
- Evaluating the image descriptions to extract any useful details.
- Considering the QA game start timestamp to ensure the query is time-appropriate.
- Simulating a debate between different potential query structures, weighing their pros and cons.
- Using self-reflection to check that the query is as clear, concise, neutral, and authoritative as possible.

## Provided Input Data

Question: {question}

QA Game Start Timestamp: {tweet_timestamp}

Current Timestamp: {current_timestamp}

{content_images}

## Final Instructions:
- Think carefully and list your thoughts step by step before arriving at your final query.
- Utilize advanced reasoning techniques such as chain-of-thought, debate simulation, and self-reflection.
- Ensure the final answer strictly adheres to the JSON response format provided.

Now, please generate the optimized search query based on the provided input data.
"""

JUDGE_GAME_WITH_FACTS_PROMPT_TEMPLATE = """**Act as an expert in evaluating and judging the quality of AI-generated responses to tweets.**  

## Task  

Your task is to objectively evaluate multiple AI agents' responses to a tweet based on the following criteria:  

1. **Accuracy and Relevance:** Assess how accurately and appropriately each response addresses the content of the tweet.
2. **Clarity and Coherence:** Determine how well-structured and easy to understand each response is.
3. **Adherence to Constraints:** Take into account whether each response follows any specific rules or constraints mentioned in the tweet.

## Additional Consideration: Future Event Dependency  

- You will be provided with a list of facts related to the tweet.
- The timestamp of the tweet and the current timestamp will also be given. Use this to determine whether the question in the tweet refers to a future event that may not have occurred yet at the time of evaluation.
- If the question in the tweet requires results from a future event to answer, and that future event has not yet occurred based on the given facts, set "result_found" to "false".
- Additionally, set "result_found" to "false" if the result of the future event is not 100% certain based on the given facts.
- Otherwise, set "result_found" to "true".

## Evaluation Process  

1. **Analyze Each Response:** List your thoughts for each response before making a final decision.
2. **Step-by-Step Reasoning:** If complex reasoning is required, break it down step by step and weigh all sides of the topic before settling on the best response.
3. **Consider the Tweet Timestamp and Current Timestamp**: Ensure your evaluation accounts for whether the response is valid based on the time the tweet was posted and the current time.
4. **Advanced Prompting Techniques:** Utilize techniques such as Chain of Thought, Debate Simulations, Self-Reflection, and Self-Consistency to enhance your evaluation.
5. **Determine the Best Response:** Identify the agent with the best response based on the above criteria.
6. **Handling Irrelevant Responses:** If none of the responses are relevant to the question in the tweet, declare the agent with the earliest response as the winner.
7. **Tiebreaker Rule:** If multiple agents provide the best response, select the earliest one.

## Response Format  

First, output your evaluation process. Then, provide your response as a JSON object with the following structure:

{{
  "winning_agent": "Agent's username",
  "result_found": true/false
}}

## Example Output

<Your evaluating process>

{{
  "winning_agent": "Agent123",
  "result_found": false
}}

## Provided Data

Tweet text: {full_text}

Tweet timestamp: {tweet_timestamp}

Current timestamp: {current_timestamp}

{content_images}

List of given facts:
{given_facts}

Responses to evaluate (sorted from earliest to latest):
{answers_content}
"""
