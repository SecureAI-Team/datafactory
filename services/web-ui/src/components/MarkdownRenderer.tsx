import { useState, useEffect, useRef, memo, ReactNode } from 'react'
import ReactMarkdown, { Components } from 'react-markdown'
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

// List item with optional expand/collapse for nested items
const ListItem = ({ children }: { children?: ReactNode }) => {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const childArray = Array.isArray(children) ? children : [children]
  const hasNestedList = childArray.some((child: unknown) => 
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

// Custom components for ReactMarkdown
const components: Components = {
  // Code blocks and inline code
  code({ className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || '')
    const language = match ? match[1] : undefined
    const content = String(children)
    
    // Check if it's a code block (has language or multiple lines)
    if (language || content.includes('\n')) {
      return <CodeBlock language={language}>{content}</CodeBlock>
    }
    
    // Inline code
    return <code className="enhanced-inline-code" {...props}>{children}</code>
  },
  
  // Tables
  table({ children }) {
    return (
      <div className="table-wrapper">
        <table className="enhanced-table">{children}</table>
      </div>
    )
  },
  thead({ children }) {
    return <thead className="enhanced-table-head">{children}</thead>
  },
  tr({ children }) {
    return <tr className="enhanced-table-row">{children}</tr>
  },
  th({ children }) {
    return <th className="enhanced-table-th">{children}</th>
  },
  td({ children }) {
    return <td className="enhanced-table-td">{children}</td>
  },
  
  // Lists
  ul({ children }) {
    return <ul className="enhanced-list enhanced-list-unordered">{children}</ul>
  },
  ol({ children }) {
    return <ol className="enhanced-list enhanced-list-ordered">{children}</ol>
  },
  li({ children }) {
    return <ListItem>{children}</ListItem>
  },
  
  // Other elements
  blockquote({ children }) {
    return <blockquote className="enhanced-blockquote">{children}</blockquote>
  },
  strong({ children }) {
    return <strong className="enhanced-strong">{children}</strong>
  },
  h1({ children }) {
    return <h1 className="enhanced-h1">{children}</h1>
  },
  h2({ children }) {
    return <h2 className="enhanced-h2">{children}</h2>
  },
  h3({ children }) {
    return <h3 className="enhanced-h3">{children}</h3>
  },
  p({ children }) {
    return <p className="enhanced-paragraph">{children}</p>
  },
  hr() {
    return <hr className="enhanced-hr" />
  },
  a({ href, children }) {
    const isExternal = href?.startsWith('http')
    return (
      <a 
        href={href} 
        className="enhanced-link"
        target={isExternal ? '_blank' : undefined}
        rel={isExternal ? 'noopener noreferrer' : undefined}
      >
        {children}
        {isExternal && <span className="external-link-icon">↗</span>}
      </a>
    )
  },
}

// Main MarkdownRenderer component
export default function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={clsx('markdown-renderer', className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
