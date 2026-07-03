from __future__ import annotations

import datetime
from sqlalchemy import create_engine
from app.services.memory_manager import get_memory_manager, FAISSVectorStore
from app.knowledge.models import KnowledgeChunk
from app.knowledge.indexer import CodeIndexer, CodeGraph
from app.knowledge.parser import Chunker

class KnowledgeBase:
    def __init__(self, db_manager=None):
        self.db_manager = db_manager or get_memory_manager()
        self.vector_store = FAISSVectorStore()
        self.code_graph = CodeGraph()
        self._load_chunks()

    def _load_chunks(self):
        session = self.db_manager.Session()
        try:
            chunks = session.query(KnowledgeChunk).all()
            for chunk in chunks:
                self.vector_store.add(chunk.embedding_json, chunk.content, chunk.metadata_json)
                if chunk.chunk_type == "code_ast":
                    # Build graph relations
                    indexer = CodeIndexer()
                    ast_info = indexer.parse_python_ast(chunk.content, chunk.file_path)
                    self.code_graph.build_from_indexer_info(chunk.file_path, ast_info)
        finally:
            session.close()

    def index_content(self, file_path: str, content: str, chunk_type: str, metadata: dict = None):
        metadata = metadata or {}
        metadata["file_path"] = file_path
        metadata["chunk_type"] = chunk_type
        
        session = self.db_manager.Session()
        try:
            chunk_id = str(datetime.datetime.utcnow().timestamp()) + "-" + file_path + "-" + metadata.get("symbol_name", "text")
            embedding = self.db_manager.embedding_provider.get_embedding(content)
            
            db_chunk = KnowledgeChunk(
                id=chunk_id,
                file_path=file_path,
                chunk_type=chunk_type,
                content=content,
                embedding_json=embedding,
                metadata_json=metadata
            )
            session.add(db_chunk)
            session.commit()
            
            self.vector_store.add(embedding, content, metadata)
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def index_file(self, file_path: str, content: str):
        if file_path.endswith(".py"):
            indexer = CodeIndexer()
            ast_info = indexer.parse_python_ast(content, file_path)
            
            # Index functions
            for func in ast_info["functions"]:
                func_content = (
                    f"def {func['name']}({', '.join(func['arguments'])}):\n"
                    f"    \"\"\"{func['docstring']}\"\"\"\n"
                    f"    # file: {func['file_path']}, lines: {func['line_start']}-{func['line_end']}\n"
                    f"    # dependencies: {', '.join(func['dependencies'])}"
                )
                self.index_content(
                    file_path=file_path,
                    content=func_content,
                    chunk_type="code_ast",
                    metadata={
                        "symbol_name": func["name"],
                        "symbol_type": "function",
                        "line_start": func["line_start"],
                        "line_end": func["line_end"]
                    }
                )
            
            # Index classes
            for cls in ast_info["classes"]:
                cls_content = (
                    f"class {cls['name']}({', '.join(cls['inheritance'])}):\n"
                    f"    # file: {cls['file_path']}\n"
                    f"    # methods: {', '.join(m['name'] for m in cls['methods'])}"
                )
                self.index_content(
                    file_path=file_path,
                    content=cls_content,
                    chunk_type="code_ast",
                    metadata={
                        "symbol_name": cls["name"],
                        "symbol_type": "class"
                    }
                )
        else:
            chunks = Chunker.chunk_text(content, chunk_size=400, overlap=40)
            for i, chunk in enumerate(chunks):
                self.index_content(
                    file_path=file_path,
                    content=chunk,
                    chunk_type="text",
                    metadata={
                        "chunk_index": i
                    }
                )

    def update_file_index(self, file_path: str, content: str):
        """Incremental Index Update: removes old chunks for a file, and indexes new content."""
        session = self.db_manager.Session()
        try:
            # Delete old chunks
            session.query(KnowledgeChunk).filter(KnowledgeChunk.file_path == file_path).delete()
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

        # Re-index new file content
        self.index_file(file_path, content)

        # Re-initialize vector store and dependency graph from refreshed DB
        self.vector_store = FAISSVectorStore()
        self.code_graph = CodeGraph()
        self._load_chunks()

    def search(self, query: str, limit: int = 5) -> dict:
        """Hybrid Search: combines symbol search, keyword search, and vector search with ranking priority."""
        matches_dict = {}

        # 1. Symbol Search (exact match on class/function name)
        session = self.db_manager.Session()
        try:
            chunks = session.query(KnowledgeChunk).all()
            for chunk in chunks:
                meta = chunk.metadata_json or {}
                sym_name = meta.get("symbol_name", "")
                if sym_name and sym_name == query:
                    key = (chunk.file_path, chunk.content)
                    matches_dict[key] = {
                        "file_path": chunk.file_path,
                        "line_start": meta.get("line_start", 1),
                        "line_end": meta.get("line_end", 1),
                        "symbol": sym_name,
                        "content": chunk.content,
                        "symbol_score": 10.0,
                        "keyword_score": 0.0,
                        "semantic_score": 0.0
                    }

            # 2. Keyword Search (substring match in content)
            for chunk in chunks:
                if query.lower() in chunk.content.lower():
                    key = (chunk.file_path, chunk.content)
                    meta = chunk.metadata_json or {}
                    if key not in matches_dict:
                        matches_dict[key] = {
                            "file_path": chunk.file_path,
                            "line_start": meta.get("line_start", 1),
                            "line_end": meta.get("line_end", 1),
                            "symbol": meta.get("symbol_name", ""),
                            "content": chunk.content,
                            "symbol_score": 0.0,
                            "keyword_score": 2.0,
                            "semantic_score": 0.0
                        }
                    else:
                        matches_dict[key]["keyword_score"] = 2.0
        finally:
            session.close()

        # 3. Semantic Search (FAISS vector similarity)
        semantic_results = self.vector_store.search(
            self.db_manager.embedding_provider.get_embedding(query),
            k=limit
        )
        for sem in semantic_results:
            text = sem["text"]
            meta = sem["metadata"] or {}
            file_path = meta.get("file_path", "")
            key = (file_path, text)
            
            dist = sem.get("score", 0.0)
            normalized_sem_score = 1.0 / (1.0 + dist)
            
            if key not in matches_dict:
                matches_dict[key] = {
                    "file_path": file_path,
                    "line_start": meta.get("line_start", 1),
                    "line_end": meta.get("line_end", 1),
                    "symbol": meta.get("symbol_name", ""),
                    "content": text,
                    "symbol_score": 0.0,
                    "keyword_score": 0.0,
                    "semantic_score": normalized_sem_score
                }
            else:
                matches_dict[key]["semantic_score"] = normalized_sem_score

        # Combine scores and project structured output
        final_matches = []
        for match in matches_dict.values():
            final_score = match["symbol_score"] + match["keyword_score"] + match["semantic_score"]
            final_matches.append({
                "file_path": match["file_path"],
                "line_start": match["line_start"],
                "line_end": match["line_end"],
                "symbol": match["symbol"],
                "content": match["content"],
                "score": round(final_score, 2)
            })

        # Sort by final score descending
        final_matches.sort(key=lambda x: x["score"], reverse=True)
        return {"matches": final_matches[:limit]}


def search_knowledge(query: str) -> dict:
    """Search the codebase intelligence and documentation RAG database for matching classes, functions, and files."""
    kb = KnowledgeBase()
    return kb.search(query)
