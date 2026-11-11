# Day 6

The most important part of building a knowledge product may not be the AI layer.

It’s the structure underneath it.

ScholarOS uses PostgreSQL in production, with SQLAlchemy for database access and Alembic to manage schema migrations. But using a relational database doesn’t automatically make a system safe: the application still has to enforce which user can access which records.

One layer I’ve added is PostgreSQL Row-Level Security (RLS). Tenant-owned records are filtered against the authenticated user at the database level, in addition to the ownership checks in the application.

That’s a technical control with a direct product consequence: a fast, intelligent response is not useful if it pulls from the wrong user’s data or loses the source that gave it meaning.

I’m learning to treat data boundaries as part of the product experience—not invisible engineering details to patch in later. What makes you trust a tool with important work: clear ownership, transparency, reliability, or something else?

#ProductBuilding #KnowledgeWork #BuildInPublic

