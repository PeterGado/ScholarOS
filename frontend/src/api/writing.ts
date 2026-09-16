import { apiClient } from "../lib/apiClient";
import {
  draftListResponseSchema,
  draftResponseSchema,
  draftVersionListResponseSchema,
  generationStatusResponseSchema,
  reviewDecisionResponseSchema,
  writingProfileViewResponseSchema,
  writingStyleDocumentResponseSchema,
  writingStyleProfileExtractionResponseSchema,
  type DraftResponse,
  type DraftVersionResponse,
  type GenerationStatusResponse,
  type ReviewDecisionResponse,
  type WritingProfileViewResponse,
  type WritingStyleDocumentResponse,
  type WritingStyleProfileExtractionResponse,
} from "./schemas";

export interface UploadWritingStyleDocumentRequest {
  file: File;
  title: string;
  format: string;
  author?: string;
  source?: string;
}

export async function uploadWritingStyleDocument(
  request: UploadWritingStyleDocumentRequest,
): Promise<WritingStyleDocumentResponse> {
  const body = new FormData();
  body.append("file", request.file);
  body.append("title", request.title);
  body.append("format", request.format);
  if (request.author) body.append("author", request.author);
  if (request.source) body.append("source", request.source);

  const response = await apiClient.post("/writing/style-profile/documents", body, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return writingStyleDocumentResponseSchema.parse(response.data);
}

export async function extractWritingStyleProfile(
  documentIds: number[],
): Promise<WritingStyleProfileExtractionResponse> {
  const response = await apiClient.post("/writing/style-profile/extract", { document_ids: documentIds });
  return writingStyleProfileExtractionResponseSchema.parse(response.data);
}

export async function getWritingProfile(): Promise<WritingProfileViewResponse> {
  const response = await apiClient.get("/writing/style-profile");
  return writingProfileViewResponseSchema.parse(response.data);
}

export async function createDraft(title: string, target?: string): Promise<DraftResponse> {
  const response = await apiClient.post("/writing/drafts", { title, target });
  return draftResponseSchema.parse(response.data);
}

export async function listDrafts(): Promise<DraftResponse[]> {
  const response = await apiClient.get("/writing/drafts");
  return draftListResponseSchema.parse(response.data).drafts;
}

export async function getDraft(draftId: number): Promise<DraftResponse> {
  const response = await apiClient.get(`/writing/drafts/${draftId}`);
  return draftResponseSchema.parse(response.data);
}

export async function requestDraftGeneration(
  draftId: number,
  instructions: string,
): Promise<GenerationStatusResponse> {
  const response = await apiClient.post(`/writing/drafts/${draftId}/generate`, { instructions });
  return generationStatusResponseSchema.parse(response.data);
}

export async function listDraftVersions(draftId: number): Promise<DraftVersionResponse[]> {
  const response = await apiClient.get(`/writing/drafts/${draftId}/versions`);
  return draftVersionListResponseSchema.parse(response.data).versions;
}

export type ReviewOutcome = "approved" | "revisions_requested" | "rejected";

export async function submitDraftReview(
  draftId: number,
  versionId: number,
  outcome: ReviewOutcome,
  options?: { rationale?: string; notes?: string },
): Promise<ReviewDecisionResponse> {
  const response = await apiClient.post(`/writing/drafts/${draftId}/versions/${versionId}/reviews`, {
    outcome,
    rationale: options?.rationale,
    notes: options?.notes,
  });
  return reviewDecisionResponseSchema.parse(response.data);
}
