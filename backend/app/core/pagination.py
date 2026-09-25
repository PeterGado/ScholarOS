DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
"""Shared offset/limit defaults for every paginated list endpoint (2026-09-23, real-traffic
audit: GET /writing/memory, GET /writing/conversations,
GET /writing/conversations/{id}/messages, GET /projects/{id}/documents,
GET /writing/style-profile/documents - the first pagination in this app). One shared pair
rather than each endpoint repeating its own literals, mirroring how `DEFAULT_TOP_K`/`MAX_TOP_K`
(app.modules.knowledge.application.retrieval) already anchor knowledge search's own bound.
"""
