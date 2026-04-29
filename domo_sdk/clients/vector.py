"""
Vector database and embedding client for Domo SDK.

Provides both traditional embedding/similarity operations and full VectorDB (Recall) 
functionality for semantic search, RAG, and document retrieval.
"""

from typing import List, Dict, Any, Optional, Union, Tuple
import base64
import time
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from ..core import _get_domo_client, _config
from .. import usage


class Vector:
    """
    Vector database client for embeddings, semantic search, and RAG.
    
    Supports both:
    1. Direct embedding generation and similarity calculations
    2. Full VectorDB (Recall) operations for persistent vector storage
    """
    
    # ========================================================================
    # EMBEDDING GENERATION
    # ========================================================================
    
    def embed(self, texts: List[str], 
              model: str = "domo.domo_ai.domo-embed-text-multilingual-v1:cohere", 
              max_length: int = 2000) -> np.ndarray:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            model: Embedding model to use
                   Options: 
                   - "domo.openai.text-embedding-ada-002" (8192 token context)
                   - "domo.domo_ai.domo-embed-text-multilingual-v1:cohere" (2048 char limit)
            max_length: Max characters per text (default 2000 to stay under limit)
        
        Returns:
            numpy array of embeddings, shape (len(texts), embedding_dim)
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/ai/v1/embedding/text"
        
        truncated_texts = [text[:max_length] if len(text) > max_length else text for text in texts]
        
        for i, (orig, trunc) in enumerate(zip(texts, truncated_texts)):
            if len(orig) > max_length:
                print(f"WARNING: Text {i} truncated from {len(orig)} to {len(trunc)} chars")
        
        payload = {
            "input": truncated_texts,
            "model": model
        }
        
        try:
            call_started = time.time()
            response = domo_client._post(url, payload).json()
            elapsed = time.time() - call_started

            if 'status' in response and response['status'] >= 400:
                error_msg = response.get('details', {}).get('inputIssue', response.get('message', 'Unknown error'))
                raise ValueError(f"Embedding API error: {error_msg}")

            # Embedding endpoint does not return token counts (modelProviderUsage
            # is null — see agent-docs/ai-response-shape.md). Estimate from input
            # length: chars/4 is a coarse, model-agnostic approximation. Off by
            # ±20%; treat as a trend indicator, not a billing source.
            estimated_tokens = sum(len(t) for t in truncated_texts) // 4
            usage.record_call(
                surface="embedding",
                model_id=response.get("modelId") or model,
                embedding_tokens_estimated=estimated_tokens,
                elapsed_seconds=elapsed,
            )

            embeddings = response['embeddings']
            return np.array(embeddings)

        except KeyError as e:
            print(f"ERROR: Unexpected response format: {response}")
            raise
    
    def embed_single(self, text: str, 
                     model: str = "domo.domo_ai.domo-embed-text-multilingual-v1:cohere",
                     max_length: int = 2000) -> np.ndarray:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text string to embed
            model: Embedding model to use
            max_length: Max characters (default 2000)
        
        Returns:
            numpy array of embedding vector
        """
        result = self.embed([text], model=model, max_length=max_length)
        return result[0]

    
    # ========================================================================
    # SIMILARITY & SEARCH
    # ========================================================================
    
    def similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Similarity score between -1 and 1 (higher = more similar)
        """
        return float(cosine_similarity([embedding1], [embedding2])[0][0])
    
    def search(self, query: str, corpus_embeddings: np.ndarray, top_k: int = 3,
               model: str = "domo.domo_ai.domo-embed-text-multilingual-v1:cohere") -> List[Tuple[int, float]]:
        """
        Search for most similar items in a corpus using semantic similarity.
        
        Args:
            query: Query text to search for
            corpus_embeddings: Array of embeddings to search through (shape: [n_items, embedding_dim])
            top_k: Number of top results to return
            model: Embedding model to use for query
        
        Returns:
            List of tuples (index, similarity_score) sorted by relevance
        """
        query_embedding = self.embed_single(query, model=model)
        similarities = cosine_similarity([query_embedding], corpus_embeddings)[0]
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        return [(int(idx), float(similarities[idx])) for idx in top_indices]
    
    # ========================================================================
    # VECTORDB (RECALL) - INDEX MANAGEMENT
    # ========================================================================
    
    def create_index(self, index_id: str, 
                     embedding_model: str = "domo.domo_ai.domo-embed-text-multilingual-v1:cohere") -> Dict[str, Any]:
        """
        Create a new vector database index.
        
        Args:
            index_id: Unique identifier for the index
            embedding_model: Model to use for embeddings
        
        Returns:
            Response dictionary from the API
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes"
        
        payload = {
            "indexId": index_id,
            "embeddingModel": embedding_model
        }
        
        response = domo_client._post(url, payload)
        return response.json() if response.status_code == 200 else response.text
    
    def delete_index(self, index_id: str) -> Dict[str, Any]:
        """
        Delete a vector database index.
        
        Args:
            index_id: ID of the index to delete
        
        Returns:
            Response from the API
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes/{index_id}"
        
        response = domo_client._delete(url)
        return response.json() if response.status_code == 200 else response.text
    
    def list_indexes(self) -> List[Dict[str, Any]]:
        """
        List all vector database indexes.
        
        Args:
        
        Returns:
            List of index information dictionaries
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes"
        
        response = domo_client._get(url)
        return response.json() if response.status_code == 200 else []

    
    # ========================================================================
    # VECTORDB (RECALL) - VECTOR OPERATIONS
    # ========================================================================
    
    def upsert(self, index_id: str, nodes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insert or update vectors in an index.
        
        Args:
            index_id: ID of the index
            nodes: List of node dictionaries with structure:
                   {
                       "id": "optional_id",
                       "content": "text content",
                       "type": "TEXT" | "IMAGE" | "DOCUMENT",
                       "embedding": [float, ...],
                       "properties": {"key": "value"}
                   }
        
        Returns:
            Response with upserted count and IDs
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes/{index_id}/upsert"
        
        payload = {"nodes": nodes}
        
        response = domo_client._post(url, payload)
        return response.json() if response.status_code == 200 else response.text
    
    
    def query(self, index_id: str, 
              input_text: Optional[str] = None,
              embedding: Optional[Union[np.ndarray, List[float]]] = None,
              top_k: int = 10,
              weight: float = 1.0,
              filters: Optional[Dict[str, Any]] = None,
              namespace: Optional[str] = None,
              include_metadata: bool = False,
              ) -> Dict[str, Any]:
        """
        Query the vector database.
        
        Args:
            index_id: ID of the index to query
            input_text: Text query (will be auto-embedded) - use this OR embedding
            embedding: Pre-computed embedding vector - use this OR input_text
            top_k: Number of results to return
            weight: Query weight (default 1.0)
            filters: Optional metadata filters {"key": "value"}
            namespace: Optional namespace to query within
            include_metadata: Whether to include metadata in results
        
        Returns:
            Dictionary with matches and scores
        """
        if input_text is None and embedding is None:
            raise ValueError("Must provide either input_text or embedding")
        if input_text is not None and embedding is not None:
            raise ValueError("Provide only one of input_text or embedding")
        
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes/{index_id}/query"
        
        payload = {
            "topK": top_k,
            "weight": weight,
            "includeMetadata": include_metadata
        }
        
        if input_text is not None:
            payload["input"] = input_text
        else:
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            payload["embedding"] = embedding
        
        if filters:
            payload["filter"] = filters
        if namespace:
            payload["namespace"] = namespace
        
        response = domo_client._post(url, payload)
        return response.json() if response.status_code == 200 else {"error": response.text}

    
    def delete_vectors(self, index_id: str, vector_ids: List[str],
                      ) -> Dict[str, Any]:
        """
        Delete specific vectors from an index.
        
        Args:
            index_id: ID of the index
            vector_ids: List of vector IDs to delete
        
        Returns:
            Response from the API
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes/{index_id}/delete"
        
        payload = {"ids": vector_ids}
        
        response = domo_client._post(url, payload)
        return response.json() if response.status_code == 200 else response.text
    
    def clear_index(self, index_id: str) -> Dict[str, Any]:
        """
        Delete all vectors from an index (clear the index).
        
        Args:
            index_id: ID of the index to clear
        
        Returns:
            Response from the API
        """
        domo_client = _get_domo_client()
        url = f"{_config['hostname']}/api/recall/v1/indexes/{index_id}/vectors"
        
        response = domo_client._delete(url)
        return response.json() if response.status_code == 200 else response.text
    
    
    # ========================================================================
    # HIGH-LEVEL RAG HELPERS
    # ========================================================================
    
    def rag_pipeline(self, index_id: str, query: str, top_k: int = 3,
                     context_template: str = "Context:\n{context}\n\nQuestion: {query}",
                     ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Complete RAG pipeline: query vector DB and format context for LLM.
        
        Args:
            index_id: ID of the index to query
            query: User's question/query
            top_k: Number of context chunks to retrieve
            context_template: Template for formatting context
        
        Returns:
            Tuple of (formatted_prompt, retrieved_documents)
        """
        results = self.query_text(index_id, query, top_k=top_k, )
        
        context_parts = []
        for i, match in enumerate(results, 1):
            content = match['node']['content']
            score = match['score']
            context_parts.append(f"[{i}] (score: {score:.3f})\n{content}")
        
        context = "\n\n".join(context_parts)
        formatted_prompt = context_template.format(context=context, query=query)
        
        return formatted_prompt, results
    