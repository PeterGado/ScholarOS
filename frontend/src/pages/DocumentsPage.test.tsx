import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DocumentsPage } from "./DocumentsPage";
import { ToastProvider } from "@/lib/ToastContext";
import * as documentsApi from "@/api/documents";
import type { AgentWorkspaceResponse, ResearchDocumentResponse } from "@/api/schemas";

// Only the wiring is under test here - that invalid metadata is caught before any request is
// made, and that valid metadata is normalized on its way into the request. The validation rules
// themselves are covered exhaustively by src/lib/documentMetadata.test.ts.
vi.mock("@/api/documents");
vi.mock("@/api/knowledge");

const workspace: AgentWorkspaceResponse = {
  agent: { agent_id: 1, status: "active", created_at: "2026-01-01T00:00:00Z" },
  project: {
    project_id: 7,
    agent_id: 1,
    title: "Thesis",
    topic: "Topic",
    description: null,
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
  },
};

const uploadedDocument: ResearchDocumentResponse = {
  document_id: 1,
  project_id: 7,
  title: "source.txt",
  author: null,
  source: null,
  publication_year: null,
  doi: null,
  doi_verification_status: null,
  format: "txt",
  processing_status: "pending",
  ingested_at: "2026-01-01T00:00:00Z",
  error_message: null,
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/documents"]}>
          <Routes>
            {/* DocumentsPage reads its workspace from the layout route's outlet context,
                exactly as AppShell provides it. */}
            <Route element={<Outlet context={workspace} />}>
              <Route path="/documents" element={<DocumentsPage />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

async function selectFile(container: HTMLElement, file: File) {
  const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
  expect(fileInput).not.toBeNull();
  await userEvent.upload(fileInput!, file);
}

function submitUploadForm() {
  // fireEvent.submit, not a click on the submit button: the form's file input is `required`, and
  // jsdom does not reflect a selected File into the input's `value`, so native constraint
  // validation blocks the click before onSubmit ever runs (a real browser does not). This still
  // exercises the real handler - the thing under test - without that jsdom-only gate.
  const form = screen.getByRole("button", { name: /Upload/ }).closest("form");
  expect(form).not.toBeNull();
  fireEvent.submit(form!);
}

async function fillAndSubmit(doi: string, year: string) {
  if (doi !== "") await userEvent.type(screen.getByLabelText("DOI (optional)"), doi);
  if (year !== "") await userEvent.type(screen.getByLabelText("Year (optional)"), year);
  submitUploadForm();
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(documentsApi.listProjectDocuments).mockResolvedValue({ items: [], hasMore: false });
  vi.mocked(documentsApi.uploadResearchDocument).mockResolvedValue(uploadedDocument);
  vi.mocked(documentsApi.uploadResearchDocuments).mockResolvedValue([uploadedDocument]);
});

describe("DocumentsPage upload metadata validation", () => {
  it("rejects a malformed DOI under its own field, without making an upload request", async () => {
    const { container } = renderPage();
    await selectFile(container, new File(["content"], "source.txt", { type: "text/plain" }));

    await fillAndSubmit("not-a-doi", "");

    expect(await screen.findByText("Enter a DOI like 10.1038/nphys1170.")).toBeInTheDocument();
    expect(documentsApi.uploadResearchDocument).not.toHaveBeenCalled();
  });

  it("rejects a year the API would refuse (1e5) before sending anything", async () => {
    // <input type="number"> accepts exponent notation, which Number() happily turns into
    // 100000 - a value the backend's ge=1000/le=2100 bound rejects with a generic 422.
    const { container } = renderPage();
    await selectFile(container, new File(["content"], "source.txt", { type: "text/plain" }));

    await fillAndSubmit("", "1e5");

    expect(await screen.findByText("Enter a year between 1000 and 2100.")).toBeInTheDocument();
    expect(documentsApi.uploadResearchDocument).not.toHaveBeenCalled();
  });

  it("sends the canonical DOI and the numeric year once both are valid", async () => {
    const { container } = renderPage();
    await selectFile(container, new File(["content"], "source.txt", { type: "text/plain" }));

    await fillAndSubmit("https://doi.org/10.1038/nphys1170", "2012");

    await waitFor(() => expect(documentsApi.uploadResearchDocument).toHaveBeenCalledTimes(1));
    expect(documentsApi.uploadResearchDocument).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: 7,
        title: "source.txt", // falls back to the filename when no title was typed
        doi: "10.1038/nphys1170",
        publicationYear: 2012,
        author: undefined,
      }),
    );
  });

  it("does not apply single-document metadata validation to a multi-file upload", async () => {
    // The metadata inputs are disabled for multi-file uploads (each file keeps its filename),
    // so an earlier bad value left in the year field must not block that path.
    const { container } = renderPage();
    await selectFile(container, new File(["content"], "source.txt", { type: "text/plain" }));
    await userEvent.type(screen.getByLabelText("Year (optional)"), "1e5");

    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    await userEvent.upload(fileInput!, [
      new File(["a"], "a.txt", { type: "text/plain" }),
      new File(["b"], "b.txt", { type: "text/plain" }),
    ]);
    submitUploadForm();

    await waitFor(() => expect(documentsApi.uploadResearchDocuments).toHaveBeenCalledTimes(1));
    expect(documentsApi.uploadResearchDocument).not.toHaveBeenCalled();
  });
});
