import { z } from "zod";

// Client-side validation for the optional metadata on a single-document upload
// (DocumentsPage). Mirrors the backend's own constraints rather than inventing stricter ones:
// `publication_year` is `Form(None, ge=1000, le=2100)` (app/modules/document/interface/routes.py)
// and the title only has to be non-empty (app/modules/document/domain/entities.py) - the form
// already falls back to the filename for that, so there is nothing to reject there.
//
// Why this exists at all: the year input is `type="number"`, which the browser does not stop
// from containing `2021.5` or `1e5`, and no DOI shape was checked anywhere before the request
// went out. Both used to surface as the server's generic 422 (a whole import round trip) or, for
// a DOI, as a confusing "DOI not found" badge after processing rather than "that isn't a DOI".
export const MIN_PUBLICATION_YEAR = 1000;
export const MAX_PUBLICATION_YEAR = 2100;

// A DOI is `10.<4-9 digit registrant>/<suffix>`; the suffix may contain almost anything except
// whitespace. Deliberately shape-only - whether the DOI actually resolves is Crossref's job,
// checked later at processing time, not something this can or should decide.
const DOI_PATTERN = /^10\.\d{4,9}\/\S+$/;

// People copy DOIs from a paper, a browser bar, or a reference list - `https://doi.org/10.1038/
// nphys1170` and `doi:10.1038/nphys1170` are the same DOI as the bare form, and rejecting them
// for the prefix would be a false positive.
const DOI_PREFIX = /^(?:https?:\/\/(?:dx\.)?doi\.org\/|doi:\s*)/i;

export interface DocumentMetadataFormValues {
  title: string;
  author: string;
  year: string;
  doi: string;
}

export interface DocumentMetadata {
  title: string;
  author: string | null;
  publicationYear: number | null;
  doi: string | null;
}

export type DocumentMetadataField = "year" | "doi";
export type DocumentMetadataErrors = Partial<Record<DocumentMetadataField, string>>;

export type DocumentMetadataResult =
  | { ok: true; value: DocumentMetadata }
  | { ok: false; errors: DocumentMetadataErrors };

const documentMetadataSchema = z
  .object({
    title: z.string(),
    author: z.string(),
    year: z.string(),
    doi: z.string(),
  })
  .superRefine((values, ctx) => {
    const year = values.year.trim();
    if (year !== "") {
      // Digits only, then range - so `1e5`, `2021.5` and `2021abc` all get the same clear
      // message instead of being coerced into a number the API will reject.
      if (!/^\d+$/.test(year)) {
        ctx.addIssue({ code: "custom", path: ["year"], message: "Enter a four-digit year like 2012." });
      } else if (Number(year) < MIN_PUBLICATION_YEAR || Number(year) > MAX_PUBLICATION_YEAR) {
        ctx.addIssue({
          code: "custom",
          path: ["year"],
          message: `Enter a year between ${MIN_PUBLICATION_YEAR} and ${MAX_PUBLICATION_YEAR}.`,
        });
      }
    }

    const doi = normalizeDoi(values.doi);
    if (doi !== null && !DOI_PATTERN.test(doi)) {
      ctx.addIssue({ code: "custom", path: ["doi"], message: "Enter a DOI like 10.1038/nphys1170." });
    }
  });

export function normalizeDoi(raw: string): string | null {
  const stripped = raw.trim().replace(DOI_PREFIX, "").trim();
  return stripped === "" ? null : stripped;
}

/**
 * Validates and normalizes the upload form's metadata fields. Blank optional fields become
 * null, whitespace is trimmed, and DOI prefixes are stripped so the backend stores the canonical
 * form. Returns every field error at once rather than stopping at the first one.
 */
export function parseDocumentMetadata(values: DocumentMetadataFormValues): DocumentMetadataResult {
  const result = documentMetadataSchema.safeParse(values);
  if (!result.success) {
    const errors: DocumentMetadataErrors = {};
    for (const issue of result.error.issues) {
      const [field] = issue.path;
      if ((field === "year" || field === "doi") && errors[field] === undefined) {
        errors[field] = issue.message;
      }
    }
    return { ok: false, errors };
  }

  const year = result.data.year.trim();
  return {
    ok: true,
    value: {
      title: result.data.title.trim(),
      author: result.data.author.trim() || null,
      publicationYear: year === "" ? null : Number(year),
      doi: normalizeDoi(result.data.doi),
    },
  };
}
