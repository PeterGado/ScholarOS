import { Link } from "react-router-dom";
import { ArrowLeftIcon } from "@phosphor-icons/react";

const LAST_UPDATED = "October 6, 2026";
const CONTACT_EMAIL = "peter.favour.gado@gmail.com";

// Real privacy policy (2026-10-06), replacing the earlier placeholder. Every claim below
// describes ScholarOS's actual current implementation, confirmed against the real code - not
// generic template language. Governing law/jurisdiction is deliberately left unstated (see
// TermsPage.tsx's matching note) since that's a real legal decision, not something to invent.
// This is a careful draft, not a substitute for review by a qualified lawyer before relying on
// it commercially.
export function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <Link to="/" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeftIcon className="size-4" />
        Back to home
      </Link>
      <h1 className="mt-6 text-2xl font-semibold tracking-tight">Privacy policy</h1>
      <p className="mt-2 text-sm text-muted-foreground">Last updated {LAST_UPDATED}</p>

      <div className="mt-8 space-y-8 text-sm leading-relaxed text-muted-foreground">
        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">What this covers</h2>
          <p>
            This policy explains what ScholarOS collects, why, and who it's shared with. It
            describes what the product actually does today, not a generic template - if a
            practice changes, this page changes with it.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Information we collect</h2>
          <p>
            <strong className="text-foreground">Account information.</strong> A username and a
            password, which is hashed before storage - we never store or can see your actual
            password. An email address is optional and used for exactly one thing: sending you a
            password reset link if you ask for one.
          </p>
          <p>
            <strong className="text-foreground">Google Sign-In (if you use it).</strong> Google
            provides us your email and basic profile information via a signed identity token. We
            don't receive your Google password or anything else from your Google account.
          </p>
          <p>
            <strong className="text-foreground">Content you provide.</strong> Research documents
            and writing samples you upload, your project details, and the messages you send in
            chat. This is the material the product exists to work with.
          </p>
          <p>
            <strong className="text-foreground">Content we generate from your activity.</strong>{" "}
            As you use ScholarOS, it extracts a writing style profile from your samples and
            "memory" records (decisions, terminology, direction) from your conversations, so it
            doesn't need to be re-explained things you've already told it.
          </p>
          <p>
            <strong className="text-foreground">Usage data.</strong> How much AI capacity your
            account has used, kept only to enforce fair-use limits and prevent abuse.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Who we share it with
          </h2>
          <p>
            We don't sell your data. We share it with the following services, only as needed to
            run the product:
          </p>
          <ul className="list-disc space-y-1 pl-5">
            <li>
              <strong className="text-foreground">Our AI provider</strong> (currently Google
              Gemini) - your conversation content, project context, and relevant excerpts from
              your uploaded documents are sent there to generate replies.
            </li>
            <li>
              <strong className="text-foreground">Resend</strong> - your email address and a
              one-time reset link, only when you actually request a password reset.
            </li>
            <li>
              <strong className="text-foreground">Crossref</strong> - only the DOI string itself
              from a document you upload with one, to verify it against the public scholarly
              record. No personal data is sent.
            </li>
            <li>
              <strong className="text-foreground">Our cloud storage provider</strong> - the files
              you upload are stored there.
            </li>
            <li>
              <strong className="text-foreground">Google</strong> - only if you choose Google
              Sign-In, to verify your identity.
            </li>
          </ul>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Cookies</h2>
          <p>
            ScholarOS itself sets no cookies. You stay signed in via a token stored in your
            browser's local storage, not a cookie, and we run no analytics or tracking scripts of
            any kind. If you sign in with Google, Google's own sign-in script - loaded from
            Google's servers, outside our control - may set its own cookies as part of that flow.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Data retention and deletion
          </h2>
          <p>
            You can permanently delete your project, documents, extracted knowledge, writing
            style, memory, and conversations yourself at any time from Settings - this takes
            effect immediately and can't be undone. To delete your account entirely, email{" "}
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-foreground underline underline-offset-4">
              {CONTACT_EMAIL}
            </a>
            .
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Security</h2>
          <p>
            Passwords are hashed, never stored in plain text. Every user's data is isolated at
            the database level, so one account's rows are never visible to another's queries.
            Traffic to ScholarOS is served over HTTPS only.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Children</h2>
          <p>ScholarOS isn't directed at, or knowingly used by, children under 13.</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">
            Changes to this policy
          </h2>
          <p>
            If this policy changes in a way that matters, we'll update the date at the top of
            this page.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-base font-semibold tracking-tight text-foreground">Contact</h2>
          <p>
            Questions about this policy or your data:{" "}
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
