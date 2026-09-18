import { describe, expect, it } from "vitest";
import { agentWorkspaceResponseSchema, searchResponseSchema } from "./schemas";

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

describe("searchResponseSchema", () => {
  it("accepts an empty results list", () => {
    expect(() => searchResponseSchema.parse({ results: [] })).not.toThrow();
  });
});
