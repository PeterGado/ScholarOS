import { Link } from "react-router-dom";
import { BookOpenIcon, BrainIcon, MagnifyingGlassIcon, PencilLineIcon } from "@phosphor-icons/react";
import { useAuth } from "@/lib/AuthContext";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const features = [
  {
    icon: BookOpenIcon,
    title: "Document intelligence",
    description:
      "Upload your literature and source documents. ScholarOS reads them and organizes what it finds into structured, searchable knowledge - not just a pile of PDFs.",
    tint: "bg-accent/10 dark:bg-accent/15",
    span: "sm:col-span-2",
  },
  {
    icon: BrainIcon,
    title: "Project memory",
    description:
      "It remembers your decisions, terminology, and direction across the whole project, not just one conversation - so you never have to re-explain your own research.",
    tint: "",
    span: "sm:col-span-1",
  },
  {
    icon: MagnifyingGlassIcon,
    title: "Grounded retrieval",
    description:
      "Answers and drafts are grounded in the sources you've actually uploaded, with the evidence pulled in at the right moment - not generic, ungrounded text.",
    tint: "",
    span: "sm:col-span-1",
  },
  {
    icon: PencilLineIcon,
    title: "Your writing style, preserved",
    description:
      "ScholarOS learns your own voice so drafts sound like you wrote them, keeping intellectual ownership of the work where it belongs.",
    tint: "bg-primary/5 dark:bg-primary/10",
    span: "sm:col-span-2",
  },
];

export function LandingPage() {
  // 2026-09-30: this used to redirect an already-authenticated visitor straight past the
  // landing page to /chat - explicitly changed after real feedback that the landing page
  // should always be reachable as the first page, logged in or not, with a way in from here
  // rather than an automatic skip.
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-dvh bg-background">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <span className="text-lg font-semibold">ScholarOS</span>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          {isAuthenticated ? (
            <Button asChild>
              <Link to="/chat">Go to your workspace</Link>
            </Button>
          ) : (
            <>
              <Button variant="ghost" asChild>
                <Link to="/login">Sign in</Link>
              </Button>
              <Button asChild>
                <Link to="/register">Get started</Link>
              </Button>
            </>
          )}
        </div>
      </header>

      <main>
        <section className="mx-auto grid max-w-5xl gap-10 px-6 pt-10 pb-20 lg:grid-cols-2 lg:items-center lg:pt-16">
          <div>
            <p className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
              Research. Reason. Write.
            </p>
            <h1 className="mt-4 text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              An intelligent research operating system for academic writing
            </h1>
            <p className="mt-6 max-w-[42ch] text-lg text-muted-foreground text-balance">
              Upload your sources and style, and ScholarOS grounds every draft in them, so the
              writing stays provably yours.
            </p>
            <div className="mt-8 flex items-center gap-3">
              {isAuthenticated ? (
                <Button size="lg" asChild>
                  <Link to="/chat">Go to your workspace</Link>
                </Button>
              ) : (
                <>
                  <Button size="lg" asChild>
                    <Link to="/register">Get started</Link>
                  </Button>
                  <Button size="lg" variant="outline" asChild>
                    <Link to="/login">Sign in</Link>
                  </Button>
                </>
              )}
            </div>
          </div>

          {/* CSS-only abstract composition, not a product screenshot or mockup - no
              image-generation tool is available in this environment, and stock placeholder
              photography doesn't fit a research tool's brand. Three layered, rotated panels in
              the brand palette plus two thin teal/navy accent lines. */}
          <div className="relative mx-auto aspect-square w-full max-w-sm lg:max-w-none" aria-hidden="true">
            <div className="absolute inset-8 rotate-[-4deg] rounded-xl bg-primary/10 dark:bg-primary/20" />
            <div className="absolute inset-12 rotate-[3deg] rounded-xl bg-accent/15 dark:bg-accent/25" />
            <div className="absolute inset-16 rounded-xl bg-card shadow-xl ring-1 ring-foreground/10" />
            <div className="absolute top-1/4 left-1/2 h-px w-24 -translate-x-1/2 bg-accent/60" />
            <div className="absolute bottom-1/4 left-1/2 h-px w-16 -translate-x-1/2 bg-primary/40" />
          </div>
        </section>

        <section className="border-t border-border bg-muted/30">
          <div className="mx-auto max-w-5xl px-6 py-10 sm:py-16">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              {features.map(({ icon: Icon, title, description, tint, span }) => (
                <Card key={title} className={`${span} ${tint}`}>
                  <CardHeader>
                    <Icon className="size-5 text-primary" />
                    <CardTitle className="mt-2">{title}</CardTitle>
                  </CardHeader>
                  <CardContent className="text-muted-foreground">{description}</CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-5xl px-6 py-10 sm:py-16">
          <p className="max-w-2xl text-muted-foreground">
            ScholarOS doesn't replace the researcher - it amplifies your thinking and cuts the
            repetitive work, while keeping the writing genuinely yours.
          </p>
        </section>
      </main>

      <footer className="border-t border-border px-6 py-8 text-sm text-muted-foreground">
        <div className="mx-auto flex max-w-5xl flex-col items-center gap-3 sm:flex-row sm:justify-between">
          <span>ScholarOS</span>
          <div className="flex gap-4">
            <Link to="/privacy" className="hover:text-foreground">
              Privacy
            </Link>
            <Link to="/terms" className="hover:text-foreground">
              Terms
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
