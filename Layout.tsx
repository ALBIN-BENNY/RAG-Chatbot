import { Outlet, Link, useNavigate } from 'react-router-dom'
import { Bot, Plus, Globe, Trash2, ChevronRight } from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from 'react-query'
import { listWebsites, deleteWebsite, Website } from '../lib/api'
import { formatDistanceToNow } from 'date-fns'
import clsx from 'clsx'

function StatusDot({ status }: { status: Website['status'] }) {
  const colors: Record<string, string> = {
    ready: 'bg-emerald-400',
    crawling: 'bg-amber-400 animate-pulse',
    indexing: 'bg-blue-400 animate-pulse',
    pending: 'bg-surface-300',
    failed: 'bg-red-400',
  }
  return (
    <span className={clsx('inline-block w-2 h-2 rounded-full flex-shrink-0', colors[status] || 'bg-surface-300')} />
  )
}

export default function Layout() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { data: websites = [] } = useQuery('websites', listWebsites, {
    refetchInterval: 5000, // poll while crawling
  })

  const deleteMut = useMutation((id: string) => deleteWebsite(id), {
    onSuccess: () => qc.invalidateQueries('websites'),
  })

  return (
    <div className="flex h-screen overflow-hidden bg-surface-50">
      {/* Sidebar */}
      <aside className="w-72 flex-shrink-0 bg-surface-0 border-r border-surface-200 flex flex-col">
        {/* Logo */}
        <div className="px-5 py-4 border-b border-surface-200">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center shadow-sm group-hover:bg-brand-700 transition-colors">
              <Bot className="w-4.5 h-4.5 text-white" size={18} />
            </div>
            <div>
              <span className="font-semibold text-ink-900 text-sm">RAG Chatbot</span>
              <p className="text-[10px] text-ink-400 leading-tight">Chat with any website</p>
            </div>
          </Link>
        </div>

        {/* Add website */}
        <div className="px-3 pt-3">
          <button
            onClick={() => navigate('/')}
            className="btn-primary w-full justify-center text-xs"
          >
            <Plus size={14} />
            Add Website
          </button>
        </div>

        {/* Website list */}
        <nav className="flex-1 overflow-y-auto scrollbar-thin px-2 py-3 space-y-0.5">
          {websites.length === 0 && (
            <p className="text-xs text-ink-400 text-center py-6 px-4">
              No websites indexed yet. Add one to get started!
            </p>
          )}
          {websites.map(site => (
            <div key={site.id} className="group relative">
              <Link
                to={`/website/${site.id}`}
                className="flex items-start gap-2.5 px-3 py-2.5 rounded-lg hover:bg-surface-50 transition-colors"
              >
                <StatusDot status={site.status} />
                <div className="flex-1 min-w-0 mt-0.5">
                  <p className="text-xs font-medium text-ink-700 truncate">
                    {site.title || new URL(site.url).hostname}
                  </p>
                  <p className="text-[10px] text-ink-400 truncate mt-0.5">
                    {site.status === 'ready'
                      ? `${site.pages_indexed} pages · ${site.total_chunks} chunks`
                      : site.status === 'crawling'
                      ? `Crawling… ${site.pages_crawled} pages`
                      : site.status === 'indexing'
                      ? `Indexing…`
                      : site.status === 'failed'
                      ? 'Failed'
                      : 'Pending'}
                  </p>
                </div>
                <ChevronRight size={12} className="text-ink-300 mt-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
              </Link>
              <button
                onClick={(e) => { e.preventDefault(); deleteMut.mutate(site.id) }}
                className="absolute right-2 top-2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-red-50 hover:text-red-500 text-ink-300 transition-all"
                title="Delete"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-surface-200">
          <p className="text-[10px] text-ink-300 text-center">
            Powered by RAG + Hybrid Search
          </p>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
