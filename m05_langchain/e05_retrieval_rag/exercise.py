"""Exercise 5.5: retrieval and RAG.

Retrieval-augmented generation in five steps: load documents, split them into
chunks, embed and index the chunks, retrieve the best ones for a question,
and put them into the prompt. You build each step, and a small vector store,
then wire them into LCEL chains. Run the tests with:

    uv run pytest m05_langchain/e05_retrieval_rag
"""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel, RunnablePassthrough
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

ChatModel = BaseChatModel | Runnable[Any, Any]
Retriever = BaseRetriever | Runnable[str, list[Document]]


# ---------------------------------------------------------------------------
# Given: deterministic, offline embeddings (no numpy, no API key)
# ---------------------------------------------------------------------------
class HashingEmbeddings(Embeddings):
    """Bag-of-words "embeddings": every word is hashed into one of ``size`` buckets.

    Texts that share words get similar vectors, identical texts get identical
    vectors (cosine similarity 1.0). It is not semantic, but it is
    deterministic and good enough to test retrieval plumbing.

    (``langchain_core.embeddings.DeterministicFakeEmbedding`` and
    ``InMemoryVectorStore`` need numpy, which this repo does not install.)

    In production swap in a real model, e.g.
    ``langchain_openai.OpenAIEmbeddings(model="text-embedding-3-small")``.
    Nothing else in this exercise has to change.
    """

    def __init__(self, size: int = 256) -> None:
        self.size = size

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.size
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            vector[int.from_bytes(digest[:8], "big") % self.size] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        return [v / norm for v in vector] if norm else vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


# ---------------------------------------------------------------------------
# Task 1: rows -> Documents
# ---------------------------------------------------------------------------
def load_documents(records: Iterable[dict[str, Any]]) -> list[Document]:
    """Turn knowledge-base rows into ``Document`` objects.

    Each record has ``id`` (int), ``title``, ``body`` and ``url``. For each:

    * ``page_content`` = the body, stripped
    * ``metadata`` = ``{"source": url, "title": title, "doc_id": id}``
    * ``id`` = ``str(id)``

    Skip records whose body is empty or only whitespace.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 2: chunking
# ---------------------------------------------------------------------------
def split_documents(
    docs: Sequence[Document], chunk_size: int = 200, chunk_overlap: int = 40
) -> list[Document]:
    """Split documents into overlapping chunks that remember where they came from.

    Use ``RecursiveCharacterTextSplitter(chunk_size=..., chunk_overlap=...,
    add_start_index=True)``. Every chunk:

    * has at most ``chunk_size`` characters
    * keeps **all** metadata of its parent document, plus
      ``"start_index"`` (offset of the chunk in the parent's text, added by
      the splitter) and ``"chunk_index"`` (0, 1, 2, ... per parent document)
    * gets ``id = f"{parent.id}:{chunk_index}"`` when the parent has an id
      (stable ids let you re-index a document without duplicates), else ``None``

    Chunks come out grouped by parent, in input order.
    ``chunk_overlap >= chunk_size`` raises ``ValueError`` (check it yourself:
    the splitter only rejects ``chunk_overlap > chunk_size``).

    Hint: call ``splitter.split_documents([doc])`` once per document so you
    can number the chunks of each one.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 3 + 4: a minimal vector store
