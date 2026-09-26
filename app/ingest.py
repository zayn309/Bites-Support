import argparse
import shutil
import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownTextSplitter
from langchain_core.documents import Document

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FAQ_DIR = Path(__file__).parent.parent / "data" / "faq"
PERSIST_DIR = Path(__file__).parent.parent / "chroma_db"


def ingest(force: bool = False):
    if force and PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)
        logger.info("Cleared existing Chroma index.")

    embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-small",show_progress=True)
    vectorstore = Chroma(
        collection_name="bites_faq",
        embedding_function=embeddings,
        persist_directory=str(PERSIST_DIR),
    )

    splitter = MarkdownTextSplitter(chunk_size=500, chunk_overlap=50)
    docs = []
    for path in FAQ_DIR.glob("*.md"):
        for chunk in splitter.split_text(path.read_text(encoding="utf-8")):
            docs.append(Document(page_content=chunk, metadata={"source": path.stem}))

    vectorstore.add_documents(docs)
    logger.info("Indexed %d chunks into Chroma.", len(docs))


def parse_args():
    parser = argparse.ArgumentParser(description="Build or rebuild the Bites FAQ Chroma index.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete the existing Chroma index and rebuild from scratch.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    ingest(force=args.force)
    
