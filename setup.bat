@echo off
mkdir support-agent
cd support-agent

python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install langgraph langchain langchain-openai langchain-chroma chromadb fastapi uvicorn python-dotenv

mkdir app data\faq evals
type nul > app\__init__.py
type nul > app\tools.py
type nul > app\rag.py
type nul > app\graph.py
type nul > app\main.py
type nul > evals\run_evals.py
type nul > README.md
echo OPENAI_API_KEY=sk-...> .env

echo Done. Now run: cd support-agent ^&^& .venv\Scripts\activate