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

export async function listProjectDocuments(projectId: number): Promise<ResearchDocumentResponse[]> {
  const response = await apiClient.get(`/projects/${projectId}/documents`);
  return researchDocumentListResponseSchema.parse(response.data).documents;
}
