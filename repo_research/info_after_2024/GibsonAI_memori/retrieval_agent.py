"""
Memory Search Engine - Intelligent memory retrieval using Pydantic models
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import openai
from loguru import logger

from ..utils.pydantic_models import MemorySearchQuery


class MemorySearchEngine:
    """
    Pydantic-based search engine for intelligent memory retrieval.
    Uses OpenAI Structured Outputs to understand queries and plan searches.
    """

    SYSTEM_PROMPT = """You are a Memory Search Agent responsible for understanding user queries and planning effective memory retrieval strategies.

Your primary functions:
1. **Analyze Query Intent**: Understand what the user is actually looking for
2. **Extract Search Parameters**: Identify key entities, topics, and concepts
3. **Plan Search Strategy**: Recommend the best approach to find relevant memories
4. **Filter Recommendations**: Suggest appropriate filters for category, importance, etc.

**MEMORY CATEGORIES AVAILABLE:**
- **fact**: Factual information, definitions, technical details, specific data points
- **preference**: User preferences, likes/dislikes, settings, personal choices, opinions
- **skill**: Skills, abilities, competencies, learning progress, expertise levels
- **context**: Project context, work environment, current situations, background info
- **rule**: Rules, policies, procedures, guidelines, constraints

**SEARCH STRATEGIES:**
- **keyword_search**: Direct keyword/phrase matching in content
- **entity_search**: Search by specific entities (people, technologies, topics)
- **category_filter**: Filter by memory categories
- **importance_filter**: Filter by importance levels
- **temporal_filter**: Search within specific time ranges
- **semantic_search**: Conceptual/meaning-based search

**QUERY INTERPRETATION GUIDELINES:**
- "What did I learn about X?" → Focus on facts and skills related to X
- "My preferences for Y" → Focus on preference category
- "Rules about Z" → Focus on rule category
- "Recent work on A" → Temporal filter + context/skill categories
- "Important information about B" → Importance filter + keyword search

