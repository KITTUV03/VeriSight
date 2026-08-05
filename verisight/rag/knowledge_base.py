"""
ChromaDB Knowledge Base for VeriSight.

Manages persistent storage of debugging sessions as structured embeddings.
Supports 11 collections covering specifications, RTL, testbench, logs,
errors, fixes, patterns, protocols, assertions, coverage, and lessons learned.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from verisight.config import get_config
from verisight.utils.logger import get_logger

logger = get_logger("knowledge_base")

# Collection definitions
COLLECTIONS = [
    "specifications",
    "rtl",
    # ChromaDB rejects collection names shorter than 3 characters.
    "testbench",
    "logs",
    "errors",
    "fixes",
    "patterns",
    "protocols",
    "assertions",
    "coverage",
    "lessons_learned",
]


class KnowledgeBase:
    """
    ChromaDB-backed knowledge base for storing and retrieving
    debugging sessions and patterns.
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Initialize the knowledge base.

        Args:
            persist_path: Path for ChromaDB persistence.
                         Defaults to config setting.
        """
        config = get_config()
        self.persist_path = persist_path or config.chroma.persist_path
        self._client = None
        self._collections: Dict[str, Any] = {}

    @property
    def client(self):
        """Lazy-initialize ChromaDB client."""
        if self._client is None:
            try:
                import chromadb
                Path(self.persist_path).mkdir(parents=True, exist_ok=True)
                self._client = chromadb.PersistentClient(
                    path=self.persist_path
                )
                logger.info(f"ChromaDB initialized at: {self.persist_path}")
            except ImportError:
                logger.warning(
                    "ChromaDB not installed. RAG features disabled. "
                    "Install with: pip install chromadb"
                )
                return None
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                return None
        return self._client

    def get_collection(self, name: str):
        """Get or create a named collection."""
        if name not in self._collections:
            if self.client is None:
                return None
            try:
                self._collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={"description": f"VeriSight {name} knowledge"}
                )
            except Exception as e:
                logger.error(f"Failed to get/create collection '{name}': {e}")
                return None
        return self._collections[name]

    def initialize_collections(self) -> bool:
        """Initialize all standard collections."""
        if self.client is None:
            return False

        for name in COLLECTIONS:
            self.get_collection(name)

        logger.info(f"Initialized {len(COLLECTIONS)} collections")
        return True

    def store_session(
        self,
        session_id: str,
        problem: str,
        cause: str,
        fix: str,
        classification: str,
        files: List[str],
        metadata: Dict[str, str],
    ) -> bool:
        """
        Store a complete debugging session in the knowledge base.

        Args:
            session_id: Unique session identifier.
            problem: Problem description.
            cause: Root cause description.
            fix: Recommended fix.
            classification: Bug classification (TB Bug / RTL Bug / etc.).
            files: List of affected files.
            metadata: Additional metadata.

        Returns:
            True if stored successfully.
        """
        errors_col = self.get_collection("errors")
        fixes_col = self.get_collection("fixes")
        lessons_col = self.get_collection("lessons_learned")

        if not all([errors_col, fixes_col, lessons_col]):
            logger.warning("Knowledge base not available, skipping storage")
            return False

        timestamp = datetime.now().isoformat()

        try:
            # Store the error/problem
            errors_col.add(
                documents=[problem],
                ids=[f"{session_id}_error"],
                metadatas=[{
                    "session_id": session_id,
                    "classification": classification,
                    "timestamp": timestamp,
                    "cause": cause[:500],
                    "files": json.dumps(files[:10]),
                    **{k: str(v)[:200] for k, v in metadata.items()},
                }]
            )

            # Store the fix
            fixes_col.add(
                documents=[fix],
                ids=[f"{session_id}_fix"],
                metadatas=[{
                    "session_id": session_id,
                    "classification": classification,
                    "timestamp": timestamp,
                    "problem": problem[:500],
                }]
            )

            # Store as a lesson learned (combined problem→cause→fix)
            lesson = (
                f"Problem: {problem}\n"
                f"Root Cause: {cause}\n"
                f"Classification: {classification}\n"
                f"Fix: {fix}\n"
                f"Files: {', '.join(files[:5])}"
            )
            lessons_col.add(
                documents=[lesson],
                ids=[f"{session_id}_lesson"],
                metadatas=[{
                    "session_id": session_id,
                    "classification": classification,
                    "timestamp": timestamp,
                }]
            )

            logger.info(f"Stored debugging session: {session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to store session {session_id}: {e}")
            return False

    def store_pattern(
        self,
        pattern_id: str,
        pattern_description: str,
        category: str,
        metadata: Dict[str, str],
    ) -> bool:
        """Store a debugging pattern."""
        patterns_col = self.get_collection("patterns")
        if not patterns_col:
            return False

        try:
            patterns_col.add(
                documents=[pattern_description],
                ids=[pattern_id],
                metadatas=[{
                    "category": category,
                    "timestamp": datetime.now().isoformat(),
                    **{k: str(v)[:200] for k, v in metadata.items()},
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store pattern: {e}")
            return False

    def store_document(
        self,
        collection_name: str,
        doc_id: str,
        document: str,
        metadata: Dict[str, str],
    ) -> bool:
        """Store a document in a specific collection."""
        collection = self.get_collection(collection_name)
        if not collection:
            return False

        try:
            collection.add(
                documents=[document],
                ids=[doc_id],
                metadatas=[{
                    "timestamp": datetime.now().isoformat(),
                    **{k: str(v)[:200] for k, v in metadata.items()},
                }]
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store document in {collection_name}: {e}")
            return False

    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query a collection by semantic similarity.

        Args:
            collection_name: Name of the collection to query.
            query_text: Query text.
            n_results: Number of results to return.
            where: Optional metadata filter.

        Returns:
            List of results with documents, metadatas, and distances.
        """
        collection = self.get_collection(collection_name)
        if not collection:
            return []

        try:
            # Check collection has data
            if collection.count() == 0:
                return []

            query_params = {
                "query_texts": [query_text],
                "n_results": min(n_results, collection.count()),
            }
            if where:
                query_params["where"] = where

            results = collection.query(**query_params)

            # Format results
            formatted = []
            if results and results["documents"]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted.append({
                        "document": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0.0,
                        "id": results["ids"][0][i] if results["ids"] else "",
                    })

            return formatted

        except Exception as e:
            logger.error(f"Query failed on {collection_name}: {e}")
            return []

    def search_similar_failures(
        self, problem_description: str, n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for similar past failures.

        Args:
            problem_description: Description of current problem.
            n_results: Number of results.

        Returns:
            List of similar past failures with their solutions.
        """
        # Search across errors and lessons learned
        error_results = self.query("errors", problem_description, n_results)
        lesson_results = self.query("lessons_learned", problem_description, n_results)

        # Merge and sort by distance (lower = more similar)
        all_results = []
        for r in error_results:
            r["source"] = "errors"
            all_results.append(r)
        for r in lesson_results:
            r["source"] = "lessons_learned"
            all_results.append(r)

        all_results.sort(key=lambda x: x.get("distance", float("inf")))
        return all_results[:n_results]

    def search_patterns(
        self, query: str, category: Optional[str] = None, n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Search for relevant debugging patterns."""
        where = {"category": category} if category else None
        return self.query("patterns", query, n_results, where)

    def get_stats(self) -> Dict[str, int]:
        """Get counts for all collections."""
        stats = {}
        for name in COLLECTIONS:
            col = self.get_collection(name)
            if col:
                try:
                    stats[name] = col.count()
                except Exception:
                    stats[name] = -1
            else:
                stats[name] = -1
        return stats
