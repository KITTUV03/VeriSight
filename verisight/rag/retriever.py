"""
Semantic Similarity Retriever for VeriSight RAG.

Provides high-level retrieval interface that searches across multiple
ChromaDB collections and returns relevant past failures, fixes, and
debugging patterns.
"""

from typing import List, Dict, Any, Optional

from verisight.rag.knowledge_base import KnowledgeBase
from verisight.schemas.knowledge_schema import RAGContext
from verisight.utils.logger import get_logger

logger = get_logger("retriever")


class Retriever:
    """
    Semantic similarity retriever that searches the VeriSight
    knowledge base for relevant past debugging information.
    """

    def __init__(self, knowledge_base: KnowledgeBase):
        """
        Initialize the retriever.

        Args:
            knowledge_base: KnowledgeBase instance to search.
        """
        self.kb = knowledge_base

    def retrieve_context(
        self,
        problem_description: str,
        error_messages: List[str],
        n_results: int = 5,
    ) -> RAGContext:
        """
        Retrieve relevant context from the knowledge base.

        Searches across errors, fixes, patterns, and lessons learned
        to find similar past failures and relevant debugging patterns.

        Args:
            problem_description: Description of the current problem.
            error_messages: List of error messages from simulation.
            n_results: Number of results per query.

        Returns:
            RAGContext with similar failures and relevant patterns.
        """
        similar_failures = []
        relevant_patterns = []

        # Search for similar failures
        if problem_description:
            failures = self.kb.search_similar_failures(
                problem_description, n_results
            )
            for f in failures:
                similar_failures.append({
                    "document": f.get("document", ""),
                    "metadata": f.get("metadata", {}),
                    "similarity": 1.0 - f.get("distance", 1.0),
                    "source": f.get("source", ""),
                })

        # Search for relevant patterns using error messages
        for error_msg in error_messages[:3]:  # Limit to top 3 errors
            patterns = self.kb.search_patterns(error_msg, n_results=3)
            for p in patterns:
                relevant_patterns.append({
                    "document": p.get("document", ""),
                    "metadata": p.get("metadata", {}),
                    "similarity": 1.0 - p.get("distance", 1.0),
                    "query": error_msg[:200],
                })

        # Calculate overall confidence
        confidence = 0.0
        if similar_failures:
            top_similarity = similar_failures[0].get("similarity", 0.0)
            confidence = max(0.0, min(1.0, top_similarity))

        context = RAGContext(
            similar_failures=similar_failures,
            relevant_patterns=relevant_patterns,
            confidence=confidence,
        )

        logger.info(
            f"RAG retrieval: {len(similar_failures)} similar failures, "
            f"{len(relevant_patterns)} patterns, confidence={confidence:.2f}"
        )
        return context

    def search_by_category(
        self,
        category: str,
        query: str,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search a specific collection by category.

        Args:
            category: Collection name (specifications, rtl, tb, etc.).
            query: Search query.
            n_results: Number of results.

        Returns:
            List of matching documents with metadata.
        """
        return self.kb.query(category, query, n_results)

    def find_similar_fixes(
        self,
        problem: str,
        classification: Optional[str] = None,
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find fixes for similar problems.

        Args:
            problem: Problem description.
            classification: Optional filter by classification.
            n_results: Number of results.

        Returns:
            List of relevant fixes.
        """
        where = {"classification": classification} if classification else None
        return self.kb.query("fixes", problem, n_results, where)
