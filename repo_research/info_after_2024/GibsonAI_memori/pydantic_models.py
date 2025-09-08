"""
Pydantic Models for Structured Memory Processing
"""

from datetime import datetime
from enum import Enum
from typing import Annotated, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field


class MemoryCategoryType(str, Enum):
    """Primary memory categories"""

    fact = "fact"
    preference = "preference"
    skill = "skill"
    context = "context"
    rule = "rule"


class RetentionType(str, Enum):
    """Memory retention types"""

    short_term = "short_term"
    long_term = "long_term"
    permanent = "permanent"


class EntityType(str, Enum):
    """Types of entities that can be extracted"""

    person = "person"
    technology = "technology"
    topic = "topic"
    skill = "skill"
    project = "project"
    keyword = "keyword"


# Define constrained types using Annotated
ConfidenceScore = Annotated[float, Field(ge=0.0, le=1.0)]
ImportanceScore = Annotated[float, Field(ge=0.0, le=1.0)]
RelevanceScore = Annotated[float, Field(ge=0.0, le=1.0)]
PriorityLevel = Annotated[int, Field(ge=1, le=10)]


class MemoryCategory(BaseModel):
    """Memory categorization with confidence and reasoning"""

    primary_category: MemoryCategoryType
    confidence_score: ConfidenceScore = Field(
        description="Confidence in categorization (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Brief explanation for why this category was chosen"
    )


class ExtractedEntity(BaseModel):
    """Individual extracted entity with metadata"""

    entity_type: EntityType
    value: str = Field(description="The actual entity value")
    relevance_score: RelevanceScore = Field(
        description="How relevant this entity is to the memory"
    )
    context: Optional[str] = Field(
        default=None, description="Additional context about this entity"
    )


class ExtractedEntities(BaseModel):
    """All entities extracted from a conversation"""

    people: List[str] = Field(
        default_factory=list, description="Names of people mentioned"
    )
    technologies: List[str] = Field(
        default_factory=list, description="Technologies, tools, libraries mentioned"
    )
    topics: List[str] = Field(
        default_factory=list, description="Main topics or subjects discussed"
    )
    skills: List[str] = Field(
        default_factory=list, description="Skills, abilities, or competencies mentioned"
    )
    projects: List[str] = Field(
        default_factory=list,
        description="Projects, repositories, or initiatives mentioned",
    )
    keywords: List[str] = Field(
        default_factory=list, description="Important keywords for search"
    )

    # Structured entities with metadata
    structured_entities: List[ExtractedEntity] = Field(
        default_factory=list, description="Detailed entity extraction"
    )


class MemoryImportance(BaseModel):
    """Importance scoring and retention decisions"""

    importance_score: ImportanceScore = Field(
        description="Overall importance score (0.0-1.0)"
    )
    retention_type: RetentionType = Field(description="Recommended retention type")
    reasoning: str = Field(
        description="Explanation for the importance level and retention decision"
    )

    # Additional scoring factors
    novelty_score: RelevanceScore = Field(
        default=0.5, description="How novel/new this information is"
    )
    relevance_score: RelevanceScore = Field(
        default=0.5, description="How relevant to user's interests"
    )
    actionability_score: RelevanceScore = Field(
        default=0.5, description="How actionable this information is"
    )


class ProcessedMemory(BaseModel):
    """Complete processed memory with all extracted information"""

    # Core categorization
    category: MemoryCategory

    # Entity extraction
    entities: ExtractedEntities

    # Importance and retention
    importance: MemoryImportance

    # Content processing
    summary: str = Field(description="Concise, searchable summary of the memory")
    searchable_content: str = Field(
        description="Content optimized for keyword and semantic search"
    )
    key_insights: List[str] = Field(
        default_factory=list, description="Key insights or takeaways"
    )

    # Storage decision
    should_store: bool = Field(description="Whether this memory should be stored")
    storage_reasoning: str = Field(
        description="Why this memory should or shouldn't be stored"
    )

    # Metadata (optional fields)
    timestamp: Optional[datetime] = Field(
        default_factory=datetime.now, description="When this memory was processed"
    )
    processing_metadata: Optional[Dict[str, str]] = Field(
        default=None, description="Additional processing metadata"
    )


class MemorySearchQuery(BaseModel):
    """Structured query for memory search"""

    # Query components
    query_text: str = Field(description="Original query text")
    intent: str = Field(description="Interpreted intent of the query")

    # Search parameters
    entity_filters: List[str] = Field(
        default_factory=list, description="Specific entities to search for"
    )
    category_filters: List[MemoryCategoryType] = Field(
        default_factory=list, description="Memory categories to include"
    )
    time_range: Optional[str] = Field(
        default=None, description="Time range for search (e.g., 'last_week')"
    )
    min_importance: ImportanceScore = Field(
        default=0.0, description="Minimum importance score"
    )

    # Search strategy
    search_strategy: List[str] = Field(
        default_factory=list, description="Recommended search strategies"
    )
    expected_result_types: List[str] = Field(
        default_factory=list, description="Expected types of results"
    )


class MemoryRelationship(BaseModel):
    """Relationship between memories"""

    source_memory_id: str
    target_memory_id: str
    relationship_type: Literal[
        "builds_on", "contradicts", "supports", "related_to", "prerequisite"
    ]
    strength: RelevanceScore = Field(description="Strength of the relationship")
    reasoning: str = Field(description="Why these memories are related")


class UserRule(BaseModel):
    """User preferences and rules"""

    rule_text: str = Field(description="The rule or preference in natural language")
    rule_type: Literal["preference", "instruction", "constraint", "goal"]
    priority: PriorityLevel = Field(default=5, description="Priority level (1-10)")
    context: Optional[str] = Field(default=None, description="When this rule applies")
    active: bool = Field(
        default=True, description="Whether this rule is currently active"
    )


class ConversationContext(BaseModel):
    """Context information for memory processing"""

    model_config = {"protected_namespaces": ()}

    user_id: Optional[str] = Field(default=None)
    session_id: str
    conversation_id: str
    model_used: str

    # User context
    user_preferences: List[str] = Field(default_factory=list)
    current_projects: List[str] = Field(default_factory=list)
    relevant_skills: List[str] = Field(default_factory=list)

    # Conversation metadata
    conversation_length: int = Field(
        default=1, description="Number of exchanges in this conversation"
    )
    topic_thread: Optional[str] = Field(
        default=None, description="Main topic thread being discussed"
    )

    # Memory context
    recent_memories: List[str] = Field(
        default_factory=list, description="IDs of recently accessed memories"
    )
    applied_rules: List[str] = Field(
        default_factory=list, description="Rules that were applied"
    )


class MemoryStats(BaseModel):
    """Statistics about stored memories"""

    total_memories: int
    memories_by_category: Dict[str, int]
    memories_by_retention: Dict[str, int]
    average_importance: float
    total_entities: int
    most_common_entities: List[Tuple[str, int]]
    storage_size_mb: float
    oldest_memory_date: Optional[datetime]
    newest_memory_date: Optional[datetime]