Be strategic and comprehensive in your search planning."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize Memory Search Engine

        Args:
            api_key: OpenAI API key (if None, uses environment variable)
            model: OpenAI model to use for query understanding
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

        # Performance improvements
        self._query_cache = {}  # Cache for search plans
        self._cache_ttl = 300  # 5 minutes cache TTL
        self._cache_lock = threading.Lock()

        # Background processing
        self._background_executor = None

    def plan_search(
        self, query: str, context: Optional[str] = None
    ) -> MemorySearchQuery:
        """
        Plan search strategy for a user query using OpenAI Structured Outputs with caching

        Args:
            query: User's search query
            context: Optional additional context

        Returns:
            Structured search query plan
        """
        try:
            # Create cache key
            cache_key = f"{query}|{context or ''}"

            # Check cache first
            with self._cache_lock:
                if cache_key in self._query_cache:
                    cached_result, timestamp = self._query_cache[cache_key]
                    if time.time() - timestamp < self._cache_ttl:
                        logger.debug(f"Using cached search plan for: {query}")
                        return cached_result

            # Prepare the prompt
            prompt = f"User query: {query}"
            if context:
                prompt += f"\nAdditional context: {context}"

            # Call OpenAI Structured Outputs
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Analyze and plan memory search for this query:\n\n{prompt}",
                    },
                ],
                response_format=MemorySearchQuery,
                temperature=0.1,
            )

            # Handle potential refusal
            if completion.choices[0].message.refusal:
                logger.warning(
                    f"Search planning refused: {completion.choices[0].message.refusal}"
                )
                return self._create_fallback_query(query)

            search_query = completion.choices[0].message.parsed

            # Cache the result
            with self._cache_lock:
                self._query_cache[cache_key] = (search_query, time.time())
                # Clean old cache entries
                self._cleanup_cache()

            logger.debug(
                f"Planned search for query '{query}': intent='{search_query.intent}', strategies={search_query.search_strategy}"
            )
            return search_query

        except Exception as e:
            logger.error(f"Search planning failed: {e}")
            return self._create_fallback_query(query)

    def execute_search(
        self, query: str, db_manager, namespace: str = "default", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Execute intelligent search using planned strategies

        Args:
            query: User's search query
            db_manager: Database manager instance
            namespace: Memory namespace
            limit: Maximum results to return

        Returns:
            List of relevant memory items with search metadata
        """
        try:
            # Plan the search
            search_plan = self.plan_search(query)

            all_results = []
            seen_memory_ids = set()

            # Execute keyword search (primary strategy)
            if (
                search_plan.entity_filters
                or "keyword_search" in search_plan.search_strategy
            ):
                keyword_results = self._execute_keyword_search(
                    search_plan, db_manager, namespace, limit
                )
                for result in keyword_results:
                    if result.get("memory_id") not in seen_memory_ids:
                        seen_memory_ids.add(result["memory_id"])
                        result["search_strategy"] = "keyword_search"
                        result["search_reasoning"] = (
                            f"Keyword match for: {', '.join(search_plan.entity_filters)}"
                        )
                        all_results.append(result)

            # Execute category-based search
            if (
                search_plan.category_filters
                or "category_filter" in search_plan.search_strategy
            ):
                category_results = self._execute_category_search(
                    search_plan, db_manager, namespace, limit - len(all_results)
                )
                for result in category_results:
                    if result.get("memory_id") not in seen_memory_ids:
                        seen_memory_ids.add(result["memory_id"])
                        result["search_strategy"] = "category_filter"
                        result["search_reasoning"] = (
                            f"Category match: {', '.join([c.value for c in search_plan.category_filters])}"
                        )
                        all_results.append(result)

            # Execute importance-based search
            if (
                search_plan.min_importance > 0.0
                or "importance_filter" in search_plan.search_strategy
            ):
                importance_results = self._execute_importance_search(
                    search_plan, db_manager, namespace, limit - len(all_results)
                )
                for result in importance_results:
                    if result.get("memory_id") not in seen_memory_ids:
                        seen_memory_ids.add(result["memory_id"])
                        result["search_strategy"] = "importance_filter"
                        result["search_reasoning"] = (
                            f"High importance (≥{search_plan.min_importance})"
                        )
                        all_results.append(result)

            # If no specific strategies worked, do a general search
            if not all_results:
                general_results = db_manager.search_memories(
                    query=search_plan.query_text, namespace=namespace, limit=limit
                )
                for result in general_results:
                    result["search_strategy"] = "general_search"
                    result["search_reasoning"] = "General content search"
                    all_results.append(result)

            # Sort by relevance (importance score + recency)
            all_results.sort(
                key=lambda x: (
                    x.get("importance_score", 0) * 0.7  # Importance weight
                    + (
                        datetime.now().replace(tzinfo=None)  # Ensure timezone-naive
                        - datetime.fromisoformat(
                            x.get("created_at", "2000-01-01")
                        ).replace(tzinfo=None)
                    ).days
                    * -0.001  # Recency weight
                ),
                reverse=True,
            )

            # Add search metadata
            for result in all_results:
                result["search_metadata"] = {
                    "original_query": query,
                    "interpreted_intent": search_plan.intent,
                    "search_timestamp": datetime.now().isoformat(),
                }

            logger.debug(
                f"Search executed for '{query}': {len(all_results)} results found"
            )
            return all_results[:limit]

        except Exception as e:
            logger.error(f"Search execution failed: {e}")
            return []

    def _execute_keyword_search(
        self, search_plan: MemorySearchQuery, db_manager, namespace: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Execute keyword-based search"""
        keywords = search_plan.entity_filters
        if not keywords:
            # Extract keywords from query text
            keywords = [
                word.strip()
                for word in search_plan.query_text.split()
                if len(word.strip()) > 2
            ]

        search_terms = " ".join(keywords)
        return db_manager.search_memories(
            query=search_terms, namespace=namespace, limit=limit
        )

    def _execute_category_search(
        self, search_plan: MemorySearchQuery, db_manager, namespace: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Execute category-based search"""
        categories = (
            [cat.value for cat in search_plan.category_filters]
            if search_plan.category_filters
            else []
        )

        if not categories:
            return []

        # This would need to be implemented in the database manager
        # For now, get all memories and filter by category
        all_results = db_manager.search_memories(
            query="", namespace=namespace, limit=limit * 3
        )

        filtered_results = []
        for result in all_results:
            # Extract category from processed_data if it's stored as JSON
            try:
                if "processed_data" in result:
                    processed_data = json.loads(result["processed_data"])
                    memory_category = processed_data.get("category", {}).get(
                        "primary_category", ""
                    )
                    if memory_category in categories:
                        filtered_results.append(result)
                elif result.get("category") in categories:
                    filtered_results.append(result)
            except (json.JSONDecodeError, KeyError):
                continue

        return filtered_results[:limit]

    def _execute_importance_search(
        self, search_plan: MemorySearchQuery, db_manager, namespace: str, limit: int
    ) -> List[Dict[str, Any]]:
        """Execute importance-based search"""
        min_importance = max(
            search_plan.min_importance, 0.7
        )  # Default to high importance

        all_results = db_manager.search_memories(
            query="", namespace=namespace, limit=limit * 2
        )

        high_importance_results = [
            result
            for result in all_results
            if result.get("importance_score", 0) >= min_importance
        ]

        return high_importance_results[:limit]

    def _create_fallback_query(self, query: str) -> MemorySearchQuery:
        """Create a fallback search query for error cases"""
        return MemorySearchQuery(
            query_text=query,
            intent="General search (fallback)",
            entity_filters=[word for word in query.split() if len(word) > 2],
            search_strategy=["keyword_search", "general_search"],
            expected_result_types=["any"],
        )

    def _cleanup_cache(self):
        """Clean up expired cache entries"""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._query_cache.items()
            if current_time - timestamp >= self._cache_ttl
        ]
        for key in expired_keys:
            del self._query_cache[key]

    async def execute_search_async(
        self, query: str, db_manager, namespace: str = "default", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Async version of execute_search for better performance in background processing
        """
        try:
            # Run search planning in background if needed
            loop = asyncio.get_event_loop()
            search_plan = await loop.run_in_executor(
                self._background_executor, self.plan_search, query
            )

            # Execute searches concurrently
            search_tasks = []

            # Keyword search task
            if (
                search_plan.entity_filters
                or "keyword_search" in search_plan.search_strategy
            ):
                search_tasks.append(
                    loop.run_in_executor(
                        self._background_executor,
                        self._execute_keyword_search,
                        search_plan,
                        db_manager,
                        namespace,
                        limit,
                    )
                )

            # Category search task
            if (
                search_plan.category_filters
                or "category_filter" in search_plan.search_strategy
            ):
                search_tasks.append(
                    loop.run_in_executor(
                        self._background_executor,
                        self._execute_category_search,
                        search_plan,
                        db_manager,
                        namespace,
                        limit,
                    )
                )

            # Execute all searches concurrently
            if search_tasks:
                results_lists = await asyncio.gather(
                    *search_tasks, return_exceptions=True
                )

                all_results = []
                seen_memory_ids = set()

                for i, results in enumerate(results_lists):
                    if isinstance(results, Exception):
                        logger.warning(f"Search task {i} failed: {results}")
                        continue

                    for result in results:
                        if result.get("memory_id") not in seen_memory_ids:
                            seen_memory_ids.add(result["memory_id"])
                            all_results.append(result)

                return all_results[:limit]

            # Fallback to sync execution
            return self.execute_search(query, db_manager, namespace, limit)

        except Exception as e:
            logger.error(f"Async search execution failed: {e}")
            return []

    def execute_search_background(
        self,
        query: str,
        db_manager,
        namespace: str = "default",
        limit: int = 10,
        callback=None,
    ):
        """
        Execute search in background thread for non-blocking operation

        Args:
            query: Search query
            db_manager: Database manager
            namespace: Memory namespace
            limit: Max results
            callback: Optional callback function to handle results
        """

        def _background_search():
            try:
                results = self.execute_search(query, db_manager, namespace, limit)
                if callback:
                    callback(results)
                return results
            except Exception as e:
                logger.error(f"Background search failed: {e}")
                if callback:
                    callback([])
                return []

        # Start background thread
        thread = threading.Thread(target=_background_search, daemon=True)
        thread.start()
        return thread

    def search_memories(
        self, query: str, max_results: int = 5, namespace: str = "default"
    ) -> List[Dict[str, Any]]:
        """
        Simple search interface for compatibility with memory tools

        Args:
            query: Search query
            max_results: Maximum number of results
            namespace: Memory namespace

        Returns:
            List of memory search results
        """
        # This is a compatibility method that uses the database manager directly
        # We'll need the database manager to be injected or passed
        # For now, return empty list and log the issue
        logger.warning(f"search_memories called without database manager: {query}")
        return []


def create_retrieval_agent(
    memori_instance=None, api_key: str = None, model: str = "gpt-4o"
) -> MemorySearchEngine:
    """
    Create a retrieval agent instance

    Args:
        memori_instance: Optional Memori instance for direct database access
        api_key: OpenAI API key
        model: Model to use for query planning

    Returns:
        MemorySearchEngine instance
    """
    agent = MemorySearchEngine(api_key=api_key, model=model)
    if memori_instance:
        agent._memori_instance = memori_instance
    return agent


def smart_memory_search(query: str, memori_instance, limit: int = 5) -> str:
    """
    Direct string-based memory search function that uses intelligent retrieval

    Args:
        query: Search query string
        memori_instance: Memori instance with database access
        limit: Maximum number of results

    Returns:
        Formatted string with search results
    """
    try:
        # Create search engine
        search_engine = MemorySearchEngine()

        # Execute intelligent search
        results = search_engine.execute_search(
            query=query,
            db_manager=memori_instance.db_manager,
            namespace=memori_instance.namespace,
            limit=limit,
        )

        if not results:
            return f"No relevant memories found for query: '{query}'"

        # Format results as a readable string
        output = f"🔍 Smart Memory Search Results for: '{query}'\n\n"

        for i, result in enumerate(results, 1):
            try:
                # Try to parse processed data for better formatting
                if "processed_data" in result:
                    import json

                    processed_data = json.loads(result["processed_data"])
                    summary = processed_data.get("summary", "")
                    category = processed_data.get("category", {}).get(
                        "primary_category", ""
                    )
                else:
                    summary = result.get(
                        "summary", result.get("searchable_content", "")[:100] + "..."
                    )
                    category = result.get("category_primary", "unknown")

                importance = result.get("importance_score", 0.0)
                created_at = result.get("created_at", "")
                search_strategy = result.get("search_strategy", "unknown")
                search_reasoning = result.get("search_reasoning", "")

                output += f"{i}. [{category.upper()}] {summary}\n"
                output += f"   📊 Importance: {importance:.2f} | 📅 {created_at}\n"
                output += f"   🔍 Strategy: {search_strategy}\n"

                if search_reasoning:
                    output += f"   🎯 {search_reasoning}\n"

                output += "\n"

            except Exception:
                # Fallback formatting
                content = result.get("searchable_content", "Memory content available")[
                    :100
                ]
                output += f"{i}. {content}...\n\n"

        return output.strip()

    except Exception as e:
        logger.error(f"Smart memory search failed: {e}")
        return f"Error in smart memory search: {str(e)}"
