import { apiClient } from "../lib/apiClient";
import {
  chatMessageListResponseSchema,
  chatReplyStatusResponseSchema,
  conversationListResponseSchema,
  conversationResponseSchema,
  memoryRecordListResponseSchema,
  memoryRecordResponseSchema,
  writingProfileViewResponseSchema,
  writingStyleDocumentListResponseSchema,
  writingStyleDocumentResponseSchema,
  writingStyleProfileExtractionResponseSchema,
  type ChatMessageResponse,
  type ChatReplyStatusResponse,
  type ConversationResponse,
  type MemoryRecordResponse,
  type WritingProfileViewResponse,
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

export async function listWritingStyleDocuments(): Promise<WritingStyleDocumentSummaryResponse[]> {
  const response = await apiClient.get("/writing/style-profile/documents");
  return writingStyleDocumentListResponseSchema.parse(response.data).documents;
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

// --- Persistent Brain: Agent Workspace chat -------------------------------------------------

export async function startConversation(title?: string): Promise<ConversationResponse> {
  const response = await apiClient.post("/writing/conversations", { title: title || null });
  return conversationResponseSchema.parse(response.data);
}

export async function listConversations(): Promise<ConversationResponse[]> {
  const response = await apiClient.get("/writing/conversations");
  return conversationListResponseSchema.parse(response.data).conversations;
}

export async function deleteConversation(conversationId: number): Promise<void> {
  await apiClient.delete(`/writing/conversations/${conversationId}`);
}

export async function listConversationMessages(conversationId: number): Promise<ChatMessageResponse[]> {
  const response = await apiClient.get(`/writing/conversations/${conversationId}/messages`);
  return chatMessageListResponseSchema.parse(response.data).messages;
}

export async function sendChatMessage(conversationId: number, content: string): Promise<ChatReplyStatusResponse> {
  const response = await apiClient.post(`/writing/conversations/${conversationId}/messages`, { content });
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

export async function listMemory(): Promise<MemoryRecordResponse[]> {
  const response = await apiClient.get("/writing/memory");
  return memoryRecordListResponseSchema.parse(response.data).records;
}

export async function supersedeMemoryRecord(
  recordId: number,
  content: string,
  rationale?: string,
): Promise<MemoryRecordResponse> {
  const response = await apiClient.post(`/writing/memory/${recordId}/supersede`, { content, rationale });
  return memoryRecordResponseSchema.parse(response.data);
}