# ---------------------------------------------------------------------------
MetadataFilter = dict[str, Any] | Callable[[Document], bool]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Task 3a: cosine similarity of two equal-length vectors.

    ``dot(a, b) / (|a| * |b|)``; return ``0.0`` if either vector is all zeros.
    Different lengths raise ``ValueError``.
    """
    raise NotImplementedError("TODO: implement this task")


class SimpleVectorStore(VectorStore):
    """An in-memory ``VectorStore`` in pure Python.

    Subclassing ``VectorStore`` and implementing a few methods gives you
    ``add_texts``, ``from_documents``, ``as_retriever`` etc. for free. That is
    exactly how real integrations (PGVector, Chroma, ...) plug into LangChain.
    """

    def __init__(self, embedding: Embeddings) -> None:
        self.embedding = embedding
        # id -> (document, vector); dicts keep insertion order
        self._records: dict[str, tuple[Document, list[float]]] = {}

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding

    def __len__(self) -> int:
        return len(self._records)

    def add_documents(self, documents: list[Document], **kwargs: Any) -> list[str]:
        """Task 3b: embed and store documents; return their ids.

        * Embed all texts with **one** ``self.embedding.embed_documents(...)``
          call (providers bill and rate-limit per request: batch!).
        * Id of each document: ``kwargs["ids"][i]`` if ``ids`` is given,
          else ``doc.id``, else a new ``uuid.uuid4().hex``.
        * Store a *copy* of the document with its ``id`` set
          (``doc.model_copy(update={"id": ...})``) in ``self._records``.
          Adding an id that already exists replaces it (upsert).
        * ``ids`` of the wrong length raises ``ValueError``.
        """
        raise NotImplementedError("TODO: implement this task")

    def similarity_search_with_score(
        self, query: str, k: int = 4, filter: MetadataFilter | None = None, **kwargs: Any
    ) -> list[tuple[Document, float]]:
        """Task 4a: the ``k`` most similar documents with their cosine scores.

        * Embed the query with ``self.embedding.embed_query``.
        * ``filter`` (optional) is applied **before** ranking:
          - a ``dict``: keep documents whose metadata has every key with an
            equal value (``{"source": "a.md"}``)
          - a callable: keep documents for which ``filter(doc)`` is true
        * Sort by score, highest first; equal scores keep insertion order.
        * Return at most ``k`` pairs; ``k <= 0`` or an empty store gives ``[]``.
        """
        raise NotImplementedError("TODO: implement this task")

    def similarity_search(
        self, query: str, k: int = 4, filter: MetadataFilter | None = None, **kwargs: Any
    ) -> list[Document]:
        """Task 4b: like ``similarity_search_with_score`` but documents only.

        ``as_retriever()`` calls this method with its ``search_kwargs``.
        """
        raise NotImplementedError("TODO: implement this task")

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Embeddings,
        metadatas: list[dict] | None = None,
        **kwargs: Any,
    ) -> SimpleVectorStore:
        store = cls(embedding)
        store.add_texts(texts, metadatas=metadatas, **kwargs)
        return store


# ---------------------------------------------------------------------------
# Task 5: retriever
# ---------------------------------------------------------------------------
def build_retriever(store: VectorStore, k: int = 4, source: str | None = None) -> VectorStoreRetriever:
    """Wrap a vector store as a retriever (a ``Runnable[str, list[Document]]``).

    * ``store.as_retriever(search_kwargs=...)`` with ``{"k": k}``.
    * If ``source`` is given, also pass ``"filter": {"source": source}`` so
      only chunks of that document are returned (e.g. "search in this
      PDF only").
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 6: formatting context with citations
# ---------------------------------------------------------------------------
NO_CONTEXT = "No relevant documents found."


def format_docs(docs: Sequence[Document]) -> str:
    """Render retrieved documents as a numbered context block for the prompt.

    Each document becomes ``"[<n>] <source>\\n<page_content>"`` where ``n``
    starts at 1 and ``source`` is ``metadata["source"]`` (``"unknown"`` if
    missing). Blocks are joined with a blank line (``"\\n\\n"``). No
    documents -> ``NO_CONTEXT``.

    >>> print(format_docs([Document("Refunds take 5 days.", metadata={"source": "faq.md"})]))
    [1] faq.md
    Refunds take 5 days.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 7: the RAG chain
# ---------------------------------------------------------------------------
RAG_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Answer the question using only the context below. "
            "Cite sources as [n]. If the context is not enough, say so.\n\n"
            "Context:\n{context}",
        ),
        ("human", "{question}"),
    ]
)


def build_rag_chain(retriever: Retriever, model: ChatModel) -> Runnable[str, str]:
    """The classic LCEL RAG chain. Input: the question (``str``). Output: ``str``.

    ::

        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | RAG_PROMPT | model | StrOutputParser()

    The dict runs both branches on the same input string: one retrieves and
    formats, the other passes the question through unchanged.
    """
    raise NotImplementedError("TODO: implement this task")


# ---------------------------------------------------------------------------
# Task 8: answer + sources
# ---------------------------------------------------------------------------
def build_rag_chain_with_sources(retriever: Retriever, model: ChatModel) -> Runnable[str, dict]:
    """Like Task 7, but also return the sources, so the API can show citations.

    Input: the question (``str``). Output::

        {"answer": str, "sources": [unique metadata["source"] values, in retrieval order]}

    * The retriever must run **once** per question (it costs an embedding
      call and a DB query). So retrieve first, keep the documents, and build
      both the prompt context and the sources from them:
      ``RunnableParallel(docs=retriever, question=RunnablePassthrough()).assign(answer=...)``
      then map to the output dict.
    * Documents without a ``source`` are left out of ``sources``.
    """
    raise NotImplementedError("TODO: implement this task")
