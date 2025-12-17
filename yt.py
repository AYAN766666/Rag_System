import cohere
from qdrant_client import QdrantClient

# Initialize Cohere client
cohere_client = cohere.Client("LZPDz2PDJPDVRuvAs3VkISJznUdgbL4mDrzPgPgT")

# Connect to Qdrant
qdrant = QdrantClient(
    url="https://91a64b91-1f8d-4ae0-aef2-73ea66296820.europe-west3-0.gcp.cloud.qdrant.io:6333", 
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.mqyZzGZWIq9CUcjTjDUsyQiXIQ2MAEv7CxO0VZP6WD4"
)

def get_embedding(text):
    """Get embedding vector from Cohere Embed v3"""
    response = cohere_client.embed(
        model="embed-english-v3.0",
        input_type="search_query",  # Use search_query for queries
        texts=[text],
    )
    return response.embeddings[0]  # Return the first embedding

def retrieve(query):
    embedding = get_embedding(query)
    result = qdrant.query_points(
        collection_name="humanoid_robotics_docs",
        query=embedding,
        limit=5
    )
    return [point.payload["text"] for point in result.points]

# Test
print(retrieve("What data do you have?"))