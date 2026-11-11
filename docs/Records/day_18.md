# Day 18

Fast answers are useful. Answers you can inspect and understand are more useful.

There are two different kinds of trust to think about in an AI product.

First: can I trace an answer back to the source material? ScholarOS attaches evidence links to retrieved knowledge chunks so the source document can be surfaced with the result.

Second: is the data itself isolated correctly? The production database uses PostgreSQL Row-Level Security, alongside application-level ownership checks, to restrict access to user-owned records.

Neither is a magic guarantee. Source links help a person verify relevance; RLS is one enforcement layer in a broader security design. But both are more useful than asking people to trust a polished response without visibility into its basis or boundaries.

What would you need to see before trusting an AI tool with important work?

#AI #Trust #KnowledgeWork
