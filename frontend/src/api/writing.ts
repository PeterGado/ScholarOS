import { apiClient } from "../lib/apiClient";
import type { Page, PageParams } from "./pagination";
import {
  chatMessageListResponseSchema,
  chatReplyStatusResponseSchema,
  conversationListResponseSchema,
  conversationResponseSchema,
  memoryRecordListResponseSchema,
  memoryRecordResponseSchema,
  writingProfileViewResponseSchema,
  writingSegmentListResponseSchema,
  writingSegmentResponseSchema,
  writingStyleDocumentListResponseSchema,
  writingStyleDocumentResponseSchema,
  writingStyleProfileExtractionResponseSchema,
  type ChatMessageResponse,
  type ChatReplyStatusResponse,
  type ConversationResponse,
  type MemoryRecordResponse,
  type WritingProfileViewResponse,
  type WritingSegmentResponse,
  type WritingStyleDocumentResponse,
  type WritingStyleDocumentSummaryResponse,
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

export async function listWritingStyleDocuments(
  { limit, offset }: PageParams = {},
): Promise<Page<WritingStyleDocumentSummaryResponse>> {
  const response = await apiClient.get("/writing/style-profile/documents", { params: { limit, offset } });
  const parsed = writingStyleDocumentListResponseSchema.parse(response.data);
  return { items: parsed.documents, hasMore: parsed.has_more };
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

// --- Writing Segments (2026-10-02) ----------------------------------------------------------

export async function listWritingSegments(): Promise<WritingSegmentResponse[]> {
  const response = await apiClient.get("/writing/segments");
  return writingSegmentListResponseSchema.parse(response.data).segments;
}

export async function createWritingSegment(name: string, instructions: string): Promise<WritingSegmentResponse> {
  const response = await apiClient.post("/writing/segments", { name, instructions });
  return writingSegmentResponseSchema.parse(response.data);
}

export async function updateWritingSegment(
  segmentId: number,
  name: string,
  instructions: string,
): Promise<WritingSegmentResponse> {
  const response = await apiClient.patch(`/writing/segments/${segmentId}`, { name, instructions });
  return writingSegmentResponseSchema.parse(response.data);
}

export async function deleteWritingSegment(segmentId: number): Promise<void> {
  await apiClient.delete(`/writing/segments/${segmentId}`);
}

// --- Persistent Brain: Agent Workspace chat -------------------------------------------------

export async function startConversation(title?: string): Promise<ConversationResponse> {
  const response = await apiClient.post("/writing/conversations", { title: title || null });
  return conversationResponseSchema.parse(response.data);
}

export async function listConversations({ limit, offset }: PageParams = {}): Promise<Page<ConversationResponse>> {
  const response = await apiClient.get("/writing/conversations", { params: { limit, offset } });
  const parsed = conversationListResponseSchema.parse(response.data);
  return { items: parsed.conversations, hasMore: parsed.has_more };
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await apiClient.delete(`/writing/conversations/${conversationId}`);
}

export async function listConversationMessages(
  conversationId: number,
  { limit, offset }: PageParams = {},
): Promise<Page<ChatMessageResponse>> {
  const response = await apiClient.get(`/writing/conversations/${conversationId}/messages`, {
    params: { limit, offset },
  });
  const parsed = chatMessageListResponseSchema.parse(response.data);
  return { items: parsed.messages, hasMore: parsed.has_more };
}

export async function sendChatMessage(
  conversationId: number,
  content: string,
  segmentId?: number,
): Promise<ChatReplyStatusResponse> {
  const response = await apiClient.post(`/writing/conversations/${conversationId}/messages`, {
    content,
    segment_id: segmentId ?? null,
  });
  return chatReplyStatusResponseSchema.parse(response.data);
}

export async function getChatReplyStatus(
  conversationId: number,
  workItemId: number,
): Promise<ChatReplyStatusResponse> {
  const response = await apiClient.get(`/writing/conversations/${conversationId}/reply-status/${workItemId}`);
  return chatReplyStatusResponseSchema.parse(response.data);
}

export async function retryChatReply(
  conversationId: number,
  workItemId: number,
): Promise<ChatReplyStatusResponse> {
  const response = await apiClient.post(`/writing/conversations/${conversationId}/reply-status/${workItemId}/retry`);
  return chatReplyStatusResponseSchema.parse(response.data);
}

// --- Persistent Brain v2: Memory inspection -------------------------------------------------

export async function listMemory({ limit, offset }: PageParams = {}): Promise<Page<MemoryRecordResponse>> {
  const response = await apiClient.get("/writing/memory", { params: { limit, offset } });
  const parsed = memoryRecordListResponseSchema.parse(response.data);
  return { items: parsed.records, hasMore: parsed.has_more };
}

export async function supersedeMemoryRecord(
  recordId: number,
  content: string,
  rationale?: string,
): Promise<MemoryRecordResponse> {
  const response = await apiClient.post(`/writing/memory/${recordId}/supersede`, { content, rationale });
  return memoryRecordResponseSchema.parse(response.data);
}
