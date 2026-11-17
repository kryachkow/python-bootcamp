"""Tests for exercise 5.5.

HashingEmbeddings is lexical, not semantic, so the tests never rely on
"meaningful" ranking: they query with a document's exact text (score 1.0)
or assert on structure (counts, filters, ids, prompt contents).
"""

import pytest
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.vectorstores import VectorStore, VectorStoreRetriever

from m05_langchain.e05_retrieval_rag.exercise import (
    NO_CONTEXT,
    HashingEmbeddings,
    SimpleVectorStore,
    build_rag_chain,
    build_rag_chain_with_sources,
    build_retriever,
    cosine_similarity,
    format_docs,
    load_documents,
    split_documents,
)

RECORDS = [
    {"id": 1, "title": "Refunds", "body": "  Refunds are processed within 5 business days. ", "url": "kb/refunds.md"},
    {"id": 2, "title": "Empty", "body": "   ", "url": "kb/empty.md"},
    {"id": 3, "title": "Shipping", "body": "We ship to the EU and the UK.", "url": "kb/shipping.md"},
]

LONG_TEXT = (
    "LangChain splits long documents into chunks. Each chunk is embedded separately. "
    "Overlap keeps sentences that cross a boundary searchable. "
    "Metadata travels with every chunk so answers can cite their sources. "
    "Small chunks give precise matches; large chunks give more context."
)


class CountingEmbeddings(HashingEmbeddings):
    def __init__(self):
        super().__init__(size=64)
        self.document_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return super().embed_documents(texts)


class RecordingStore(VectorStore):
    """Test double: records the kwargs the retriever passes to similarity_search."""

    def __init__(self):
        self.calls = []

    def similarity_search(self, query, k=4, **kwargs):
        self.calls.append({"query": query, "k": k, **kwargs})
        return [Document(f"hit {i}") for i in range(k)]

    @classmethod
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        return cls()


class SpyModel:
    def __init__(self, reply="answer [1]"):
        self.prompts = []

        def _call(prompt_value):
            self.prompts.append(prompt_value.to_messages())
            return AIMessage(reply)

        self.runnable = RunnableLambda(_call)


def fake_retriever(docs, calls=None):
    def _retrieve(question):
        if calls is not None:
            calls.append(question)
        return docs

    return RunnableLambda(_retrieve)


DOCS = [
    Document("Refunds take 5 days.", metadata={"source": "kb/refunds.md"}),
    Document("Refund requests need an order id.", metadata={"source": "kb/refunds.md"}),
    Document("We ship to the EU.", metadata={"source": "kb/shipping.md"}),
]


class TestTask1LoadDocuments:
    def test_maps_fields(self):
        docs = load_documents(RECORDS)
        assert len(docs) == 2
        assert docs[0].page_content == "Refunds are processed within 5 business days."
        assert docs[0].metadata == {"source": "kb/refunds.md", "title": "Refunds", "doc_id": 1}
        assert docs[0].id == "1"
        assert docs[1].id == "3"

    def test_empty(self):
        assert load_documents([]) == []


class TestTask2SplitDocuments:
    @staticmethod
    def parent():
        return Document(LONG_TEXT, metadata={"source": "guide.md", "title": "Guide"}, id="42")

    def test_chunk_size_and_metadata(self):
        chunks = split_documents([self.parent()], chunk_size=80, chunk_overlap=20)
        assert len(chunks) > 3
        for i, chunk in enumerate(chunks):
            assert len(chunk.page_content) <= 80
            assert chunk.metadata["source"] == "guide.md"
            assert chunk.metadata["title"] == "Guide"
            assert chunk.metadata["chunk_index"] == i
            assert chunk.id == f"42:{i}"

    def test_start_index_points_into_parent(self):
        for chunk in split_documents([self.parent()], chunk_size=80, chunk_overlap=20):
            start = chunk.metadata["start_index"]
            assert LONG_TEXT[start : start + len(chunk.page_content)] == chunk.page_content

    def test_overlap_repeats_text(self):
        chunks = split_documents([self.parent()], chunk_size=80, chunk_overlap=30)
        # with overlap, consecutive chunks overlap in the parent text
        first, second = chunks[0], chunks[1]
        assert second.metadata["start_index"] < first.metadata["start_index"] + len(first.page_content)

    def test_numbering_restarts_per_document_and_no_id(self):
        docs = [Document(LONG_TEXT, metadata={"source": "a"}), Document("short text", metadata={"source": "b"})]
        chunks = split_documents(docs, chunk_size=100, chunk_overlap=0)
        last = chunks[-1]
        assert last.metadata == {"source": "b", "start_index": 0, "chunk_index": 0}
        assert last.id is None
        assert docs[0].metadata == {"source": "a"}  # parent untouched

    def test_invalid_overlap(self):
        with pytest.raises(ValueError):
            split_documents([self.parent()], chunk_size=50, chunk_overlap=50)


