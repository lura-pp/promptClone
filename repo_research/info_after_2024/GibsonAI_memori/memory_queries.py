"""
Memory-related database queries
"""

from typing import Dict

from .base_queries import BaseQueries


class MemoryQueries(BaseQueries):
    """Centralized memory-related SQL queries"""

    def get_table_creation_queries(self) -> Dict[str, str]:
        """Memory table creation queries"""
        from .base_queries import SchemaQueries

        return {
            "short_term_memory": SchemaQueries.TABLE_CREATION["short_term_memory"],
            "long_term_memory": SchemaQueries.TABLE_CREATION["long_term_memory"],
            "rules_memory": SchemaQueries.TABLE_CREATION["rules_memory"],
        }

    def get_index_creation_queries(self) -> Dict[str, str]:
        """Memory index creation queries"""
        from .base_queries import SchemaQueries

        return {
            k: v
            for k, v in SchemaQueries.INDEX_CREATION.items()
            if any(table in k for table in ["short_term", "long_term", "rules"])
        }

    def get_trigger_creation_queries(self) -> Dict[str, str]:
        """Memory trigger creation queries"""
        from .base_queries import SchemaQueries

        return SchemaQueries.TRIGGER_CREATION

    # INSERT Queries
    INSERT_SHORT_TERM_MEMORY = """
        INSERT INTO short_term_memory (
            memory_id, chat_id, processed_data, importance_score, category_primary,
            retention_type, namespace, created_at, expires_at, searchable_content, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    INSERT_LONG_TERM_MEMORY = """
        INSERT INTO long_term_memory (
            memory_id, original_chat_id, processed_data, importance_score, category_primary,
            retention_type, namespace, created_at, searchable_content, summary,
            novelty_score, relevance_score, actionability_score
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    INSERT_RULES_MEMORY = """
        INSERT INTO rules_memory (
            rule_id, rule_text, rule_type, priority, active, context_conditions,
            namespace, created_at, updated_at, processed_data, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    # SELECT Queries
    SELECT_MEMORIES_BY_NAMESPACE = """
        SELECT memory_id, processed_data, importance_score, category_primary, created_at, summary
        FROM {table}
        WHERE namespace = ?
        ORDER BY importance_score DESC, created_at DESC
        LIMIT ?
    """

    SELECT_MEMORIES_BY_CATEGORY = """
        SELECT memory_id, processed_data, importance_score, created_at, summary
        FROM {table}
        WHERE namespace = ? AND category_primary = ?
        ORDER BY importance_score DESC, created_at DESC
        LIMIT ?
    """

    SELECT_MEMORIES_BY_IMPORTANCE = """
        SELECT memory_id, processed_data, importance_score, created_at, summary
        FROM {table}
        WHERE namespace = ? AND importance_score >= ?
        ORDER BY importance_score DESC, created_at DESC
        LIMIT ?
    """

    SELECT_EXPIRED_MEMORIES = """
        SELECT memory_id, processed_data
        FROM short_term_memory
        WHERE namespace = ? AND expires_at <= ?
    """

    SELECT_MEMORY_BY_ID = """
        SELECT * FROM {table} WHERE memory_id = ? AND namespace = ?
    """

    # UPDATE Queries
    UPDATE_MEMORY_ACCESS = """
        UPDATE {table}
        SET access_count = access_count + 1, last_accessed = ?
        WHERE memory_id = ? AND namespace = ?
    """

    UPDATE_MEMORY_IMPORTANCE = """
        UPDATE {table}
        SET importance_score = ?
        WHERE memory_id = ? AND namespace = ?
    """

    UPDATE_RULE_STATUS = """
        UPDATE rules_memory
        SET active = ?, updated_at = ?
        WHERE rule_id = ? AND namespace = ?
    """

    # DELETE Queries
    DELETE_MEMORY = """
        DELETE FROM {table} WHERE memory_id = ? AND namespace = ?
    """

    DELETE_EXPIRED_MEMORIES = """
        DELETE FROM short_term_memory
        WHERE namespace = ? AND expires_at <= ?
    """

    DELETE_MEMORIES_BY_CATEGORY = """
        DELETE FROM {table}
        WHERE namespace = ? AND category_primary = ?
    """

    # SEARCH Queries
    SEARCH_MEMORIES_FTS = """
        SELECT m.memory_id, m.memory_type, m.namespace, m.searchable_content, m.summary, m.category_primary
        FROM memory_search_fts m
        WHERE m.searchable_content MATCH ? AND m.namespace = ?
        ORDER BY rank
        LIMIT ?
    """

    SEARCH_MEMORIES_SEMANTIC = """
        SELECT memory_id, processed_data, importance_score, searchable_content, summary
        FROM {table}
        WHERE namespace = ? AND (
            searchable_content LIKE ? OR
            summary LIKE ? OR
            category_primary = ?
        )
        ORDER BY importance_score DESC, created_at DESC
        LIMIT ?
    """

    # ANALYTICS Queries
    COUNT_MEMORIES_BY_CATEGORY = """
        SELECT category_primary, COUNT(*) as count
        FROM {table}
        WHERE namespace = ?
        GROUP BY category_primary
        ORDER BY count DESC
    """

    GET_MEMORY_STATISTICS = """
        SELECT
            COUNT(*) as total_memories,
            AVG(importance_score) as avg_importance,
            MAX(importance_score) as max_importance,
            MIN(importance_score) as min_importance,
            COUNT(DISTINCT category_primary) as unique_categories
        FROM {table}
        WHERE namespace = ?
    """

    GET_RECENT_MEMORIES = """
        SELECT memory_id, summary, importance_score, created_at
        FROM {table}
        WHERE namespace = ? AND created_at >= ?
        ORDER BY created_at DESC
        LIMIT ?
    """
