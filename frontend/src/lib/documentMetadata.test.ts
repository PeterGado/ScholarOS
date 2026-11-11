import { describe, expect, it } from "vitest";
import {
  MAX_PUBLICATION_YEAR,
  MIN_PUBLICATION_YEAR,
  normalizeDoi,
  parseDocumentMetadata,
  type DocumentMetadataFormValues,
} from "./documentMetadata";

function values(overrides: Partial<DocumentMetadataFormValues> = {}): DocumentMetadataFormValues {
  return { title: "", author: "", year: "", doi: "", ...overrides };
}

describe("parseDocumentMetadata", () => {
  it("accepts an entirely blank metadata form (every field is optional)", () => {
    const result = parseDocumentMetadata(values());

    expect(result).toEqual({
      ok: true,
      value: { title: "", author: null, publicationYear: null, doi: null },
    });
  });

  it("trims text fields and treats blank optional fields as null", () => {
    const result = parseDocumentMetadata(
      values({ title: "  Coastal Erosion  ", author: "  Uadiale, O.  ", year: "  ", doi: "   " }),
    );

    expect(result).toEqual({
      ok: true,
      value: { title: "Coastal Erosion", author: "Uadiale, O.", publicationYear: null, doi: null },
    });
  });

  it("converts a valid year to a number", () => {
    const result = parseDocumentMetadata(values({ year: "2012" }));

    expect(result.ok && result.value.publicationYear).toBe(2012);
  });

  it("accepts the boundary years the backend accepts", () => {
    expect(parseDocumentMetadata(values({ year: String(MIN_PUBLICATION_YEAR) })).ok).toBe(true);
    expect(parseDocumentMetadata(values({ year: String(MAX_PUBLICATION_YEAR) })).ok).toBe(true);
  });

  it.each(["1e5", "2021.5", "2021abc", "-2012", " 20 12 "])(
    "rejects %s as a year instead of letting the server coerce it",
    (year) => {
      const result = parseDocumentMetadata(values({ year }));

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.year).toMatch(/four-digit year/);
    },
  );

  it.each(["999", "2101", "0"])("rejects an out-of-range year (%s)", (year) => {
    const result = parseDocumentMetadata(values({ year }));

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.year).toBe(
        `Enter a year between ${MIN_PUBLICATION_YEAR} and ${MAX_PUBLICATION_YEAR}.`,
      );
    }
  });

  it("accepts a bare DOI", () => {
    const result = parseDocumentMetadata(values({ doi: "10.1038/nphys1170" }));

    expect(result.ok && result.value.doi).toBe("10.1038/nphys1170");
  });

  it.each([
    "https://doi.org/10.1038/nphys1170",
    "http://dx.doi.org/10.1038/nphys1170",
    "doi:10.1038/nphys1170",
    "DOI: 10.1038/nphys1170",
  ])("normalizes the pasted form %s to the canonical DOI", (doi) => {
    const result = parseDocumentMetadata(values({ doi }));

    expect(result.ok && result.value.doi).toBe("10.1038/nphys1170");
  });

  it.each(["not-a-doi", "10.1038", "11.1038/nphys1170", "10.103/nphys1170", "10.1038/n phys"])(
    "rejects %s as a DOI before any request is made",
    (doi) => {
      const result = parseDocumentMetadata(values({ doi }));

      expect(result.ok).toBe(false);
      if (!result.ok) expect(result.errors.doi).toMatch(/Enter a DOI like/);
    },
  );

  it("reports a year and a DOI error together rather than stopping at the first", () => {
    const result = parseDocumentMetadata(values({ year: "abc", doi: "nope" }));

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors.year).toBeDefined();
      expect(result.errors.doi).toBeDefined();
    }
  });
});

describe("normalizeDoi", () => {
  it("returns null for blank input", () => {
    expect(normalizeDoi("   ")).toBeNull();
  });

  it("leaves an already-canonical DOI untouched", () => {
    expect(normalizeDoi("10.1000/xyz123")).toBe("10.1000/xyz123");
  });
});
