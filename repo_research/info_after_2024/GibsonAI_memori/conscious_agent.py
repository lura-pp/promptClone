"""
Conscious Agent for Background Memory Processing

This agent analyzes long-term memory patterns to extract essential personal facts
and promote them to short-term memory for immediate context injection.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel, Field


class EssentialMemory(BaseModel):
    """Essential conversation memory identified for short-term storage"""

    memory_id: str = Field(description="Original memory ID from long-term storage")
    summary: str = Field(description="Summary of the conversation")
    category: str = Field(description="Memory category")
    importance_score: float = Field(ge=0.0, le=1.0, description="Importance score")
    frequency_score: float = Field(
        ge=0.0, le=1.0, description="How frequently this is referenced"
    )
    recency_score: float = Field(
        ge=0.0, le=1.0, description="How recent this information is"
    )
    relevance_reasoning: str = Field(description="Why this memory is essential")


class EssentialMemoriesAnalysis(BaseModel):
    """Analysis result containing essential memories to promote to short-term"""

    essential_memories: List[EssentialMemory] = Field(
        default_factory=list,
        description="Conversations that should be promoted to short-term memory",
    )
    analysis_reasoning: str = Field(
        description="Overall reasoning for memory selection"
    )
    total_analyzed: int = Field(description="Total memories analyzed")
    promoted_count: int = Field(
        description="Number of memories recommended for promotion"
    )


class ConsciouscAgent:
    """
    Background agent that analyzes long-term memory to extract essential personal facts.

    This agent mimics the conscious mind's ability to keep essential information
    readily accessible in short-term memory.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the conscious agent

        Args:
            api_key: OpenAI API key (if None, uses environment variable)
            model: OpenAI model to use for analysis (gpt-4o recommended)
        """
        self.api_key = api_key
        self.model = model

        # Check if API key is available (either provided or in environment)
        effective_api_key = api_key or os.getenv("OPENAI_API_KEY")

        if effective_api_key:
            self.client = AsyncOpenAI(
                api_key=api_key
            )  # AsyncOpenAI handles None api_key automatically
        else:
            self.client = None
            logger.warning(
                "ConsciouscAgent: No OpenAI API key found. Set OPENAI_API_KEY environment variable or provide api_key parameter."
            )

        self.last_analysis = None
        self.analysis_interval = timedelta(hours=6)  # Analyze every 6 hours

        # System prompt for memory selection
        self.system_prompt = """You are a Conscious Agent responsible for selecting essential conversations from long-term memory to promote to short-term memory.

Your role is to identify the most important conversations that should be readily available for immediate context injection.

SELECTION CRITERIA:

1. PERSONAL IDENTITY: Conversations where the user shares their name, occupation, location, or basic info
2. PREFERENCES & HABITS: Conversations revealing likes, dislikes, routines, sleep schedule, work patterns
3. SKILLS & EXPERTISE: Conversations about their technical skills, programming languages, tools they use
4. CURRENT PROJECTS: Conversations about ongoing work, projects, or learning goals
5. RELATIONSHIPS: Conversations mentioning important people, colleagues, or connections
6. REPEATED REFERENCES: Conversations that get referenced or built upon in later discussions

SCORING GUIDELINES:
- **Frequency Score**: How often this information is referenced or mentioned again
- **Recency Score**: How recent and relevant this information remains
- **Importance Score**: How critical this information is for understanding the person

SELECT conversations that:
- Contain foundational information about the person (name, role, preferences)
- Are frequently referenced or built upon in later conversations
- Provide essential context for understanding future conversations
- Represent stable, long-term characteristics rather than temporary states

