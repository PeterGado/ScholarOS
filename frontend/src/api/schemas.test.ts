import { describe, expect, it } from "vitest";
import {
  agentWorkspaceResponseSchema,
  draftVersionResponseSchema,
  generationStatusResponseSchema,
  searchResponseSchema,
} from "./schemas";

// These fixtures are hand-copied from the real Pydantic response shapes
// (backend/app/**/interface/schemas.py) - if the backend contract drifts, these should be the
// first thing to fail, per docs/Frontend_Implementation_Plan.md's validation rationale.

describe("agentWorkspaceResponseSchema", () => {
  it("accepts a real POST /agents response shape", () => {
    const body = {
      agent: { agent_id: 1, status: "active", created_at: "2026-09-16T00:00:00Z" },
      project: {
        project_id: 1,
        agent_id: 1,
        title: "Thesis",
        topic: "Coastal erosion",
        description: null,
        status: "active",
        created_at: "2026-09-16T00:00:00Z",
      },
    };
    expect(() => agentWorkspaceResponseSchema.parse(body)).not.toThrow();
  });
});

describe("draftVersionResponseSchema", () => {
  it("accepts a version with evidence links of both target types", () => {
    const body = {
      version_id: 5,
      version_number: 1,
      content: "Generated text.",
      created_at: "2026-09-16T00:00:00Z",
      created_by: "system",
      evidence: [
        { target_type: "knowledge_chunk", chunk_id: 7, document_id: null },
        { target_type: "research_document", chunk_id: null, document_id: 3 },
      ],
    };
    expect(() => draftVersionResponseSchema.parse(body)).not.toThrow();
  });
});

describe("generationStatusResponseSchema", () => {
  it("accepts the 202 response shape from POST /writing/drafts/{id}/generate", () => {
    const body = { draft_id: 1, work_item_id: 9, state: "queued" };
    expect(() => generationStatusResponseSchema.parse(body)).not.toThrow();
  });
});

describe("searchResponseSchema", () => {
  it("accepts an empty results list", () => {
    expect(() => searchResponseSchema.parse({ results: [] })).not.toThrow();
  });
});
