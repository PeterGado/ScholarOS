import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Renders chat message content as markdown (bold/italic, lists, links, code blocks) - a real
// gap the plain-text rendering left: LLM replies routinely come back with markdown syntax that
// was previously shown to the user as literal asterisks and backticks. Styling lives in
// index.css under `.markdown-content` rather than pulling in a full typography plugin for what
// is, in practice, a handful of simple element types.
export function MarkdownMessage({ content }: { content: string }) {
  return (
    <div className="markdown-content text-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
