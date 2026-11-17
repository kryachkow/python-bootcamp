# 5.5 Retrieval & RAG

Retrieval-augmented generation answers questions from *your* data: load
documents, split them into chunks, embed and index the chunks, retrieve the
most similar ones for a question, and put them into the prompt with citations.
You implement each stage, including a small `VectorStore`, so you can see what
PGVector, Chroma & co. plug into.

## Concepts

| Tool | Use it for |
|------|------------|
| `Document(page_content, metadata, id)` | a unit of text plus where it came from |
| `RecursiveCharacterTextSplitter(chunk_size, chunk_overlap, add_start_index=True)` | chunks that respect paragraphs and sentences; metadata is copied to each chunk |
| `Embeddings.embed_documents` / `embed_query` | text to vectors (batch the documents!) |
| `VectorStore` subclass | implement `add_documents`, `similarity_search(_with_score)`, `from_texts`; get `add_texts`, `as_retriever` for free |
| `store.as_retriever(search_kwargs={"k": 4, "filter": ...})` | a `Runnable[str, list[Document]]` |
| `{"context": retriever \| format_docs, "question": RunnablePassthrough()}` | the classic RAG input map |

About the fake embeddings: `HashingEmbeddings` (given in `exercise.py`) hashes
words into buckets. It is deterministic and offline but lexical, not semantic,
so the tests only rely on exact-text matches (score 1.0) and on structure, not
on "meaningful" ranking. With a real model you would swap in
`OpenAIEmbeddings()` / `AzureOpenAIEmbeddings(...)` and nothing else changes.
(`langchain_core`'s own `DeterministicFakeEmbedding` and `InMemoryVectorStore`
need `numpy`, which this repo does not install.)

## Tasks

All tasks are in [`exercise.py`](exercise.py).

| # | Task | What you practise |
|---|------|-------------------|
| 1 | `load_documents` | `Document` with metadata and ids |
| 2 | `split_documents` | `RecursiveCharacterTextSplitter`, `start_index`, stable chunk ids |
| 3 | `cosine_similarity`, `SimpleVectorStore.add_documents` | the `Embeddings` interface, batching, upserts |
| 4 | `SimpleVectorStore.similarity_search(_with_score)` | ranking, `k`, metadata filters |
| 5 | `build_retriever` | `as_retriever(search_kwargs=...)` |
| 6 | `format_docs` | numbered context with source citations |
| 7 | `build_rag_chain` | the LCEL RAG chain, checked with a spy model |
| 8 | `build_rag_chain_with_sources` | retrieve once, return answer and sources |

## Run the tests

```bash
uv run pytest m05_langchain/e05_retrieval_rag
uv run pytest m05_langchain/e05_retrieval_rag -k Task4   # one task only
```

No API keys needed.

## Further reading

- [Retrieval](https://python.langchain.com/docs/concepts/retrieval/)
- [Text splitters](https://python.langchain.com/docs/concepts/text_splitters/)
- [Build a RAG app](https://python.langchain.com/docs/tutorials/rag/)
