import { Link, Navigate } from "react-router-dom";
import { BookOpen, Brain, PenLine, Search } from "lucide-react";
import { useAuth } from "@/lib/AuthContext";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const features = [
  {
    icon: BookOpen,
    title: "Document intelligence",
    description:
      "Upload your literature and source documents. ScholarOS reads them and organizes what it finds into structured, searchable knowledge - not just a pile of PDFs.",
  },
  {
    icon: Brain,
    title: "Project memory",
    description:
      "It remembers your decisions, terminology, and direction across the whole project, not just one conversation - so you never have to re-explain your own research.",
  },
  {
    icon: Search,
    title: "Grounded retrieval",
    description:
      "Answers and drafts are grounded in the sources you've actually uploaded, with the evidence pulled in at the right moment - not generic, ungrounded text.",
  },
  {
    icon: PenLine,
    title: "Your writing style, preserved",
    description:
      "ScholarOS learns your own voice so drafts sound like you wrote them, keeping intellectual ownership of the work where it belongs.",
  },
];

export function LandingPage() {
  const { isAuthenticated } = useAuth();

  if (isAuthenticated) {
    return <Navigate to="/chat" replace />;
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-6 py-6">
        <span className="text-lg font-semibold">ScholarOS</span>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <Button variant="ghost" asChild>
            <Link to="/login">Sign in</Link>
          </Button>
          <Button asChild>
            <Link to="/register">Get started</Link>
          </Button>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-3xl px-6 pt-16 pb-20 text-center">
          <p className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            Research. Reason. Write.
          </p>
          <h1 className="mt-4 text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
            An intelligent research operating system for academic writing
          </h1>
          <p className="mt-6 text-lg text-muted-foreground text-balance">
            ScholarOS helps you build real understanding of your research topic, literature, and
            institutional guidelines before you draft a single sentence - then writes with you in
            your own voice. Understand first. Write second.
          </p>
          <div className="mt-8 flex items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link to="/register">Get started</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/login">Sign in</Link>
            </Button>
          </div>
        </section>

        <section className="border-t border-border bg-muted/30">
          <div className="mx-auto max-w-5xl px-6 py-16">
            <div className="grid gap-4 sm:grid-cols-2">
              {features.map(({ icon: Icon, title, description }) => (
                <Card key={title}>
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

        <section className="mx-auto max-w-3xl px-6 py-16 text-center">
          <p className="text-muted-foreground">
            ScholarOS doesn't replace the researcher - it amplifies your thinking and cuts the
            repetitive work, while keeping the writing genuinely yours.
          </p>
        </section>
      </main>

      <footer className="border-t border-border px-6 py-8 text-center text-sm text-muted-foreground">
        ScholarOS
      </footer>
    </div>
  );
}
