
import requests
import xml.etree.ElementTree as ET
import trafilatura
import cohere
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

# -------------------------------
# CONFIG
# -------------------------------
SITEMAP_URL = "https://physicalhumanoidaitextbook.vercel.app/sitemap.xml"
COLLECTION_NAME = "humanoid_robotics_docs"

cohere_client = cohere.Client("LZPDz2PDJPDVRuvAs3VkISJznUdgbL4mDrzPgPgT")
EMBED_MODEL = "embed-english-v3.0"

qdrant_client = QdrantClient(
    url="https://91a64b91-1f8d-4ae0-aef2-73ea66296820.europe-west3-0.gcp.cloud.qdrant.io:6333",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.mqyZzGZWIq9CUcjTjDUsyQiXIQ2MAEv7CxO0VZP6WD4",
)

# -------------------------------------
def get_all_urls(sitemap_url):
    xml = requests.get(sitemap_url).text
    root = ET.fromstring(xml)

    urls = []
    for child in root:
        loc_tag = child.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        if loc_tag is not None:
            urls.append(loc_tag.text)

    print("\nFOUND URLS:")
    for u in urls:
        print(" -", u)

    return urls

# -------------------------------------
def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[SKIPPED] Cannot open URL: {url}")
        print("Reason:", e)
        return None

    text = trafilatura.extract(response.text)
    if not text:
        print("[WARNING] No text extracted from:", url)

    return text

# -------------------------------------
def chunk_text(text, max_chars=1200):
    chunks = []
    while len(text) > max_chars:
        split_pos = text[:max_chars].rfind(". ")
        if split_pos == -1:
            split_pos = max_chars

        chunks.append(text[:split_pos])
        text = text[split_pos:]

    chunks.append(text)
    return chunks

# -------------------------------------
def embed(text):
    response = cohere_client.embed(
        model=EMBED_MODEL,
        input_type="search_query",
        texts=[text],
    )
    return response.embeddings[0]

# -------------------------------------
def create_collection():
    print("\nCreating Qdrant collection...")
    qdrant_client.recreate_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=1024,
            distance=Distance.COSINE,
        ),
    )

# -------------------------------------
def save_chunk_to_qdrant(chunk, chunk_id, url):
    vector = embed(chunk)

    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "url": url,
                    "text": chunk,
                    "chunk_id": chunk_id,
                },
            )
        ],
    )

# -------------------------------------
def ingest_book():
    urls = get_all_urls(SITEMAP_URL)

    create_collection()

    global_id = 1

    for url in urls:
        # ❌ skip invalid docusaurus example URLs
        if "your-docusaurus-site.example.com" in url:
            print("[SKIPPED FAKE URL]:", url)
            continue

        print("\nProcessing:", url)

        text = extract_text_from_url(url)
        if not text:
            continue

        chunks = chunk_text(text)

        for ch in chunks:
            save_chunk_to_qdrant(ch, global_id, url)
            print(f"Saved chunk {global_id}")
            global_id += 1

    print("\n✔️ Ingestion completed!")
    print("Total chunks stored:", global_id - 1)

# Run
if __name__ == "__main__":
    ingest_book()