class TestTask3VectorStoreAdd:
    def test_cosine_similarity(self):
        assert cosine_similarity([1, 0], [1, 0]) == pytest.approx(1.0)
        assert cosine_similarity([1, 0], [0, 1]) == pytest.approx(0.0)
        assert cosine_similarity([1, 1], [-1, -1]) == pytest.approx(-1.0)
        assert cosine_similarity([0, 0], [1, 1]) == 0.0
        with pytest.raises(ValueError):
            cosine_similarity([1], [1, 2])

    def test_add_documents_batches_and_assigns_ids(self):
        emb = CountingEmbeddings()
        store = SimpleVectorStore(emb)
        ids = store.add_documents([Document("a", id="doc-a"), Document("b")])
        assert emb.document_calls == [["a", "b"]]  # one batched call
        assert ids[0] == "doc-a"
        assert isinstance(ids[1], str) and len(ids[1]) == 32
        assert len(store) == 2

    def test_explicit_ids_and_upsert(self):
        store = SimpleVectorStore(HashingEmbeddings())
        store.add_documents([Document("old")], ids=["x"])
        store.add_documents([Document("new")], ids=["x"])
        assert len(store) == 1
        with pytest.raises(ValueError):
            store.add_documents([Document("a"), Document("b")], ids=["only-one"])

    def test_add_texts_comes_for_free(self):
        store = SimpleVectorStore.from_texts(["t1", "t2"], HashingEmbeddings(), metadatas=[{"n": 1}, {"n": 2}])
        assert len(store) == 2


class TestTask4VectorStoreSearch:
    @staticmethod
    def store():
        store = SimpleVectorStore(HashingEmbeddings())
        store.add_documents(DOCS, ids=["r1", "r2", "s1"])
        return store

    def test_exact_text_ranks_first_with_score_one(self):
        results = self.store().similarity_search_with_score("We ship to the EU.", k=2)
        assert len(results) == 2
        doc, score = results[0]
        assert doc.page_content == "We ship to the EU."
        assert doc.id == "s1"
        assert score == pytest.approx(1.0)
        assert results[0][1] >= results[1][1]

    def test_k_limits_results(self):
        store = self.store()
        assert len(store.similarity_search("anything", k=1)) == 1
        assert len(store.similarity_search("anything", k=10)) == 3
        assert store.similarity_search("anything", k=0) == []

    def test_dict_filter(self):
        docs = self.store().similarity_search("We ship to the EU.", k=5, filter={"source": "kb/refunds.md"})
        assert {d.metadata["source"] for d in docs} == {"kb/refunds.md"}
        assert len(docs) == 2

    def test_callable_filter(self):
        docs = self.store().similarity_search("x", k=5, filter=lambda d: "order" in d.page_content)
        assert [d.id for d in docs] == ["r2"]

    def test_empty_store(self):
        assert SimpleVectorStore(HashingEmbeddings()).similarity_search("q") == []


class TestTask5BuildRetriever:
    def test_passes_k(self):
        store = RecordingStore()
        retriever = build_retriever(store, k=2)
        assert isinstance(retriever, VectorStoreRetriever)
        assert len(retriever.invoke("question")) == 2
        assert store.calls == [{"query": "question", "k": 2}]

    def test_source_filter(self):
        store = RecordingStore()
        build_retriever(store, k=3, source="kb/refunds.md").invoke("q")
        assert store.calls[0]["filter"] == {"source": "kb/refunds.md"}

    def test_search_kwargs(self):
        retriever = build_retriever(RecordingStore(), k=5)
        assert retriever.search_kwargs == {"k": 5}


class TestTask6FormatDocs:
    def test_numbered_with_sources(self):
        assert format_docs(DOCS[:2] + [Document("No source here.")]) == (
            "[1] kb/refunds.md\nRefunds take 5 days.\n\n"
            "[2] kb/refunds.md\nRefund requests need an order id.\n\n"
            "[3] unknown\nNo source here."
        )

    def test_empty(self):
        assert format_docs([]) == NO_CONTEXT


class TestTask7RagChain:
    def test_final_prompt_contains_context_and_question(self):
        spy = SpyModel(reply="5 days [1]")
        chain = build_rag_chain(fake_retriever(DOCS[:1]), spy.runnable)
        assert chain.invoke("How long do refunds take?") == "5 days [1]"
        system, human = spy.prompts[0]
        assert system.type == "system"
        assert system.content.endswith("Context:\n[1] kb/refunds.md\nRefunds take 5 days.")
        assert "Cite sources as [n]" in system.content
        assert human.content == "How long do refunds take?"

    def test_retriever_receives_the_question(self):
        calls = []
        build_rag_chain(fake_retriever([], calls), FakeListChatModel(responses=["?"])).invoke("q?")
        assert calls == ["q?"]

    def test_no_documents(self):
        spy = SpyModel()
        build_rag_chain(fake_retriever([]), spy.runnable).invoke("q")
        assert spy.prompts[0][0].content.endswith(f"Context:\n{NO_CONTEXT}")


class TestTask8RagChainWithSources:
    def test_answer_and_unique_sources(self):
        chain = build_rag_chain_with_sources(fake_retriever(DOCS), FakeListChatModel(responses=["See [1]."]))
        assert chain.invoke("refunds?") == {
            "answer": "See [1].",
            "sources": ["kb/refunds.md", "kb/shipping.md"],
        }

    def test_retrieves_once_and_uses_docs_in_prompt(self):
        calls = []
        spy = SpyModel()
        build_rag_chain_with_sources(fake_retriever(DOCS[2:], calls), spy.runnable).invoke("ship?")
        assert calls == ["ship?"]
        assert "[1] kb/shipping.md\nWe ship to the EU." in spy.prompts[0][0].content
        assert spy.prompts[0][1].content == "ship?"

    def test_docs_without_source_are_skipped(self):
        chain = build_rag_chain_with_sources(fake_retriever([Document("x")]), FakeListChatModel(responses=["a"]))
        assert chain.invoke("q") == {"answer": "a", "sources": []}
