import axios from 'axios'
import type { AgentResponse, DocumentUploadResponse, UploadedDocument } from '../types'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
  timeout: 120_000,
  headers: { 'Content-Type': 'application/json' },
})

// ── Shared agent query ────────────────────────────────────
export async function queryAgent(
  endpoint: string,
  query: string,
  sessionId?: string
): Promise<AgentResponse> {
  const { data } = await http.post<AgentResponse>(endpoint, {
    query,
    session_id: sessionId,
  })
  return data
}

// ── Examples ──────────────────────────────────────────────
export async function getExamples(endpoint: string): Promise<string[]> {
  const { data } = await http.get<{ examples: string[] }>(endpoint)
  return data.examples ?? []
}

// ── Speech: upload + analyse call recording ───────────────
export async function uploadAudio(
  audioBytes: Blob,
  filename: string,
  analysisPrompt: string,
  sessionId?: string
): Promise<AgentResponse> {
  const form = new FormData()
  form.append('file', audioBytes, filename)
  form.append('analysis_prompt', analysisPrompt)
  if (sessionId) form.append('session_id', sessionId)
  const { data } = await http.post<AgentResponse>('/api/speech/transcribe', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

// ── Speech: transcribe question to text (Whisper only) ────
export async function transcribeToText(
  audioBlob: Blob,
  filename = 'question.wav'
): Promise<string> {
  const form = new FormData()
  form.append('file', audioBlob, filename)
  const { data } = await http.post<{ transcript: string }>(
    '/api/speech/transcribe-text',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return data.transcript ?? ''
}

// ── Sentiment: live filtered chart data ──────────────────
export async function getSentimentChartData(params: {
  topic?:     string | null
  platform?:  string | null
  sentiment?: string | null
}) {
  const { data } = await http.get('/api/sentiment/chart-data', { params })
  return data
}

// ── TTS: text → MP3 blob ──────────────────────────────────
export async function textToSpeech(
  text: string,
  voice = 'nova',
  model = 'tts-1'
): Promise<Blob> {
  const response = await http.post(
    '/api/speech/tts',
    { text, voice, model },
    { responseType: 'blob' }
  )
  return response.data as Blob
}

// ── Call transcripts list ─────────────────────────────────
export async function listCallTranscripts(): Promise<Record<string, unknown>[]> {
  const { data } = await http.get<{ calls: Record<string, unknown>[] }>(
    '/api/speech/calls'
  )
  return data.calls ?? []
}

// ── Health check ──────────────────────────────────────────
export async function healthCheck(): Promise<{ status: string }> {
  const { data } = await http.get<{ status: string }>('/health')
  return data
}

// ── RAG: upload a document → parse, embed, auto-summary ──
export async function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData()
  form.append('file', file, file.name)
  const { data } = await http.post<DocumentUploadResponse>(
    '/api/documents/upload',
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } }
  )
  return data
}

// ── RAG: ask a question about an uploaded document ───────
export async function queryDocument(
  docId: number,
  query: string,
  sessionId?: string
): Promise<AgentResponse> {
  const { data } = await http.post<AgentResponse>(
    `/api/documents/${docId}/query`,
    { query, session_id: sessionId }
  )
  return data
}

// ── RAG: list uploaded documents ─────────────────────────
export async function listDocuments(): Promise<UploadedDocument[]> {
  const { data } = await http.get<{ documents: UploadedDocument[] }>('/api/documents/')
  return data.documents ?? []
}

// ── RAG: delete an uploaded document ─────────────────────
export async function deleteDocument(docId: number): Promise<void> {
  await http.delete(`/api/documents/${docId}`)
}

export default http
