import { apiClient } from "../lib/apiClient";
import {
  researchDocumentListResponseSchema,
  researchDocumentResponseSchema,
  type ResearchDocumentResponse,
} from "./schemas";

export interface UploadResearchDocumentRequest {
  projectId: number;
  file: File;
  title: string;
  format: string;
  author?: string;
  source?: string;
}

export async function uploadResearchDocument(
  request: UploadResearchDocumentRequest,
): Promise<ResearchDocumentResponse> {
  const body = new FormData();
  body.append("file", request.file);
  body.append("title", request.title);
  body.append("format", request.format);
  if (request.author) body.append("author", request.author);
  if (request.source) body.append("source", request.source);

  const response = await apiClient.post(`/projects/${request.projectId}/documents`, body, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return researchDocumentResponseSchema.parse(response.data);
}

/**
 * Upload a selected group from one user action. Requests are deliberately sent in sequence:
 * firing a `Promise.all` of large multipart uploads both overwhelms a modest API deployment
 * and creates a burst of document-processing jobs against the AI provider.
 */
export async function uploadResearchDocuments(
  projectId: number,
  files: File[],
): Promise<ResearchDocumentResponse[]> {
  const uploaded: ResearchDocumentResponse[] = [];
  for (const file of files) {
    const extension = file.name.split(".").pop() ?? "txt";
    uploaded.push(
      await uploadResearchDocument({ projectId, file, title: file.name, format: extension }),
    );
  }
  return uploaded;
}

export async function listProjectDocuments(projectId: number): Promise<ResearchDocumentResponse[]> {
  const response = await apiClient.get(`/projects/${projectId}/documents`);
  return researchDocumentListResponseSchema.parse(response.data).documents;
}

export async function deleteResearchDocument(projectId: number, documentId: number): Promise<void> {
  await apiClient.delete(`/projects/${projectId}/documents/${documentId}`);
}

export async function retryResearchDocument(
  projectId: number,
  documentId: number,
): Promise<ResearchDocumentResponse> {
  const response = await apiClient.post(`/projects/${projectId}/documents/${documentId}/retry`);
  return researchDocumentResponseSchema.parse(response.data);
}