AVOID conversations that:
- Are purely transactional or generic
- Contain outdated or superseded information
- Are highly specific to a single context that hasn't been revisited"""

    async def analyze_memory_patterns(
        self, db_manager, namespace: str = "default", min_memories: int = 10
    ) -> Optional[EssentialMemoriesAnalysis]:
        """
        Analyze long-term memory patterns to select essential conversations

        Args:
            db_manager: Database manager instance
            namespace: Memory namespace to analyze
            min_memories: Minimum number of memories needed for analysis

        Returns:
            EssentialMemoriesAnalysis with selected conversations or None if insufficient data
        """
        if not self.client:
            logger.debug("ConsciouscAgent: No API client available, skipping analysis")
            return None

        try:
            # Get all long-term memories for analysis
            memories = await self._get_long_term_memories(db_manager, namespace)

            if len(memories) < min_memories:
                logger.info(
                    f"ConsciouscAgent: Insufficient memories ({len(memories)}) for analysis"
                )
                return None

            # Prepare memory data for analysis
            memory_summaries = []
            for memory in memories:
                try:
                    processed_data = json.loads(memory.get("processed_data", "{}"))
                    memory_summaries.append(
                        {
                            "memory_id": memory.get("memory_id", ""),
                            "summary": memory.get("summary", ""),
                            "category": memory.get("category_primary", ""),
                            "created_at": memory.get("created_at", ""),
                            "entities": processed_data.get("entities", {}),
                            "importance": memory.get("importance_score", 0.0),
                            "access_count": memory.get("access_count", 0),
                        }
                    )
                except json.JSONDecodeError:
                    continue

            if not memory_summaries:
                logger.warning("ConsciouscAgent: No valid memories found for analysis")
                return None

            # Perform AI analysis to select essential conversations
            analysis = await self._perform_memory_selection(memory_summaries)

            if analysis:
                self.last_analysis = datetime.now()
                logger.info(
                    f"ConsciouscAgent: Selected {len(analysis.essential_memories)} essential conversations"
                )

            return analysis

        except Exception as e:
            logger.error(f"ConsciouscAgent: Memory analysis failed: {e}")
            return None

    async def _get_long_term_memories(
        self, db_manager, namespace: str
    ) -> List[Dict[str, Any]]:
        """Get long-term memories for analysis"""
        try:
            # Get memories from the last 30 days for pattern analysis
            cutoff_date = datetime.now() - timedelta(days=30)

            query = """
            SELECT memory_id, summary, category_primary, processed_data,
                   importance_score, created_at, access_count
            FROM long_term_memory
            WHERE namespace = ? AND created_at >= ?
            ORDER BY importance_score DESC, access_count DESC
            LIMIT 100
            """

            # Execute query through database manager
            with db_manager._get_connection() as connection:
                cursor = connection.execute(query, (namespace, cutoff_date.isoformat()))

                memories = []
                for row in cursor.fetchall():
                    memories.append(
                        {
                            "memory_id": row[0],
                            "summary": row[1],
                            "category_primary": row[2],
                            "processed_data": row[3],
                            "importance_score": row[4],
                            "created_at": row[5],
                            "access_count": row[6],
                        }
                    )

                return memories

        except Exception as e:
            logger.error(f"ConsciouscAgent: Failed to get long-term memories: {e}")
            return []

    async def _perform_memory_selection(
        self, memory_summaries: List[Dict]
    ) -> Optional[EssentialMemoriesAnalysis]:
        """Use AI to select essential conversations from memory patterns"""
        try:
            # Prepare context for AI analysis
            memory_context = self._prepare_memory_context(memory_summaries)

            # Create the analysis prompt
            user_prompt = f"""Analyze the following conversations from long-term memory and select the most essential ones to promote to short-term memory:

AVAILABLE CONVERSATIONS:
{memory_context}

Select conversations that should be promoted to short-term memory for immediate context. Focus on conversations that:
1. Contain foundational personal information (name, occupation, preferences)
2. Are frequently referenced or built upon in later conversations
3. Provide essential context for understanding the person
4. Represent stable, long-term characteristics

For each selected conversation, provide:
- The memory_id
- Frequency score (how often this info is referenced)
- Recency score (how current/relevant this remains)
- Importance score (how critical for understanding the person)
- Clear reasoning for why this conversation is essential

Limit selection to the top 5-10 most essential conversations."""

            # Make API call with structured output
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=EssentialMemoriesAnalysis,
                temperature=0.1,
            )

            analysis = response.choices[0].message.parsed
            return analysis

        except Exception as e:
            logger.error(f"ConsciouscAgent: Memory selection failed: {e}")
            return None

    def _prepare_memory_context(self, memory_summaries: List[Dict]) -> str:
        """Prepare memory data for AI analysis"""
        context_lines = []

        for i, memory in enumerate(
            memory_summaries[:50], 1
        ):  # Limit to 50 most important
            line = f"{i}. ID: {memory['memory_id']} | [{memory['category']}] {memory['summary']}"
            line += f" | Importance: {memory['importance']:.2f} | Access: {memory.get('access_count', 0)}"

            if memory.get("entities"):
                entities = []
                for _entity_type, values in memory["entities"].items():
                    if values and isinstance(values, list):
                        # Handle both string entities and structured entities
                        for value in values:
                            if isinstance(value, str):
                                entities.append(value)
                            elif isinstance(value, dict) and "value" in value:
                                # Handle structured entities
                                entities.append(value["value"])
                            elif hasattr(value, "value"):
                                # Handle Pydantic model entities
                                entities.append(value.value)
                            else:
                                # Convert any other type to string
                                entities.append(str(value))

                if entities:
                    line += f" | Entities: {', '.join(entities[:5])}"

            context_lines.append(line)

        return "\n".join(context_lines)

    async def update_short_term_memories(
        self,
        db_manager,
        analysis: EssentialMemoriesAnalysis,
        namespace: str = "default",
    ) -> int:
        """
        Update short-term memory with selected essential conversations

        Args:
            db_manager: Database manager instance
            analysis: Analysis containing selected essential memories
            namespace: Memory namespace

        Returns:
            Number of conversations copied to short-term memory
        """
        try:
            updated_count = 0

            # Clear existing essential conversations from short-term memory
            await self._clear_essential_conversations(db_manager, namespace)

            # Copy each essential conversation to short-term memory
            for essential_memory in analysis.essential_memories:
                success = await self._copy_conversation_to_short_term(
                    db_manager, essential_memory, namespace
                )
                if success:
                    updated_count += 1

            logger.info(
                f"ConsciouscAgent: Copied {updated_count} essential conversations to short-term memory"
            )
            return updated_count

        except Exception as e:
            logger.error(f"ConsciouscAgent: Failed to update short-term memories: {e}")
            return 0

    async def _clear_essential_conversations(self, db_manager, namespace: str):
        """Clear existing essential conversations from short-term memory"""
        try:
            with db_manager._get_connection() as connection:
                # Delete conversations marked as essential
                query = """
                DELETE FROM short_term_memory
                WHERE namespace = ? AND category_primary LIKE 'essential_%'
                """

                connection.execute(query, (namespace,))
                connection.commit()

        except Exception as e:
            logger.error(
                f"ConsciouscAgent: Failed to clear essential conversations: {e}"
            )

    async def _copy_conversation_to_short_term(
        self, db_manager, essential_memory: EssentialMemory, namespace: str
    ) -> bool:
        """Copy an essential conversation from long-term to short-term memory"""
        try:
            # First, get the original conversation from long-term memory
            original_memory = await self._get_original_memory(
                db_manager, essential_memory.memory_id
            )

            if not original_memory:
                logger.warning(
                    f"ConsciouscAgent: Could not find original memory {essential_memory.memory_id}"
                )
                return False

            # Create new memory ID for short-term storage
            new_memory_id = str(uuid.uuid4())
            now = datetime.now()

            # Create enhanced processed data
            try:
                original_processed_data = json.loads(
                    original_memory.get("processed_data", "{}")
                )
            except json.JSONDecodeError:
                original_processed_data = {}

            enhanced_processed_data = original_processed_data.copy()
            enhanced_processed_data.update(
                {
                    "promoted_by": "conscious_agent",
                    "promoted_at": now.isoformat(),
                    "original_memory_id": essential_memory.memory_id,
                    "frequency_score": essential_memory.frequency_score,
                    "recency_score": essential_memory.recency_score,
                    "promotion_reasoning": essential_memory.relevance_reasoning,
                }
            )

            # Store in short-term memory
            with db_manager._get_connection() as connection:
                query = """
                INSERT INTO short_term_memory (
                    memory_id, chat_id, processed_data, importance_score,
                    category_primary, retention_type, namespace, created_at,
                    expires_at, searchable_content, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                # Essential conversations expire after 30 days (refreshed by re-analysis)
                expires_at = now + timedelta(days=30)

                connection.execute(
                    query,
                    (
                        new_memory_id,
                        original_memory.get(
                            "original_chat_id"
                        ),  # Preserve original chat_id link
                        json.dumps(enhanced_processed_data),
                        essential_memory.importance_score,
                        f"essential_{original_memory.get('category_primary', 'conversation')}",  # Mark as essential
                        "short_term",
                        namespace,
                        now.isoformat(),
                        expires_at.isoformat(),
                        original_memory.get(
                            "searchable_content", essential_memory.summary
                        ),
                        essential_memory.summary,
                    ),
                )

                connection.commit()
                return True

        except Exception as e:
            logger.error(
                f"ConsciouscAgent: Failed to copy conversation to short-term: {e}"
            )
            return False

    async def _get_original_memory(self, db_manager, memory_id: str) -> Optional[Dict]:
        """Get original memory from long-term storage"""
        try:
            with db_manager._get_connection() as connection:
                query = """
                SELECT memory_id, original_chat_id, processed_data, importance_score,
                       category_primary, searchable_content, summary
                FROM long_term_memory
                WHERE memory_id = ?
                """

                cursor = connection.execute(query, (memory_id,))
                row = cursor.fetchone()

                if row:
                    return {
                        "memory_id": row[0],
                        "original_chat_id": row[1],
                        "processed_data": row[2],
                        "importance_score": row[3],
                        "category_primary": row[4],
                        "searchable_content": row[5],
                        "summary": row[6],
                    }
                return None

        except Exception as e:
            logger.error(f"ConsciouscAgent: Failed to get original memory: {e}")
            return None

    def should_run_analysis(self) -> bool:
        """Check if it's time to run memory analysis"""
        if self.last_analysis is None:
            return True

        return datetime.now() - self.last_analysis >= self.analysis_interval

    async def run_background_analysis(self, db_manager, namespace: str = "default"):
        """Run the complete background analysis workflow"""
        try:
            if not self.should_run_analysis():
                return

            logger.info("ConsciouscAgent: Starting background memory analysis")

            # Analyze memory patterns
            analysis = await self.analyze_memory_patterns(db_manager, namespace)

            if analysis:
                # Update short-term memory with selected conversations
                await self.update_short_term_memories(db_manager, analysis, namespace)
                logger.info(
                    "ConsciouscAgent: Background analysis completed successfully"
                )
            else:
                logger.info(
                    "ConsciouscAgent: No analysis performed (insufficient data)"
                )

        except Exception as e:
            logger.error(f"ConsciouscAgent: Background analysis failed: {e}")
