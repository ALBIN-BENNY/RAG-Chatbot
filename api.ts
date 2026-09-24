import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export interface Website {
  id: string
  url: string
  title?: string
  description?: string
  status: 'pending' | 'crawling' | 'indexing' | 'ready' | 'failed'
  pages_crawled: number
  pages_indexed: number
  total_chunks: number
  error_message?: string
  created_at: string
}

export interface IngestProgress {
  website_id: string
  status: string
  pages_crawled: number
  pages_indexed: number
  total_chunks: number
  current_url?: string
  error_message?: string
}

export interface Source {
  url: string
  title?: string
  snippet: string
  score: number
}

export interface ChatResponse {
  session_id: string
  message_id: string
  answer: string
  sources: Source[]
  latency_ms: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  created_at: string
}

export interface Session {
  id: string
  website_id: string
  title: string
  created_at: string
  messages: Message[]
}

// Websites
export const createWebsite = (url: string, max_pages = 100, use_playwright = false) =>
  api.post<Website>('/websites', { url, max_pages, use_playwright }).then(r => r.data)

export const listWebsites = () =>
  api.get<Website[]>('/websites').then(r => r.data)

export const getWebsite = (id: string) =>
  api.get<Website>(`/websites/${id}`).then(r => r.data)

export const deleteWebsite = (id: string) =>
  api.delete(`/websites/${id}`)

// Ingestion
export const startIngestion = (website_id: string, force_recrawl = false) =>
  api.post<IngestProgress>('/ingest/start', { website_id, force_recrawl }).then(r => r.data)

export const getIngestionStatus = (website_id: string) =>
  api.get<IngestProgress>(`/ingest/status/${website_id}`).then(r => r.data)

// Chat
export const sendMessage = (website_id: string, message: string, session_id?: string) =>
  api.post<ChatResponse>('/chat/message', { website_id, message, session_id }).then(r => r.data)

export const getSessions = (website_id: string) =>
  api.get<Session[]>(`/chat/sessions/${website_id}`).then(r => r.data)

export const getSession = (session_id: string) =>
  api.get<Session>(`/chat/session/${session_id}`).then(r => r.data)

export default api
