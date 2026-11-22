import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'

/** Markdown renderer with code syntax highlighting (shared by exam & admin pages). */
export default function Markdown({ content }: { content: string }) {
  return <ReactMarkdown rehypePlugins={[rehypeHighlight]}>{content}</ReactMarkdown>
}
