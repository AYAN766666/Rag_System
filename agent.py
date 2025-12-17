
# backend/agent_api.py
from agents import Agent, Runner, OpenAIChatCompletionsModel, AsyncOpenAI
from agents import set_tracing_disabled, function_tool
import os
from dotenv import load_dotenv
from agents import enable_verbose_stdout_logging

import cohere
from qdrant_client import QdrantClient

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# -----------------------------
# FastAPI App
# -----------------------------
app = FastAPI()

# -----------------------------
# Enable CORS for frontend fetch
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Development ke liye, production me specific domain use karein
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

# -----------------------------
# Logging & env
# -----------------------------
enable_verbose_stdout_logging()
load_dotenv()
set_tracing_disabled(disabled=True)

# -----------------------------
# Gemini API setup
# -----------------------------
gemini_api_key = os.getenv("GEMINI_API_KEY")
provider = AsyncOpenAI(
    api_key=gemini_api_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

model = OpenAIChatCompletionsModel(
    model="gemini-2.5-flash",  # ya koi free Gemini model
    openai_client=provider
)

# -----------------------------
# Cohere & Qdrant setup
# -----------------------------
cohere_client = cohere.Client(os.getenv("COHERE_API_KEY"))
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# -----------------------------
# Embedding function
# -----------------------------
async def get_embedding(text: str):
    """Get embedding vector from Cohere Embed v3"""
    try:
        response = cohere_client.embed(
            model="embed-english-v3.0",
            input_type="search_query",
            texts=[text],
        )
        return response.embeddings[0]
    except Exception as e:
        print("Cohere embedding failed:", e)
        return None

# -----------------------------
# Tool: retrieve
# -----------------------------
@function_tool
async def retrieve(query: str):
    embedding = await get_embedding(query)
    if embedding is None:
        print("Failed to get embedding for query:", query)
        return []

    try:
        result = qdrant.query_points(
            collection_name="humanoid_robotics_docs",
            query=embedding,
            limit=5
        )
        return [point.payload.get("text", "") for point in result.points]
    except Exception as e:
        print("Qdrant query failed:", e)
        return []

# -----------------------------
# Agent setup
# -----------------------------
agent = Agent(
    name="Assistant",
    instructions="""
You are an AI tutor for the Physical AI & Humanoid Robotics textbook.
To answer the user question, first call the tool `retrieve` with the user query.
Use ONLY the returned content from `retrieve` to answer.
If the answer is not in the retrieved content, say "I don't know".
""",
    model=model,
    tools=[retrieve]
)

# -----------------------------
# FastAPI Endpoints
# -----------------------------
@app.get("/")
async def root():
    return {"message": "FastAPI agent is running! Use POST /chat to talk with the AI."}

@app.post("/chat")
async def chat_with_agent(request: ChatRequest):
    print(f"Received message: {request.message}")
    # Async agent execution
    result = await Runner.run(
        agent,
        input=request.message
    )
    return {"response": result.final_output}

# -----------------------------
# Run the agent directly (console + uvicorn)
# -----------------------------
if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def test_agent():
        result = await Runner.run(
            agent,
            input="what is physical ai?"
        )
        print("Agent output:\n", result.final_output)

    # Test agent once on startup
    asyncio.run(test_agent())

    # Start FastAPI server
    uvicorn.run("backend.agent_api:app", host="0.0.0.0", port=8000, reload=True)
