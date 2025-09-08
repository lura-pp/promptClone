"""
Memory Agent - The heart of Memori v1.0
Pydantic-based memory processing using OpenAI Structured Outputs
"""

from datetime import datetime
from typing import Any, Dict, Optional

import openai
from loguru import logger

from ..utils.pydantic_models import (
    ConversationContext,
    MemoryCategoryType,
    ProcessedMemory,
    RetentionType,
)


class MemoryAgent:
    """
    Pydantic-based memory agent for intelligent conversation processing.
    Uses OpenAI Structured Outputs for reliable, structured memory extraction.
    """

    SYSTEM_PROMPT = """You are an advanced Memory Processing Agent responsible for analyzing conversations and extracting structured information for long-term storage.

Your primary functions:
1. **Categorize Memory Type**: Classify information as fact, preference, skill, context, or rule
2. **Extract Entities**: Identify people, technologies, topics, skills, projects, and keywords
3. **Score Importance**: Determine retention type and various importance dimensions
4. **Create Searchable Content**: Generate optimized summaries and searchable text
5. **Make Storage Decisions**: Decide what should be stored and why

**CATEGORIZATION GUIDELINES:**
- **fact**: Factual information, definitions, technical details, specific data points
- **preference**: User preferences, likes/dislikes, settings, personal choices, opinions
- **skill**: Skills, abilities, competencies, learning progress, expertise levels
- **context**: Project context, work environment, current situations, background info
- **rule**: Rules, policies, procedures, guidelines, constraints, "should/must" statements

**RETENTION GUIDELINES:**
- **short_term**: Recent activities, temporary information, casual mentions (expires ~7 days)
- **long_term**: Important information, learned skills, preferences, significant context
- **permanent**: Critical rules, core preferences, essential facts, major milestones

**ENTITY EXTRACTION:**
Focus on extracting specific, searchable entities that would be useful for future retrieval:
- People: Names, roles, relationships
- Technologies: Tools, libraries, platforms, programming languages
- Topics: Subjects, domains, areas of interest
- Skills: Abilities, competencies, learning areas
- Projects: Named projects, repositories, initiatives
- Keywords: Important terms for search and categorization

**IMPORTANCE SCORING:**
Consider multiple dimensions:
- Overall importance (0.0-1.0): How crucial is this information?
- Novelty (0.0-1.0): How new or unique is this information?
- Relevance (0.0-1.0): How relevant to the user's current interests/work?
- Actionability (0.0-1.0): How actionable or useful is this information?

Be thorough but practical. Focus on information that would genuinely help in future conversations."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize Memory Agent with OpenAI configuration

        Args:
            api_key: OpenAI API key (if None, uses environment variable)
            model: OpenAI model to use for structured output (gpt-4o recommended)
        """
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    async def process_conversation(
        self,
        chat_id: str,
        user_input: str,
        ai_output: str,
        context: Optional[ConversationContext] = None,
        mem_prompt: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> ProcessedMemory:
        """
        Process a conversation using OpenAI Structured Outputs

        Args:
            chat_id: Conversation ID
            user_input: User's input message
            ai_output: AI's response
            context: Additional conversation context
            mem_prompt: Optional memory filtering prompt
            filters: Memory filters to apply

        Returns:
            Structured processed memory
        """
        try:
            # Prepare conversation content
            conversation_text = f"User: {user_input}\nAssistant: {ai_output}"

            # Build system prompt
            system_prompt = self.SYSTEM_PROMPT
            if mem_prompt:
                system_prompt += f"\n\nSPECIAL FOCUS: {mem_prompt}"

            # Prepare context information
            context_info = ""
            if context:
                context_info = f"""
CONVERSATION CONTEXT:
- Session: {context.session_id}
- Model: {context.model_used}
- User Projects: {', '.join(context.current_projects) if context.current_projects else 'None specified'}
- Relevant Skills: {', '.join(context.relevant_skills) if context.relevant_skills else 'None specified'}
- Topic Thread: {context.topic_thread or 'General conversation'}
"""

            # Call OpenAI Structured Outputs
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Process this conversation for memory storage:\n\n{conversation_text}\n{context_info}",
                    },
                ],
                response_format=ProcessedMemory,
                temperature=0.1,  # Low temperature for consistent processing
            )

            # Handle potential refusal
            if completion.choices[0].message.refusal:
                logger.warning(
                    f"Memory processing refused for chat {chat_id}: {completion.choices[0].message.refusal}"
                )
                return self._create_empty_memory(
                    chat_id, "Processing refused for safety reasons"
                )

            processed_memory = completion.choices[0].message.parsed

            # Apply filters if provided
            if filters and not self._passes_filters(processed_memory, filters):
                processed_memory.should_store = False
                processed_memory.storage_reasoning = (
                    "Filtered out based on memory filters"
                )

            # Add processing metadata
            processed_memory.processing_metadata = {
                "chat_id": chat_id,
                "model": self.model,
                "processed_at": datetime.now().isoformat(),
                "agent_version": "v1.0_pydantic",
            }

            logger.debug(
                f"Processed conversation {chat_id}: category={processed_memory.category.primary_category}, should_store={processed_memory.should_store}"
            )
            return processed_memory

        except Exception as e:
            logger.error(f"Memory agent processing failed for {chat_id}: {e}")
            return self._create_empty_memory(chat_id, f"Processing failed: {str(e)}")

    def process_conversation_sync(
        self,
        chat_id: str,
        user_input: str,
        ai_output: str,
        context: Optional[ConversationContext] = None,
        mem_prompt: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> ProcessedMemory:
        """
        Synchronous version of process_conversation for compatibility
        """
        try:
            # Prepare conversation content
            conversation_text = f"User: {user_input}\nAssistant: {ai_output}"

            # Build system prompt
            system_prompt = self.SYSTEM_PROMPT
            if mem_prompt:
                system_prompt += f"\n\nSPECIAL FOCUS: {mem_prompt}"

            # Prepare context information
            context_info = ""
            if context:
                context_info = f"""
CONVERSATION CONTEXT:
- Session: {context.session_id}
- Model: {context.model_used}
- User Projects: {', '.join(context.current_projects) if context.current_projects else 'None specified'}
- Relevant Skills: {', '.join(context.relevant_skills) if context.relevant_skills else 'None specified'}
- Topic Thread: {context.topic_thread or 'General conversation'}
"""

            # Call OpenAI Structured Outputs
            completion = self.client.beta.chat.completions.parse(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": f"Process this conversation for memory storage:\n\n{conversation_text}\n{context_info}",
                    },
                ],
                response_format=ProcessedMemory,
                temperature=0.1,
            )

            # Handle potential refusal
            if completion.choices[0].message.refusal:
                logger.warning(
                    f"Memory processing refused for chat {chat_id}: {completion.choices[0].message.refusal}"
                )
                return self._create_empty_memory(
                    chat_id, "Processing refused for safety reasons"
                )

            processed_memory = completion.choices[0].message.parsed

            # Apply filters if provided
            if filters and not self._passes_filters(processed_memory, filters):
                processed_memory.should_store = False
                processed_memory.storage_reasoning = (
                    "Filtered out based on memory filters"
                )

            # Add processing metadata
            processed_memory.processing_metadata = {
                "chat_id": chat_id,
                "model": self.model,
                "processed_at": datetime.now().isoformat(),
                "agent_version": "v1.0_pydantic",
            }

            logger.debug(
                f"Processed conversation {chat_id}: category={processed_memory.category.primary_category}, should_store={processed_memory.should_store}"
            )
            return processed_memory

        except Exception as e:
            logger.error(f"Memory agent processing failed for {chat_id}: {e}")
            return self._create_empty_memory(chat_id, f"Processing failed: {str(e)}")

    def _passes_filters(self, memory: ProcessedMemory, filters: Dict[str, Any]) -> bool:
        """Check if processed memory passes configured filters"""

        # Include keywords filter
        if "include_keywords" in filters:
            include_keywords = filters["include_keywords"]
            content_lower = memory.searchable_content.lower()
            if not any(
                keyword.lower() in content_lower for keyword in include_keywords
            ):
                return False

        # Exclude keywords filter
        if "exclude_keywords" in filters:
            exclude_keywords = filters["exclude_keywords"]
            content_lower = memory.searchable_content.lower()
            if any(keyword.lower() in content_lower for keyword in exclude_keywords):
                return False

        # Minimum importance filter
        if "min_importance" in filters:
            if memory.importance.importance_score < filters["min_importance"]:
                return False

        # Category filter
        if "allowed_categories" in filters:
            if memory.category.primary_category not in filters["allowed_categories"]:
                return False

        return True

    def _create_empty_memory(self, chat_id: str, reason: str) -> ProcessedMemory:
        """Create an empty memory object for error cases"""
        from ..utils.pydantic_models import (
            ExtractedEntities,
            MemoryCategory,
            MemoryCategoryType,
            MemoryImportance,
            RetentionType,
        )

        return ProcessedMemory(
            category=MemoryCategory(
                primary_category=MemoryCategoryType.fact,
                confidence_score=0.0,
                reasoning="Failed to process",
            ),
            entities=ExtractedEntities(),
            importance=MemoryImportance(
                importance_score=0.0,
                retention_type=RetentionType.short_term,
                reasoning="Processing failed",
            ),
            summary="Processing failed",
            searchable_content="",
            should_store=False,
            storage_reasoning=reason,
            processing_metadata={"chat_id": chat_id, "error": reason},
        )

    def determine_storage_location(self, processed_memory: ProcessedMemory) -> str:
        """Determine appropriate storage location based on memory properties"""

        if processed_memory.category.primary_category == MemoryCategoryType.rule:
            return "rules_memory"

        if processed_memory.importance.retention_type == RetentionType.permanent:
            return "long_term_memory"
        elif processed_memory.importance.retention_type == RetentionType.long_term:
            return "long_term_memory"
        else:
            return "short_term_memory"
