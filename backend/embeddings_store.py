import chromadb
from config import EMBEDDING_MODEL
from data_loader import resolve_page

class VectorStore:
    def __init__(self, chunks, *, model=None):
        if model is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(EMBEDDING_MODEL)
        self.model = model
        self.chunks = chunks
        self.client = chromadb.Client()
        self.collection = self.client.create_collection("triple_spark_rag", embedding_function=None)
        texts = [c["text"] for c in chunks]
        vectors = self.model.encode(texts).tolist()
        self.collection.add(
            ids=[c["id"] for c in chunks],
            documents=texts,
            embeddings=vectors,
            metadatas=[{"source": c["source"], "page": resolve_page(c)} for c in chunks],
        )

    def search(self, question, k):
        vector = self.model.encode([question]).tolist()
        return self.collection.query(
            query_embeddings=vector,
            n_results=min(k, len(self.chunks)),
            include=["documents", "metadatas", "distances"],
        )
