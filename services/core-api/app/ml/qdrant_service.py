from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class QdrantService:
    """Qdrant vector database for location embeddings"""

    def __init__(self):
        self.client = None
        self.model = None
        self.collection_name = "locations"
        self.vector_size = 384  # all-MiniLM-L6-v2 output size
        logger.info("QdrantService initialized (lazy loading)")

    def _load(self):
        """Lazy load Qdrant client and embedding model"""
        if self.client is None:
            logger.info("Connecting to Qdrant...")
            self.client = QdrantClient(host="qdrant", port=6333)
            logger.info("✅ Qdrant connected")

        if self.model is None:
            logger.info("Loading sentence transformer model...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("✅ Sentence transformer loaded")

    def create_collection(self):
        """Create locations collection if not exists"""
        self._load()
        
        collections = self.client.get_collections().collections
        names = [c.name for c in collections]
        
        if self.collection_name not in names:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"✅ Collection '{self.collection_name}' created")
        else:
            logger.info(f"Collection '{self.collection_name}' already exists")

    def add_locations(self, locations: List[Dict]) -> int:
        """Add enriched locations to Qdrant"""
        self._load()
        self.create_collection()

        points = []
        for loc in locations:
            name = loc.get("original_name", "")
            place_data = loc.get("place_data", {})

            # Embedding oluştur
            text = f"{name} {place_data.get('address', '')}"
            vector = self.model.encode(text).tolist()

            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "name": name,
                    "address": place_data.get("address", ""),
                    "lat": place_data.get("location", {}).get("lat"),
                    "lng": place_data.get("location", {}).get("lng"),
                    "type": place_data.get("type", ""),
                }
            )
            points.append(point)

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"✅ Added {len(points)} locations to Qdrant")
        return len(points)

    def search_similar(self, query: str, limit: int = 5) -> List[Dict]:
        """Search similar locations by text query"""
        self._load()

        vector = self.model.encode(query).tolist()
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=vector,
            limit=limit
        )

        locations = []
        for r in results:
            locations.append({
                "name": r.payload.get("name"),
                "address": r.payload.get("address"),
                "score": round(r.score, 3),
                "lat": r.payload.get("lat"),
                "lng": r.payload.get("lng"),
            })

        logger.info(f"Found {len(locations)} similar locations for: {query}")
        return locations