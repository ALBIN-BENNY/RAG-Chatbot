import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  getWebsite, getIngestionStatus, sendMessage, getSessions, getSession,
  startIngestion, Source, Message, Session
} from '../lib/api'
import {
  Send, RefreshCw, Globe, Clock, FileText, ChevronDown, ChevronUp,
  ExternalLink, Plus, MessageSquare, Loader2, AlertCircle, CheckCircle2
} from 'lucide-react'
import clsx from 'clsx'
import { formatDistanceToNow } from 'date-fns'

function TypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-7 h-7 rounded-full bg-brand-100 flex items-center justify-center flex-shrink-0 mt-0.5">
        <span className="text-brand-600 text-xs font-bold">AI</span>
      </div>
      <div className="bg-surface-100 rounded-2xl rounded-tl-sm px-4 py-3">
        <div className="dot-bounce flex gap-1.5 items-center" style={{ color: '#94a3b8' }}>
          <span /><span /><span />
        </div>
      </div>
    </div>
  )
}

function SourceCard({ source }: { source: Source }) {
  const [open, setOpen] = useState(false)
  const score = Math.round(source.score * 100)
  return (
    <div className="border border-surface-200 rounded-lg overflow-hidden text-xs">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-surface-50 hover:bg-surface-100 transition-colors text-left"
      >
        <FileText size={11} className="text-ink-400 flex-shrink-0" />
        <span className="font-medium text-ink-700 truncate flex-1">{source.title || source.url}</span>
        <span className={clsx(
          'flex-shrink-0 px-1.5 py-0.5 rounded-full font-medium',
          score >= 70 ? 'bg-emerald-100 text-emerald-700' :
          score >= 40 ? 'bg-amber-100 text-amber-700' :
          'bg-surface-200 text-ink-400'
        )}>
          {score}%
        </span>
        {open ? <ChevronUp size={11} className="text-ink-300" /> : <ChevronDown size={11} className="text-ink-300" />}
      </button>
      {open && (
        <div className="px-3 py-2 bg-white border-t border-surface-100">
          <p className="text-ink-500 leading-relaxed mb-2">{source.snippet}</p>
          <a
            href={source.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-brand-600 hover:text-brand-700 font-medium"
          >
            Visit page <ExternalLink size={10} />
          </a>
        </div>
      )}
    </div>
  )
}

function ChatMessage({ msg }: { msg: Message }) {
  const isUser = msg.role === 'user'
  return (
    <div className={clsx('flex gap-3 animate-slide-up', isUser && 'flex-row-reverse')}>
      {/* Avatar */}
      <div className={clsx(
        'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 text-xs font-bold',
        isUser ? 'bg-brand-600 text-white' : 'bg-brand-100 text-brand-600'
      )}>
        {isUser ? 'U' : 'AI'}
      </div>

      <div className={clsx('max-w-[80%] space-y-2', isUser && 'items-end flex flex-col')}>
        <div className={clsx(
          'rounded-2xl px-4 py-3',
          isUser
            ? 'bg-brand-600 text-white rounded-tr-sm'
            : 'bg-surface-100 text-ink-900 rounded-tl-sm'
        )}>
          {isUser ? (
            <p className="text-sm">{msg.content}</p>
          ) : (
            <div className="prose-chat">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          )}
        </div>

        {/* Sources */}
        {!isUser && msg.sources && msg.sources.length > 0 && (
          <div className="w-full space-y-1.5">
            <p className="text-[10px] font-medium text-ink-400 uppercase tracking-wide px-1">
              Sources ({msg.sources.length})
            </p>
            {(msg.sources as Source[]).map((s, i) => (
              <SourceCard key={i} source={s} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default function WebsitePage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | undefined>()
  const [isTyping, setIsTyping] = useState(false)

  const { data: website } = useQuery(
    ['website', id],
    () => getWebsite(id!),
    { refetchInterval: (data) => data?.status === 'ready' ? false : 3000 }
  )

  const { data: sessions = [] } = useQuery(
    ['sessions', id],
    () => getSessions(id!),
    { enabled: website?.status === 'ready' }
  )

  const reindexMut = useMutation(() => startIngestion(id!, true), {
    onSuccess: () => qc.invalidateQueries(['website', id]),
  })

  const sendMut = useMutation(
    (msg: string) => sendMessage(id!, msg, sessionId),
    {
      onMutate: (msg) => {
        const userMsg: Message = {
          id: `tmp-${Date.now()}`,
          role: 'user',
          content: msg,
          sources: [],
          created_at: new Date().toISOString(),
        }
        setMessages(m => [...m, userMsg])
        setIsTyping(true)
        setInput('')
      },
      onSuccess: (resp) => {
        setSessionId(resp.session_id)
        const aiMsg: Message = {
          id: resp.message_id,
          role: 'assistant',
          content: resp.answer,
          sources: resp.sources as any,
          created_at: new Date().toISOString(),
        }
        setMessages(m => [...m, aiMsg])
        setIsTyping(false)
        qc.invalidateQueries(['sessions', id])
      },
      onError: () => setIsTyping(false),
    }
  )

  const loadSession = async (sid: string) => {
    const sess = await getSession(sid)
    setSessionId(sid)
    setMessages(sess.messages)
  }

  const newConversation = () => {
    setSessionId(undefined)
    setMessages([])
  }

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || sendMut.isLoading || website?.status !== 'ready') return
    sendMut.mutate(msg)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const statusBadge = {
    ready: <span className="badge-green"><CheckCircle2 size={10} className="mr-1" />Ready</span>,
    crawling: <span className="badge-amber"><Loader2 size={10} className="mr-1 animate-spin" />Crawling</span>,
    indexing: <span className="badge-blue"><Loader2 size={10} className="mr-1 animate-spin" />Indexing</span>,
    pending: <span className="badge-gray">Pending</span>,
    failed: <span className="badge-red"><AlertCircle size={10} className="mr-1" />Failed</span>,
  }

  if (!website) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-brand-500" />
      </div>
    )
  }

  const isReady = website.status === 'ready'
  const hostname = (() => { try { return new URL(website.url).hostname } catch { return website.url } })()

  return (
    <div className="h-full flex">
      {/* Chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="flex-shrink-0 bg-surface-0 border-b border-surface-200 px-5 py-3 flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center flex-shrink-0">
            <Globe size={16} className="text-brand-600" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-ink-900 truncate">
              {website.title || hostname}
            </p>
            <p className="text-xs text-ink-400 truncate">{website.url}</p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {statusBadge[website.status]}
            {isReady && (
              <>
                <span className="text-xs text-ink-400">{website.pages_indexed}p · {website.total_chunks}c</span>
                <button
                  onClick={() => reindexMut.mutate()}
                  disabled={reindexMut.isLoading}
                  className="btn-ghost text-xs px-2 py-1.5"
                  title="Re-index"
                >
                  <RefreshCw size={13} className={reindexMut.isLoading ? 'animate-spin' : ''} />
                </button>
              </>
            )}
          </div>
        </header>

        {/* Progress bar during ingestion */}
        {!isReady && website.status !== 'failed' && (
          <div className="flex-shrink-0 bg-amber-50 border-b border-amber-200 px-5 py-3">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-amber-800">
                {website.status === 'crawling' ? `Crawling website… ${website.pages_crawled} pages found` : 'Indexing content…'}
              </p>
              <p className="text-xs text-amber-600">{website.total_chunks} chunks indexed</p>
            </div>
            <div className="w-full bg-amber-200 rounded-full h-1.5 overflow-hidden">
              <div
                className="bg-amber-500 h-full rounded-full transition-all duration-500 animate-pulse"
                style={{ width: `${Math.min(90, (website.pages_crawled / (website.crawl_config?.max_pages || 100)) * 100)}%` }}
              />
            </div>
          </div>
        )}

        {website.status === 'failed' && (
          <div className="flex-shrink-0 bg-red-50 border-b border-red-200 px-5 py-3">
            <p className="text-xs text-red-700 font-medium">Indexing failed: {website.error_message}</p>
            <button onClick={() => reindexMut.mutate()} className="text-xs text-red-600 underline mt-1">
              Retry
            </button>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-5 py-6 space-y-5">
          {messages.length === 0 && isReady && (
            <div className="text-center py-16">
              <div className="w-14 h-14 rounded-2xl bg-brand-50 border border-brand-100 flex items-center justify-center mx-auto mb-4">
                <MessageSquare size={24} className="text-brand-500" />
              </div>
              <h3 className="text-base font-semibold text-ink-800 mb-2">
                Ready to chat with {hostname}
              </h3>
              <p className="text-sm text-ink-400 max-w-sm mx-auto mb-6">
                Ask anything about the content on this website. I'll find the most relevant information and cite my sources.
              </p>
              <div className="flex flex-wrap gap-2 justify-center">
                {[
                  'What is this website about?',
                  'What are the main topics covered?',
                  'Give me a quick summary',
                ].map(q => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); inputRef.current?.focus() }}
                    className="text-sm text-brand-600 bg-brand-50 hover:bg-brand-100 px-4 py-2 rounded-full border border-brand-100 transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.length === 0 && !isReady && (
            <div className="text-center py-16">
              <Loader2 className="w-8 h-8 animate-spin text-brand-400 mx-auto mb-3" />
              <p className="text-sm text-ink-500">Indexing in progress — chat will be available once ready.</p>
            </div>
          )}

          {messages.map(msg => (
            <ChatMessage key={msg.id} msg={msg} />
          ))}

          {isTyping && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="flex-shrink-0 bg-surface-0 border-t border-surface-200 p-4">
          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isReady ? 'Ask a question about this website…' : 'Waiting for indexing to complete…'}
              disabled={!isReady || sendMut.isLoading}
              rows={1}
              className="input flex-1 resize-none min-h-[40px] max-h-32 py-2.5 leading-normal"
              style={{ height: 'auto' }}
              onInput={e => {
                const el = e.currentTarget
                el.style.height = 'auto'
                el.style.height = Math.min(el.scrollHeight, 128) + 'px'
              }}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || !isReady || sendMut.isLoading}
              className="btn-primary px-3 py-2.5 flex-shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {sendMut.isLoading
                ? <Loader2 size={16} className="animate-spin" />
                : <Send size={16} />
              }
            </button>
          </div>
          <p className="text-[10px] text-ink-300 mt-1.5 text-center">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Sessions sidebar */}
      {isReady && (
        <aside className="w-60 flex-shrink-0 bg-surface-0 border-l border-surface-200 flex flex-col">
          <div className="px-3 py-3 border-b border-surface-200 flex items-center justify-between">
            <span className="text-xs font-semibold text-ink-600 uppercase tracking-wide">Conversations</span>
            <button onClick={newConversation} className="btn-ghost px-2 py-1 text-xs">
              <Plus size={12} />
              New
            </button>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin py-2">
            {sessions.length === 0 && (
              <p className="text-xs text-ink-400 text-center py-6 px-3">No conversations yet</p>
            )}
            {sessions.map(sess => (
              <button
                key={sess.id}
                onClick={() => loadSession(sess.id)}
                className={clsx(
                  'w-full text-left px-3 py-2.5 hover:bg-surface-50 transition-colors',
                  sessionId === sess.id && 'bg-brand-50 border-r-2 border-brand-500'
                )}
              >
                <p className="text-xs font-medium text-ink-700 truncate">{sess.title}</p>
                <p className="text-[10px] text-ink-400 mt-0.5">
                  {formatDistanceToNow(new Date(sess.created_at), { addSuffix: true })}
                </p>
              </button>
            ))}
          </div>
        </aside>
      )}
    </div>
  )
}
