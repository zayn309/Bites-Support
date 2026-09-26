import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.tools import tool

logger = logging.getLogger(__name__)
PERSIST_DIR = Path(__file__).parent.parent / "chroma_db"

embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small")
vectorstore = Chroma(
    collection_name="bites_faq",
    embedding_function=embeddings,
    persist_directory=str(PERSIST_DIR),
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})


@tool
def search_faq(query: str) -> str:
    """Search the Bites FAQ knowledge base for policy questions
    (refunds, delivery fees, cancellations, allergies, promo codes)."""
    logger.info("TOOL CALLED: search_faq(query=%r)", query)
    results = retriever.invoke(query)
    if not results:
        return "No relevant FAQ found."
    return "\n\n---\n\n".join(
        f"[{doc.metadata.get('source', 'faq')}] {doc.page_content}" for doc in results
    )