import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from 'react-query'
import { Globe, Zap, Search, MessageCircle, Link, ArrowRight, Shield } from 'lucide-react'
import { createWebsite, startIngestion } from '../lib/api'

export default function HomePage() {
  const [url, setUrl] = useState('')
  const [maxPages, setMaxPages] = useState(50)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const qc = useQueryClient()

  const addMut = useMutation(
    async () => {
      let normalized = url.trim()
      if (!normalized.startsWith('http')) normalized = 'https://' + normalized
      const site = await createWebsite(normalized, maxPages)
      await startIngestion(site.id)
      return site
    },
    {
      onSuccess: (site) => {
        qc.invalidateQueries('websites')
        navigate(`/website/${site.id}`)
      },
      onError: (e: any) => {
        setError(e?.response?.data?.detail || 'Failed to add website')
      },
    }
  )

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!url.trim()) { setError('Enter a website URL'); return }
    addMut.mutate()
  }

  const features = [
    { icon: Globe, label: 'Recursive crawling', desc: 'Discovers all pages within the same domain automatically' },
    { icon: Search, label: 'Hybrid retrieval', desc: 'Combines vector similarity + BM25 keyword search' },
    { icon: MessageCircle, label: 'Conversational memory', desc: 'Follow-up questions with full context awareness' },
    { icon: Shield, label: 'Source citations', desc: 'Every answer includes links to the source pages' },
  ]

  const examples = [
    'https://docs.python.org/3/',
    'https://react.dev/',
    'https://tailwindcss.com/docs',
  ]

  return (
    <div className="h-full overflow-y-auto scrollbar-thin">
      <div className="max-w-2xl mx-auto px-6 py-16">
        {/* Hero */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-brand-50 text-brand-700 text-xs font-medium px-3 py-1.5 rounded-full border border-brand-200 mb-6">
            <Zap size={12} />
            RAG-powered · Hybrid Search · Conversational
          </div>
          <h1 className="text-4xl font-bold text-ink-900 mb-4 leading-tight">
            Chat with any website
          </h1>
          <p className="text-ink-500 text-lg leading-relaxed">
            Enter a URL and instantly get an AI assistant that knows everything on that site — powered by semantic search and retrieval-augmented generation.
          </p>
        </div>

        {/* Form */}
        <div className="card p-6 mb-8">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ink-700 mb-1.5">
                Website URL
              </label>
              <div className="relative">
                <Link size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-300" />
                <input
                  type="text"
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  placeholder="https://docs.example.com"
                  className="input pl-9"
                  disabled={addMut.isLoading}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-ink-700 mb-1.5">
                Max pages to crawl: <span className="text-brand-600 font-semibold">{maxPages}</span>
              </label>
              <input
                type="range"
                min={5}
                max={200}
                step={5}
                value={maxPages}
                onChange={e => setMaxPages(+e.target.value)}
                className="w-full accent-brand-600"
                disabled={addMut.isLoading}
              />
              <div className="flex justify-between text-[10px] text-ink-400 mt-1">
                <span>5 (fast)</span>
                <span>200 (thorough)</span>
              </div>
            </div>

            {error && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={addMut.isLoading}
              className="btn-primary w-full justify-center py-2.5"
            >
              {addMut.isLoading ? (
                <>
                  <span className="dot-bounce flex gap-1">
                    <span /><span /><span />
                  </span>
                  Starting crawl…
                </>
              ) : (
                <>
                  Start indexing
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Examples */}
          <div className="mt-4 pt-4 border-t border-surface-100">
            <p className="text-xs text-ink-400 mb-2">Try an example:</p>
            <div className="flex flex-wrap gap-2">
              {examples.map(ex => (
                <button
                  key={ex}
                  onClick={() => setUrl(ex)}
                  className="text-xs text-brand-600 bg-brand-50 hover:bg-brand-100 px-2.5 py-1 rounded-full border border-brand-100 transition-colors"
                >
                  {new URL(ex).hostname}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-2 gap-4">
          {features.map(({ icon: Icon, label, desc }) => (
            <div key={label} className="card p-4">
              <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center mb-3">
                <Icon size={16} className="text-brand-600" />
              </div>
              <p className="text-sm font-semibold text-ink-800 mb-1">{label}</p>
              <p className="text-xs text-ink-500 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
