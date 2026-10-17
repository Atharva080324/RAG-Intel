/**
 * AuthContext – stores the JWT and exposes login/logout helpers.
 * Token is persisted in localStorage so it survives page refreshes.
 */
import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

interface AuthState {
  token: string | null
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthState>({
  token: null,
  login: () => undefined,
  logout: () => undefined,
})

const LS_KEY = 'rag_auth_token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(LS_KEY))

  const login = useCallback((t: string) => {
    localStorage.setItem(LS_KEY, t)
    setToken(t)
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(LS_KEY)
    setToken(null)
  }, [])

  // Handle ?token= redirect from Google OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const t = params.get('token')
    if (t) {
      login(t)
      // Clean token from URL without reload
      const clean = window.location.pathname
      window.history.replaceState({}, '', clean)
    }
  }, [login])

  return <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
