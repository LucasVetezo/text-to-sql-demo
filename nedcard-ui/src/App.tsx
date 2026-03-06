import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ChatHistoryProvider } from './context/ChatHistoryContext'
import LoginPage from './pages/LoginPage'
import WelcomePage from './pages/WelcomePage'
import ChatPage from './pages/ChatPage'
import Layout from './components/Layout'
import DashboardPage from './pages/DashboardPage'
import CreditPage from './pages/CreditPage'
import FraudPage from './pages/FraudPage'
import SentimentPage from './pages/SentimentPage'
import SpeechPage from './pages/SpeechPage'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/welcome"
        element={
          <ProtectedRoute>
            <WelcomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/chat" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="credit" element={<CreditPage />} />
        <Route path="fraud" element={<FraudPage />} />
        <Route path="sentiment" element={<SentimentPage />} />
        <Route path="speech" element={<SpeechPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <ChatHistoryProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </ChatHistoryProvider>
    </AuthProvider>
  )
}
