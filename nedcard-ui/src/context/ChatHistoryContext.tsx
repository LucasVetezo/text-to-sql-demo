/**
 * ChatHistoryContext
 *
 * Stores chat message history per module key (e.g. the API endpoint path) so
 * that navigating away from a module and back does not wipe the conversation.
 *
 * Scope: single browser session — history is held in React memory and is
 * cleared only on a full page reload or explicit logout.
 */
import React, { createContext, useCallback, useContext, useRef } from 'react'
import type { ChatMessage } from '../types'

type HistoryMap = Record<string, ChatMessage[]>

interface ChatHistoryContextValue {
  getHistory: (key: string) => ChatMessage[]
  setHistory: (key: string, messages: ChatMessage[]) => void
  clearHistory: (key?: string) => void   // clears one key (or all if omitted)
}

const ChatHistoryContext = createContext<ChatHistoryContextValue | null>(null)

export function ChatHistoryProvider({ children }: { children: React.ReactNode }) {
  // useRef so updates don't re-render the provider subtree
  const mapRef = useRef<HistoryMap>({})

  const getHistory = useCallback((key: string): ChatMessage[] => {
    return mapRef.current[key] ?? []
  }, [])

  const setHistory = useCallback((key: string, messages: ChatMessage[]) => {
    mapRef.current = { ...mapRef.current, [key]: messages }
  }, [])

  const clearHistory = useCallback((key?: string) => {
    if (key) {
      const next = { ...mapRef.current }
      delete next[key]
      mapRef.current = next
    } else {
      mapRef.current = {}
    }
  }, [])

  return (
    <ChatHistoryContext.Provider value={{ getHistory, setHistory, clearHistory }}>
      {children}
    </ChatHistoryContext.Provider>
  )
}

export function useChatHistory(): ChatHistoryContextValue {
  const ctx = useContext(ChatHistoryContext)
  if (!ctx) throw new Error('useChatHistory must be used inside <ChatHistoryProvider>')
  return ctx
}
