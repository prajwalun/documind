import os
import subprocess

# Define the project name
PROJECT_NAME = "DocuMind"

# Define the file contents
CURSOR_RULES = """You are an expert Senior Software Engineer specializing in AI, RAG pipelines, and System Design.

**General Guidelines:**
- Write production-grade code. No "toy" scripts.
- Always include type hints (Python) and interfaces (TypeScript).
- Handle errors gracefully. Never let the app crash silently.
- Use environment variables for all secrets (API keys, DB URLs).

**Backend Rules (Python/FastAPI):**
- Use **FastAPI** for the API layer.
- Use **Pydantic V2** for data validation.
- Use **SQLAlchemy (Async)** for database interactions.
- Follow the "Service-Repository" pattern:
    - `routes/` should only handle HTTP logic.
    - `services/` should contain business logic (RAG, Ingestion).
    - `db/` should handle database queries.
- Use **Async/Await** for all I/O operations (DB, OpenAI calls).
- Docstrings are mandatory for every function.

**Frontend Rules (Next.js):**
- Use **Next.js 14+ (App Router)**.
- Use **Tailwind CSS** for styling.
- Use **Shadcn UI** components where possible.
- Use `lucide-react` for icons.
- Strict TypeScript: No `any` types allowed.

**RAG Specifics:**
- When discussing "Ingestion", assume we use **LangChain** with **RecursiveCharacterTextSplitter**.
- When discussing "Retrieval", assume **Hybrid Search** (pgvector + BM25).
- Always prioritize latency. Suggest caching where appropriate.

**Documentation:**
- If you change a file, update the relevant docstring.
- Explain *why* you chose a specific architectural pattern when asked.
"""

DOCKER_COMPOSE = """services:
  # The Vector Database (Postgres + pgvector)
  db:
    image: pgvector/pgvector:pg16
    container_name: documind_db
    environment:
      POSTGRES_USER: documind
      POSTGRES_PASSWORD: password
      POSTGRES_DB: documind_local
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  # Redis for Async Task Queue (Celery)
  redis:
    image: redis:alpine
    container_name: documind_redis
    ports:
      - "6379:6379"
    restart: always

  # Optional: PGAdmin to view your vectors visually
  pgadmin:
    image: dpage/pgadmin4
    container_name: documind_pgadmin
    environment:
      PGADMIN_DEFAULT_EMAIL: admin@documind.com
      PGADMIN_DEFAULT_PASSWORD: admin
    ports:
      - "5050:80"
    depends_on:
      - db

volumes:
  postgres_data:
"""

REQUIREMENTS_TXT = """fastapi
uvicorn[standard]
sqlalchemy
asyncpg
alembic
pydantic
pydantic-settings
python-dotenv
# AI & RAG
langchain
langchain-openai
langchain-community
langchain-postgres
psycopg2-binary
# Processing
tiktoken
pypdf
# Task Queue
celery
redis
# Utils
python-multipart
requests
"""

ENV_FILE = """# App
PROJECT_NAME=DocuMind
API_V1_STR=/api/v1

# Database
POSTGRES_SERVER=localhost
POSTGRES_USER=documind
POSTGRES_PASSWORD=password
POSTGRES_DB=documind_local
DATABASE_URL=postgresql+asyncpg://documind:password@localhost:5432/documind_local

# AI
OPENAI_API_KEY=sk-your-key-here

# Redis
REDIS_URL=redis://localhost:6379/0
"""

def create_structure():
    base_dirs = [
        f"{PROJECT_NAME}/backend/app/api/v1",
        f"{PROJECT_NAME}/backend/app/core",
        f"{PROJECT_NAME}/backend/app/models",
        f"{PROJECT_NAME}/backend/app/schemas",
        f"{PROJECT_NAME}/backend/app/services",
        # Frontend folder will be created by create-next-app later, but we make the placeholder
        f"{PROJECT_NAME}/frontend" 
    ]

    # Create Directories
    for directory in base_dirs:
        os.makedirs(directory, exist_ok=True)
        # Create __init__.py in python dirs
        if "backend" in directory:
            with open(f"{directory}/__init__.py", "w") as f:
                pass
            
            # Create parent __init__ if missing
            parent = os.path.dirname(directory)
            if not os.path.exists(f"{parent}/__init__.py"):
                with open(f"{parent}/__init__.py", "w") as f:
                    pass

    # Create Files
    files = {
        f"{PROJECT_NAME}/.cursorrules": CURSOR_RULES,
        f"{PROJECT_NAME}/docker-compose.yml": DOCKER_COMPOSE,
        f"{PROJECT_NAME}/backend/requirements.txt": REQUIREMENTS_TXT,
        f"{PROJECT_NAME}/backend/.env": ENV_FILE,
        f"{PROJECT_NAME}/backend/app/main.py": "from fastapi import FastAPI\n\napp = FastAPI(title=\"DocuMind API\")\n\n@app.get(\"/\")\ndef read_root():\n    return {\"message\": \"Welcome to DocuMind API\"}",
        f"{PROJECT_NAME}/backend/app/core/config.py": "from pydantic_settings import BaseSettings\n\nclass Settings(BaseSettings):\n    PROJECT_NAME: str = \"DocuMind\"\n    class Config:\n        env_file = \".env\"\n\nsettings = Settings()",
    }

    for path, content in files.items():
        with open(path, "w") as f:
            f.write(content)

    print(f"✅ Project structure for {PROJECT_NAME} created successfully!")
    print(f"📂 Location: {os.path.abspath(PROJECT_NAME)}")

if __name__ == "__main__":
    create_structure()