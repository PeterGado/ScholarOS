// Zod schemas mirroring the backend's Pydantic response shapes (see
// docs/Frontend_Implementation_Plan.md Sec3/Sec4 "Validation") - applied at the API boundary so a
// shape drift between this frontend and the real backend fails loudly instead of silently
// rendering `undefined`. Field names/optionality match backend/app/**/interface/schemas.py
// exactly; do not rename fields here to be more "frontend-idiomatic" - that would hide drift.
import { z } from "zod";

export const tokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
});
export type TokenResponse = z.infer<typeof tokenResponseSchema>;

export const agentResponseSchema = z.object({
  agent_id: z.number(),
  status: z.string(),
  created_at: z.string(),
});

export const projectResponseSchema = z.object({
  project_id: z.number(),
  agent_id: z.number(),
  title: z.string(),
  topic: z.string(),
  description: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
});

export const agentWorkspaceResponseSchema = z.object({
  agent: agentResponseSchema,
  project: projectResponseSchema,
});
export type AgentWorkspaceResponse = z.infer<typeof agentWorkspaceResponseSchema>;

export const researchDocumentResponseSchema = z.object({
  document_id: z.number(),
  project_id: z.number(),
  title: z.string(),
  author: z.string().nullable(),
  source: z.string().nullable(),
  format: z.string(),
  processing_status: z.string(),
  ingested_at: z.string(),
});
export type ResearchDocumentResponse = z.infer<typeof researchDocumentResponseSchema>;

export const researchDocumentListResponseSchema = z.object({
  documents: z.array(researchDocumentResponseSchema),
});

export const searchResultEvidenceResponseSchema = z.object({
  document_id: z.number(),
  document_title: z.string(),
});

export const searchResultResponseSchema = z.object({
  chunk_id: z.number(),
  content: z.string(),
  summary: z.string().nullable(),
  score: z.number(),
  evidence: z.array(searchResultEvidenceResponseSchema),
});
export type SearchResultResponse = z.infer<typeof searchResultResponseSchema>;

export const searchResponseSchema = z.object({
  results: z.array(searchResultResponseSchema),
});

export const writingStyleDocumentResponseSchema = z.object({
  document_id: z.number(),
  title: z.string(),
  author: z.string().nullable(),
  source: z.string().nullable(),
  format: z.string(),
  processing_status: z.string(),
  ingested_at: z.string(),
  profile_id: z.number(),
  profile_name: z.string(),
});
export type WritingStyleDocumentResponse = z.infer<typeof writingStyleDocumentResponseSchema>;

export const profileCharacteristicResponseSchema = z.object({
  characteristic_id: z.number(),
  characteristic_type: z.string(),
  signal: z.string(),
  confidence: z.number().nullable(),
  source_document_ids: z.array(z.number()),
});

export const writingStyleProfileExtractionResponseSchema = z.object({
  profile_id: z.number(),
  profile_name: z.string(),
  characteristics: z.array(profileCharacteristicResponseSchema),
});
export type WritingStyleProfileExtractionResponse = z.infer<
  typeof writingStyleProfileExtractionResponseSchema
>;

export const writingProfileCharacteristicResponseSchema = z.object({
  characteristic_id: z.number(),
  characteristic_type: z.string(),
  signal: z.string(),
  confidence: z.number().nullable(),
});

export const writingProfileViewResponseSchema = z.object({
  profile_id: z.number(),
  profile_name: z.string(),
  characteristics: z.array(writingProfileCharacteristicResponseSchema),
});
export type WritingProfileViewResponse = z.infer<typeof writingProfileViewResponseSchema>;

export const draftResponseSchema = z.object({
  draft_id: z.number(),
  title: z.string(),
  target: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
});
export type DraftResponse = z.infer<typeof draftResponseSchema>;

export const draftListResponseSchema = z.object({
  drafts: z.array(draftResponseSchema),
});

export const draftEvidenceLinkResponseSchema = z.object({
  target_type: z.string(),
  chunk_id: z.number().nullable(),
  document_id: z.number().nullable(),
});

export const draftVersionResponseSchema = z.object({
  version_id: z.number(),
  version_number: z.number(),
  content: z.string(),
  created_at: z.string(),
  created_by: z.string(),
  evidence: z.array(draftEvidenceLinkResponseSchema),
});
export type DraftVersionResponse = z.infer<typeof draftVersionResponseSchema>;

export const draftVersionListResponseSchema = z.object({
  versions: z.array(draftVersionResponseSchema),
});

export const generationStatusResponseSchema = z.object({
  draft_id: z.number(),
  work_item_id: z.number(),
  state: z.string(),
});
export type GenerationStatusResponse = z.infer<typeof generationStatusResponseSchema>;

export const reviewDecisionResponseSchema = z.object({
  decision_id: z.number(),
  review_id: z.number(),
  outcome: z.string(),
  rationale: z.string().nullable(),
  decided_at: z.string(),
});
export type ReviewDecisionResponse = z.infer<typeof reviewDecisionResponseSchema>;
