# search_engine.py

import logging
import os
from typing import List, Tuple, Dict, Any
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
import faiss  # Requires: pip install faiss-cpu (or faiss-gpu)
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
# Remove the direct import of data_loader as it's no longer used here
# from data_loader import load_and_transform_data

# --- Configuration ---
# Choose your embedding model. 'all-MiniLM-L6-v2' is fast and decent for general text.
# Consider 'multi-qa-MiniLM-L6-codistill' for question-answer style similarity.
EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'
VECTOR_INDEX_FILE = 'vector_index.faiss' # File to save/load the FAISS index
CORPUS_FILE = 'search_corpus.pkl'      # File to save/load the corpus text
METADATA_FILE = 'search_metadata.pkl'  # File to save/load the original metadata rows
TFIDF_VECTORIZER_FILE = 'tfidf_vectorizer.pkl' # File to save/load the TF-IDF model

logger = logging.getLogger(__name__)

class HybridSearchEngine:
    """
    Manages vector and keyword search for the vulnerability index dashboard.
    """

    def __init__(self, df: pd.DataFrame, force_rebuild: bool = False):
        """
        Initializes the search engine, loading or building the vector index and TF-IDF model.

        Args:
            df (pd.DataFrame): The main dataframe loaded by load_and_transform_data in main.py.
                               It should contain columns like 'article_text', 'llm_summary',
                               'inferred_actor', 'target_country', 'strategic_intent', etc.
                               This is the FINAL processed dataframe passed from main.py.
            force_rebuild (bool): If True, rebuilds the index even if saved files exist.
        """
        # IMPORTANT: Ensure the incoming df has the required columns like 'llm_summary'
        required_cols = ['article_text', 'llm_summary', 'inferred_actor', 'target_country', 'strategic_intent', 'sector', 'media_outlet', 'URL', 'display_headline', 'posting_time', 'confidence', 'tone']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
             raise ValueError(f"DataFrame is missing required columns for search: {missing_cols}")

        self.df = df.reset_index(drop=True) # Ensure consistent indexing
        self.model_name = EMBEDDING_MODEL_NAME
        self.model = SentenceTransformer(self.model_name)
        self.index_file = VECTOR_INDEX_FILE
        self.corpus_file = CORPUS_FILE
        self.metadata_file = METADATA_FILE
        self.tfidf_file = TFIDF_VECTORIZER_FILE

        # Load or Build Indexes
        if not force_rebuild and self._check_saved_files():
            logger.info("Loading saved vector index and TF-IDF model...")
            self.corpus_texts, self.metadata_rows = self._load_corpus_and_metadata()
            self.index = self._load_faiss_index()
            self.tfidf_vectorizer = self._load_tfidf_vectorizer()
        else:
            logger.info("Building new vector index and TF-IDF model...")
            self.corpus_texts, self.metadata_rows = self._prepare_corpus_and_metadata(self.df)
            self.index = self._build_faiss_index(self.corpus_texts)
            self.tfidf_vectorizer = self._build_tfidf_vectorizer(self.corpus_texts)
            self._save_corpus_and_metadata(self.corpus_texts, self.metadata_rows)
            self._save_faiss_index(self.index)
            self._save_tfidf_vectorizer(self.tfidf_vectorizer)
            logger.info("New indexes built and saved.")

    def _check_saved_files(self) -> bool:
        """Checks if all necessary saved files exist."""
        required_files = [self.index_file, self.corpus_file, self.metadata_file, self.tfidf_file]
        return all(os.path.exists(f) for f in required_files)

    def _prepare_corpus_and_metadata(self, df: pd.DataFrame) -> Tuple[List[str], pd.DataFrame]:
        """
        Creates the text corpus for indexing and extracts corresponding metadata rows.

        Args:
            df (pd.DataFrame): The input dataframe (from main.py).

        Returns:
            Tuple[List[str], pd.DataFrame]: The list of text strings for the corpus,
                                            and the corresponding metadata rows.
        """
        # Combine relevant text fields for searching
        # Ensure columns like 'llm_summary' and 'display_headline' exist in df before calling this
        text_parts = [
            df['article_text'].fillna('').astype(str),
            df['llm_summary'].fillna('').astype(str), # This should now exist
            df['inferred_actor'].fillna('').astype(str),
            df['target_country'].fillna('').astype(str),
            df['strategic_intent'].fillna('').astype(str),
            df['sector'].fillna('').astype(str),
            df['media_outlet'].fillna('').astype(str),
            # Add other relevant columns if needed
        ]
        # Join the parts with a separator
        corpus = [" ".join(parts) for parts in zip(*text_parts)]
        # Select relevant metadata columns, ensuring 'llm_summary' and 'display_headline' are included
        metadata_df = df[['URL', 'display_headline', 'llm_summary', 'inferred_actor', 'target_country', 'strategic_intent', 'sector', 'media_outlet', 'posting_time', 'confidence', 'tone']].copy()
        return corpus, metadata_df

    def _build_faiss_index(self, corpus: List[str]) -> faiss.Index:
        """Builds and returns a FAISS index from the corpus embeddings."""
        logger.info("Encoding corpus for vector search...")
        embeddings = self.model.encode(corpus, show_progress_bar=True)
        dimension = embeddings.shape[1]
        logger.info(f"Creating FAISS index with dimension {dimension}...")
        # Using IndexFlatIP (Inner Product) for cosine similarity (after normalization)
        index = faiss.IndexFlatIP(dimension)
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings)
        logger.info("Adding embeddings to FAISS index...")
        index.add(embeddings.astype('float32'))
        return index

    def _build_tfidf_vectorizer(self, corpus: List[str]) -> TfidfVectorizer:
        """Builds and returns a TF-IDF vectorizer fitted on the corpus."""
        logger.info("Fitting TF-IDF vectorizer...")
        # Consider adding stop words specific to your domain if needed
        # stop_words='english' might remove too many relevant terms
        vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words=None, # Consider 'english' or custom list
            ngram_range=(1, 2), # Include bigrams for better phrase matching
            max_features=10000 # Limit features if memory is a concern
        )
        vectorizer.fit(corpus)
        return vectorizer

    def _save_corpus_and_metadata(self, corpus: List[str], metadata: pd.DataFrame):
        """Saves the corpus and metadata to disk."""
        import pickle
        with open(self.corpus_file, 'wb') as f:
            pickle.dump(corpus, f)
        with open(self.metadata_file, 'wb') as f:
            pickle.dump(metadata, f)

    def _save_faiss_index(self, index: faiss.Index):
        """Saves the FAISS index to disk."""
        faiss.write_index(index, self.index_file)

    def _save_tfidf_vectorizer(self, vectorizer: TfidfVectorizer):
        """Saves the TF-IDF vectorizer to disk."""
        import pickle
        with open(self.tfidf_file, 'wb') as f:
            pickle.dump(vectorizer, f)

    def _load_corpus_and_metadata(self) -> Tuple[List[str], pd.DataFrame]:
        """Loads the corpus and metadata from disk."""
        import pickle
        with open(self.corpus_file, 'rb') as f:
            corpus = pickle.load(f)
        with open(self.metadata_file, 'rb') as f:
            metadata = pickle.load(f)
        return corpus, metadata

    def _load_faiss_index(self) -> faiss.Index:
        """Loads the FAISS index from disk."""
        return faiss.read_index(self.index_file)

    def _load_tfidf_vectorizer(self) -> TfidfVectorizer:
        """Loads the TF-IDF vectorizer from disk."""
        import pickle
        with open(self.tfidf_file, 'rb') as f:
            vectorizer = pickle.load(f)
        return vectorizer


    def vector_search(self, query: str, top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Performs a semantic search using the vector index.

        Args:
            query (str): The user's query string.
            top_k (int): Number of top results to retrieve.

        Returns:
            Tuple[np.ndarray, np.ndarray]: Similarities and indices of top results.
        """
        query_embedding = self.model.encode([query])
        faiss.normalize_L2(query_embedding)
        similarities, indices = self.index.search(query_embedding.astype('float32'), top_k)
        # Note: FAISS Inner Product gives cosine similarity directly after normalization
        return similarities[0], indices[0]

    def keyword_search(self, query: str, top_k: int = 5) -> Tuple[np.ndarray, np.ndarray]:
        """
        Performs a keyword search using TF-IDF cosine similarity.

        Args:
            query (str): The user's query string.
            top_k (int): Number of top results to retrieve.

        Returns:
            Tuple[np.ndarray, np.ndarray]: Similarities and indices of top results.
        """
        query_vec = self.tfidf_vectorizer.transform([query])
        doc_vecs = self.tfidf_vectorizer.transform(self.corpus_texts)
        similarities = cosine_similarity(query_vec, doc_vecs).flatten()
        top_k_indices = np.argsort(similarities)[::-1][:top_k] # Get top_k indices, sorted descending
        top_k_similarities = similarities[top_k_indices]
        return top_k_similarities, top_k_indices


    def hybrid_search(self, query: str, top_k: int = 5, weight_vector: float = 0.7, weight_keyword: float = 0.3) -> pd.DataFrame:
        """
        Combines vector and keyword search results using weighted scores.

        Args:
            query (str): The user's query string.
            top_k (int): Number of top results to retrieve.
            weight_vector (float): Weight for vector search scores (between 0 and 1).
            weight_keyword (float): Weight for keyword search scores (between 0 and 1).

        Returns:
            pd.DataFrame: A DataFrame containing the top-k matched rows from metadata,
                          including combined scores.
        """
        if weight_vector + weight_keyword != 1.0:
             logger.warning("Warning: Weights do not sum to 1.0. Normalizing.")

        # Perform individual searches
        vec_sim, vec_indices = self.vector_search(query, top_k=len(self.corpus_texts)) # Get all for normalization
        kw_sim, kw_indices = self.keyword_search(query, top_k=len(self.corpus_texts))

        # Create dense arrays for all docs based on returned indices
        all_doc_scores = np.zeros((2, len(self.corpus_texts)))
        all_doc_scores[0, vec_indices] = vec_sim
        all_doc_scores[1, kw_indices] = kw_sim

        # Normalize scores row-wise (per search type) to [0, 1] range
        # Handle potential division by zero if all scores are the same (e.g., 0)
        mins = all_doc_scores.min(axis=1, keepdims=True)
        maxs = all_doc_scores.max(axis=1, keepdims=True)
        ranges = maxs - mins
        ranges[ranges == 0] = 1 # Avoid division by zero if range is 0
        normalized_scores = (all_doc_scores - mins) / ranges

        # Calculate weighted combined scores
        combined_scores = (weight_vector * normalized_scores[0] + weight_keyword * normalized_scores[1])

        # Get top_k results based on combined scores
        top_k_indices_final = np.argsort(combined_scores)[::-1][:top_k]
        top_k_scores_final = combined_scores[top_k_indices_final]

        # Retrieve corresponding metadata rows
        result_metadata = self.metadata_rows.iloc[top_k_indices_final].copy()
        result_metadata['combined_score'] = top_k_scores_final # Add the combined score
        # Optional: Add individual scores for debugging
        # result_metadata['vector_score'] = normalized_scores[0][top_k_indices_final]
        # result_metadata['keyword_score'] = normalized_scores[1][top_k_indices_final]

        return result_metadata

    def get_context_for_llm(self, query: str, top_k: int = 5) -> str:
        """
        Retrieves context (top-k results) formatted as a string suitable for an LLM prompt.

        Args:
            query (str): The user's query string.
            top_k (int): Number of top results to retrieve for context.

        Returns:
            str: A formatted string containing the retrieved context.
        """
        results_df = self.hybrid_search(query, top_k=top_k)

        if results_df.empty:
            return "No relevant articles found in the dataset for the given query."

        context_lines = ["Retrieved Articles:"]
        for idx, row in results_df.iterrows():
            # Format each article snippet for the LLM context
            # Ensure 'llm_summary', 'display_headline', etc. are available in row
            snippet = (
                f"- **Headline**: {row.get('display_headline', 'N/A')}\n"
                f"  **Summary**: {row.get('llm_summary', 'N/A')[:200]}...\n" # Truncate summary for brevity
                f"  **Actor**: {row.get('inferred_actor', 'N/A')}, **Country**: {row.get('target_country', 'N/A')}, **Intent**: {row.get('strategic_intent', 'N/A')}\n"
                f"  **Sector**: {row.get('sector', 'N/A')}, **Tone**: {row.get('tone', 'N/A')}\n"
                f"  **URL**: {row.get('URL', 'N/A')}\n"
                f"  **Confidence**: {row.get('confidence', 'N/A')}\n"
                f"  **Combined Score**: {row.get('combined_score', 0.0):.4f}\n"
            )
            context_lines.append(snippet)
        return "\n".join(context_lines)


# --- Modified: Standalone function to initialize the engine WITH a provided DataFrame ---
def initialize_search_engine(df: pd.DataFrame, force_rebuild: bool = False) -> HybridSearchEngine:
    """
    Initializes the search engine instance using a provided dataframe.
    This function should be called from main.py after the dataframe is fully processed.

    Args:
        df (pd.DataFrame): The processed dataframe from main.py, containing columns like
                           'article_text', 'llm_summary', 'inferred_actor', etc.
        force_rebuild (bool): If True, rebuilds the index even if saved files exist.

    Returns:
        HybridSearchEngine: An initialized instance of the search engine.
    """
    logger.info("Initializing Search Engine with provided DataFrame...")
    if df.empty:
        raise ValueError("Provided dataframe is empty. Cannot initialize search engine.")
    search_engine_instance = HybridSearchEngine(df, force_rebuild=force_rebuild)
    logger.info("Search Engine initialized successfully.")
    return search_engine_instance

# Example usage (if running this script directly for testing):
# if __name__ == "__main__":
#     # You would need to load your df here for standalone testing
#     # df = load_and_transform_data() # This wouldn't work anymore without importing data_loader
#     # df = ... # Load your processed df somehow
#     # se = initialize_search_engine(df, force_rebuild=True)
#     # query = "economic dependency Russia Ethiopia"
#     # results = se.hybrid_search(query, top_k=3)
#     # print(results[['display_headline', 'combined_score']])
#     # context = se.get_context_for_llm(query, top_k=3)
#     # print("\n--- CONTEXT FOR LLM ---\n", context)
