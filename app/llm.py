import os
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # groq | gemini | ollama | openai


def get_llm(temperature: float = 0.05):
    if PROVIDER == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(model="openai/gpt-oss-120b", temperature=temperature)
    if PROVIDER == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=temperature)
    if PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model="qwen2.5:7b", temperature=temperature)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model="gpt-4o-mini", temperature=temperature)


def get_embeddings():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")