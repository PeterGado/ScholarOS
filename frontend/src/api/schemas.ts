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
  error_message: z.string().nullable(),
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

export const writingStyleDocumentSummaryResponseSchema = z.object({
  document_id: z.number(),
  title: z.string(),
  author: z.string().nullable(),
  source: z.string().nullable(),
  format: z.string(),
  ingested_at: z.string(),
});
export type WritingStyleDocumentSummaryResponse = z.infer<typeof writingStyleDocumentSummaryResponseSchema>;

export const writingStyleDocumentListResponseSchema = z.object({
  documents: z.array(writingStyleDocumentSummaryResponseSchema),
});

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

// --- Persistent Brain: Agent Workspace chat -------------------------------------------------

export const conversationResponseSchema = z.object({
  conversation_id: z.number(),
  title: z.string().nullable(),
  status: z.string(),
  started_at: z.string(),
});
export type ConversationResponse = z.infer<typeof conversationResponseSchema>;

export const conversationListResponseSchema = z.object({
  conversations: z.array(conversationResponseSchema),
});

export const chatMessageResponseSchema = z.object({
  message_id: z.number(),
  sequence: z.number(),
  direction: z.string(),
  content: z.string(),
  created_at: z.string(),
});
export type ChatMessageResponse = z.infer<typeof chatMessageResponseSchema>;

export const chatMessageListResponseSchema = z.object({
  messages: z.array(chatMessageResponseSchema),
});

export const chatReplyStatusResponseSchema = z.object({
  conversation_id: z.number(),
  work_item_id: z.number(),
  state: z.string(),
  last_error: z.string().nullable().optional(),
});
export type ChatReplyStatusResponse = z.infer<typeof chatReplyStatusResponseSchema>;

// --- Persistent Brain v2: Memory inspection -------------------------------------------------

export const memoryProvenanceResponseSchema = z.object({
  source_type: z.string(),
  conversation_id: z.number().nullable(),
  element_id: z.number().nullable(),
  document_id: z.number().nullable(),
});

export const memoryRecordResponseSchema = z.object({
  record_id: z.number(),
  record_type: z.string(),
  content: z.string(),
  rationale: z.string().nullable(),
  status: z.string(),
  created_at: z.string(),
  created_by: z.string(),
  provenance: z.array(memoryProvenanceResponseSchema),
});
export type MemoryRecordResponse = z.infer<typeof memoryRecordResponseSchema>;

export const memoryRecordListResponseSchema = z.object({
  records: z.array(memoryRecordResponseSchema),
});
