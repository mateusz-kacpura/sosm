"use client"

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Lock, KeyRound, Shield } from "lucide-react"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api"

interface AuthContextValue {
  authenticated: boolean
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue>({
  authenticated: false,
  logout: async () => {},
})

export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState({
    authenticated: false,
    password_set: false,
    loading: true,
  })

  const checkAuth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/status`, { credentials: "include" })
      const data = await res.json()
      setState({ ...data, loading: false })
    } catch {
      setState({ authenticated: false, password_set: false, loading: false })
    }
  }, [])

  useEffect(() => {
    checkAuth()
  }, [checkAuth])

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/auth/logout`, { method: "POST", credentials: "include" })
    setState((prev) => ({ ...prev, authenticated: false }))
  }, [])

  if (state.loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-primary italic animate-pulse text-lg">SOSM Panel</div>
      </div>
    )
  }

  if (!state.password_set) {
    return <SetPasswordForm onSuccess={checkAuth} />
  }

  if (!state.authenticated) {
    return <LoginForm onSuccess={checkAuth} />
  }

  return (
    <AuthContext.Provider value={{ authenticated: true, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || "Logowanie nie powiodło się")
        return
      }

      onSuccess()
    } catch {
      setError("Brak połączenia z serwerem")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm border-primary/20">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Lock className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">SOSM Panel</CardTitle>
          <CardDescription>Podaj hasło, aby kontynuować</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">Hasło</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                placeholder="Wpisz hasło..."
              />
            </div>
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button type="submit" className="w-full" disabled={loading || !password}>
              <KeyRound className="mr-2 h-4 w-4" />
              {loading ? "Logowanie..." : "Zaloguj się"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function SetPasswordForm({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState("")
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (password.length < 4) {
      setError("Hasło musi mieć min. 4 znaki")
      return
    }
    if (password !== confirm) {
      setError("Hasła nie są identyczne")
      return
    }

    setLoading(true)

    try {
      const res = await fetch(`${API_BASE}/auth/set-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password }),
      })

      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        setError(data.detail || "Nie udało się ustawić hasła")
        return
      }

      onSuccess()
    } catch {
      setError("Brak połączenia z serwerem")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-sm border-primary/20">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <Shield className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">Ustaw hasło</CardTitle>
          <CardDescription>
            Zabezpiecz panel SOSM hasłem dostępu
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="new-password">Hasło</Label>
              <Input
                id="new-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
                placeholder="Min. 4 znaki"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">Powtórz hasło</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Powtórz hasło"
              />
            </div>
            {error && (
              <p className="text-sm text-destructive">{error}</p>
            )}
            <Button
              type="submit"
              className="w-full"
              disabled={loading || !password || !confirm}
            >
              <Shield className="mr-2 h-4 w-4" />
              {loading ? "Zapisywanie..." : "Ustaw hasło"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
