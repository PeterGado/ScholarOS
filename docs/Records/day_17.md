# Day 17

Search needs to understand two different things:

The words you remember—and the meaning you’re trying to find.

ScholarOS uses hybrid retrieval to combine those two signals. The lexical branch uses PostgreSQL full-text search (`tsvector`/`tsquery`, ranked with `ts_rank`); the semantic branch ranks stored embeddings using cosine similarity.

Sometimes you remember a specific name or technical term. Other times, you remember the idea but not the wording. A lexical-only search can miss the second case; semantic-only search can miss exact terms and quotations.

The two ranked lists are combined with Reciprocal Rank Fusion (RRF). RRF uses each result’s rank rather than trying to compare raw full-text and cosine scores, which are on different scales.

This is implemented in production today. It’s an MVP-scale approach: embeddings are stored as JSON-encoded vectors and ranked in application code, rather than using a dedicated vector database or pgvector. That trade-off keeps the deployment simpler, with a clear scaling limit to revisit if the corpus grows.

When you search your own notes or documents, do you usually remember the exact words—or only the idea? Which kind of search tends to let you down?

#Search #AI #ResearchTools
