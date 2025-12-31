import { useState, useEffect, useRef, memo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import mermaid from 'mermaid'
import { Copy, Check, ChevronDown, ChevronRight } from 'lucide-react'
import clsx from 'clsx'

// Initialize Mermaid with dark theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    primaryColor: '#0ea5e9',
    primaryTextColor: '#f1f5f9',
    primaryBorderColor: '#334155',
    lineColor: '#64748b',
    secondaryColor: '#1e293b',
    tertiaryColor: '#0f172a',
    background: '#0f172a',
    mainBkg: '#1e293b',
    nodeBorder: '#334155',
    clusterBkg: '#1e293b',
    titleColor: '#f1f5f9',
    edgeLabelBackground: '#1e293b',
  },
  fontFamily: 'Inter, system-ui, sans-serif',
})

interface MarkdownRendererProps {
  content: string
  className?: string
}

// Mermaid diagram renderer component
const MermaidDiagram = memo(({ code }: { code: string }) => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [svg, setSvg] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const idRef = useRef(`mermaid-${Math.random().toString(36).substr(2, 9)}`)

  useEffect(() => {
    const renderDiagram = async () => {
      try {
        const { svg: renderedSvg } = await mermaid.render(idRef.current, code)
        setSvg(renderedSvg)
        setError(null)
      } catch (err) {
        console.error('Mermaid render error:', err)
        setError('图表渲染失败')
      }
    }
    renderDiagram()
  }, [code])

  if (error) {
    return (
      <div className="mermaid-error">
        <span>⚠️ {error}</span>
        <pre className="mt-2 text-xs opacity-60">{code}</pre>
      </div>
    )
  }

  return (
    <div 
      ref={containerRef}
      className="mermaid-container"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
})

MermaidDiagram.displayName = 'MermaidDiagram'

// Code block with syntax highlighting and copy button
const CodeBlock = memo(({ 
  language, 
  children 
}: { 
  language: string | undefined
  children: string 
}) => {
  const [copied, setCopied] = useState(false)
  const code = String(children).replace(/\n$/, '')
  const lang = language?.toLowerCase() || 'text'

  // Handle mermaid diagrams
  if (lang === 'mermaid') {
    return <MermaidDiagram code={code} />
  }

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="code-block-container">
      <div className="code-block-header">
        <span className="code-block-lang">{lang}</span>
        <button 
          onClick={handleCopy}
          className="code-block-copy"
          title="复制代码"
        >
          {copied ? <Check size={14} /> : <Copy size={14} />}
          <span>{copied ? '已复制' : '复制'}</span>
        </button>
      </div>
      <SyntaxHighlighter
        style={oneDark}
        language={lang}
        PreTag="div"
        customStyle={{
          margin: 0,
          borderRadius: '0 0 8px 8px',
          fontSize: '13px',
          lineHeight: 1.6,
        }}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
})

CodeBlock.displayName = 'CodeBlock'

// Enhanced table component
const Table = ({ children }: { children: React.ReactNode }) => (
  <div className="table-wrapper">
    <table className="enhanced-table">
      {children}
    </table>
  </div>
)

// Table header
const TableHead = ({ children }: { children: React.ReactNode }) => (
  <thead className="enhanced-table-head">
    {children}
  </thead>
)

// Table row
const TableRow = ({ children }: { children: React.ReactNode }) => (
  <tr className="enhanced-table-row">
    {children}
  </tr>
)

// Table header cell
const TableHeaderCell = ({ children }: { children: React.ReactNode }) => (
  <th className="enhanced-table-th">
    {children}
  </th>
)

// Table data cell
const TableDataCell = ({ children }: { children: React.ReactNode }) => (
  <td className="enhanced-table-td">
    {children}
  </td>
)

// Collapsible list for outlines
const CollapsibleList = ({ 
  ordered, 
  children 
}: { 
  ordered: boolean
  children: React.ReactNode 
}) => {
  const Tag = ordered ? 'ol' : 'ul'
  return (
    <Tag className={clsx('enhanced-list', ordered ? 'enhanced-list-ordered' : 'enhanced-list-unordered')}>
      {children}
    </Tag>
  )
}

// List item with optional expand/collapse for nested items
const ListItem = ({ children }: { children: React.ReactNode }) => {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const hasNestedList = Array.isArray(children) && 
    children.some((child: unknown) => 
      typeof child === 'object' && 
      child !== null && 
      'type' in child &&
      (child.type === 'ul' || child.type === 'ol')
    )

  return (
    <li className="enhanced-list-item">
      {hasNestedList && (
        <button 
          className="list-collapse-btn"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
        </button>
      )}
      <div className={clsx('list-item-content', isCollapsed && 'collapsed')}>
        {children}
      </div>
    </li>
  )
}

// Blockquote for citations and notes
const Blockquote = ({ children }: { children: React.ReactNode }) => (
  <blockquote className="enhanced-blockquote">
    {children}
  </blockquote>
)

// Inline code
const InlineCode = ({ children }: { children: React.ReactNode }) => (
  <code className="enhanced-inline-code">{children}</code>
)

// Strong/bold text with accent
const Strong = ({ children }: { children: React.ReactNode }) => (
  <strong className="enhanced-strong">{children}</strong>
)

// Heading components
const Heading1 = ({ children }: { children: React.ReactNode }) => (
  <h1 className="enhanced-h1">{children}</h1>
)

const Heading2 = ({ children }: { children: React.ReactNode }) => (
  <h2 className="enhanced-h2">{children}</h2>
)

const Heading3 = ({ children }: { children: React.ReactNode }) => (
  <h3 className="enhanced-h3">{children}</h3>
)

// Paragraph with better spacing
const Paragraph = ({ children }: { children: React.ReactNode }) => (
  <p className="enhanced-paragraph">{children}</p>
)

// Horizontal rule
const HorizontalRule = () => (
  <hr className="enhanced-hr" />
)

// Link with external indicator
const Link = ({ href, children }: { href?: string; children: React.ReactNode }) => (
  <a 
    href={href} 
    className="enhanced-link"
    target={href?.startsWith('http') ? '_blank' : undefined}
    rel={href?.startsWith('http') ? 'noopener noreferrer' : undefined}
  >
    {children}
    {href?.startsWith('http') && <span className="external-link-icon">↗</span>}
  </a>
)

// Main MarkdownRenderer component
export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={clsx('markdown-renderer', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Code blocks
          code({ inline, className: codeClassName, children, ...props }) {
            const match = /language-(\w+)/.exec(codeClassName || '')
            const language = match ? match[1] : undefined
            
            if (!inline && (language || String(children).includes('\n'))) {
              return <CodeBlock language={language}>{String(children)}</CodeBlock>
            }
            
            return <InlineCode {...props}>{children}</InlineCode>
          },
          // Tables
          table: Table,
          thead: TableHead,
          tr: TableRow,
          th: TableHeaderCell,
          td: TableDataCell,
          // Lists
          ul: ({ children }) => <CollapsibleList ordered={false}>{children}</CollapsibleList>,
          ol: ({ children }) => <CollapsibleList ordered={true}>{children}</CollapsibleList>,
          li: ListItem,
          // Other elements
          blockquote: Blockquote,
          strong: Strong,
          h1: Heading1,
          h2: Heading2,
          h3: Heading3,
          p: Paragraph,
          hr: HorizontalRule,
          a: Link,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

