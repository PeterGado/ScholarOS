# Day 9

Before a system can help with your information, it needs to know whose information it is.

In ScholarOS, a user’s documents, knowledge chunks, conversations, and memories are stored in PostgreSQL. In production, Row-Level Security policies use the authenticated user context to restrict access to tenant-owned rows.

RLS is not a replacement for application authorization. The app also checks ownership before it runs a use case; the database policy is an additional enforcement layer if a query misses an expected filter.

This is the kind of engineering decision that is easy to overlook in a feature demo, but it supports a basic user expectation: one person’s project data must not leak into another person’s workspace.

When you use a tool for important documents, what gives you confidence that your work is handled appropriately? Is there a security behavior or setting you look for first?

#ProductDesign #Trust #BuildInPublic
