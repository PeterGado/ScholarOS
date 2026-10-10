import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

const LAST_UPDATED = "October 6, 2026";
const CONTACT_EMAIL = "peter.favour.gado@gmail.com";

// Real terms of service (2026-10-06), replacing the earlier placeholder. Governing law /
// jurisdiction is deliberately left unstated below - that's a real legal decision for the
// project owner to make, not something to invent. This is a careful draft, not a substitute
// for review by a qualified lawyer before relying on it commercially.
export function TermsPage() {
  useDocumentTitle("Terms of Service");
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" />
        Back to home
      </Link>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Terms of service</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated {LAST_UPDATED}</p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-muted-foreground">
        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Agreement</h2>
          <p>
            By creating an account or using ScholarOS, you agree to these terms. If you don't
            agree, don't use the service.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            What ScholarOS is
          </h2>
          <p>
            ScholarOS is an AI writing assistant for academic research. It reads documents you
            upload, learns your writing style from samples you provide, and generates draft
            writing grounded in that material. It's in active early-stage development.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Your account</h2>
          <p>
            You're responsible for the security of your own account and for everything that
            happens under it. Use a real password, keep it to yourself, and tell us if you think
            someone else has access to your account. Registration may require an invite code
            while the service is in early access.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Acceptable use</h2>
          <p>Don't use ScholarOS to:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Upload content you don't have the right to upload.</li>
            <li>Generate or distribute illegal, infringing, or abusive content.</li>
            <li>Attempt to bypass rate limits, usage caps, or access controls.</li>
            <li>Scrape, reverse-engineer, or extract the underlying system beyond normal use.</li>
          </ul>
          <p>We may suspend or terminate an account that does any of these.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Your content</h2>
          <p>
            You keep ownership of everything you upload and write. Using ScholarOS requires
            giving us permission to process that content (store it, send it to our AI provider,
            analyze it) solely to provide the service back to you - we don't use your content to
            train models, and we don't sell it.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            AI-generated content
          </h2>
          <p>
            ScholarOS grounds its replies in the research evidence you've actually uploaded where
            possible, and is built to flag when a citation can't be verified against that
            evidence. Even so, AI-generated text can be wrong. You're responsible for reviewing
            and verifying anything ScholarOS produces before you rely on it, cite it, or submit
            it anywhere - it isn't a substitute for your own academic judgment.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Service availability
          </h2>
          <p>
            ScholarOS is provided on a best-effort basis with no uptime guarantee at this stage.
            Features may change as the product develops.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Ending your account
          </h2>
          <p>
            You can reset your workspace data yourself at any time from Settings, or request full
            account deletion by emailing{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-foreground underline underline-offset-4">
              {CONTACT_EMAIL}
            </a>
            . We may suspend or terminate accounts that violate these terms.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Disclaimers and liability
          </h2>
          <p>
            ScholarOS is provided "as is," without warranties of any kind. To the fullest extent
            the law allows, we aren't liable for damages arising from your use of the service,
            including reliance on AI-generated content.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Governing law</h2>
          <p>
            The governing law and jurisdiction for these terms will be specified here once
            finalized.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Changes to these terms
          </h2>
          <p>
            If these terms change in a way that matters, we'll update the date at the top of this
            page.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Contact</h2>
          <p>
            Questions about these terms:{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-foreground underline underline-offset-4">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </section>
      </div>
    </div>
  );
}
