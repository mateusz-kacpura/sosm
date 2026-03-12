"use client"

import { useEffect, useState } from "react"
import {
  Card,
  CardContent,
} from "@/components/ui/card"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow
} from "@/components/ui/table"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from "@/components/ui/dialog"
import { PlusCircle, Shield, Globe, Mail, Key, Fingerprint, Loader2 } from "lucide-react"
import { api } from "@/lib/api"

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [proxy, setProxy] = useState("")
  const [submitting, setSubmitting] = useState(false)

  async function fetchAccounts() {
    try {
      const data = await api.accounts.list()
      setAccounts(data)
    } catch (err: any) {
      setError(err.message)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchAccounts()
  }, [])

  const handleAddAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await api.accounts.create({
        fb_email: email,
        fb_password: password,
        proxy_url: proxy || null,
      })
      setEmail("")
      setPassword("")
      setProxy("")
      setIsDialogOpen(false)
      await fetchAccounts()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await api.accounts.delete(id)
      await fetchAccounts()
    } catch (err: any) {
      setError(err.message)
    }
  }

  if (error) return <div className="text-rose-500">Błąd: {error}</div>

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Konta Facebook</h2>
          <p className="text-muted-foreground">Zarządzaj profilami używanymi do automatyzacji.</p>
        </div>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger render={<Button className="bg-primary text-primary-foreground hover:bg-primary/90" />}>
              <PlusCircle className="mr-2 h-4 w-4" /> Dodaj Konto
          </DialogTrigger>
          <DialogContent className="bg-card border-primary/20 text-foreground">
            <DialogHeader>
              <DialogTitle className="text-primary">Nowe Konto Facebook</DialogTitle>
              <DialogDescription>
                Wprowadź dane logowania. Dane są szyfrowane i używane tylko przez bota.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleAddAccount} className="space-y-4 pt-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email / Login FB</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="email"
                    placeholder="example@email.com"
                    className="pl-10 bg-secondary/50 border-primary/10"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Hasło Facebook</Label>
                <div className="relative">
                  <Key className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="password"
                    type="password"
                    placeholder="••••••••"
                    className="pl-10 bg-secondary/50 border-primary/10"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="proxy">Proxy (Opcjonalnie)</Label>
                <div className="relative">
                  <Globe className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="proxy"
                    placeholder="http://user:pass@host:port"
                    className="pl-10 bg-secondary/50 border-primary/10"
                    value={proxy}
                    onChange={(e) => setProxy(e.target.value)}
                  />
                </div>
              </div>
              <Button type="submit" className="w-full bg-primary text-primary-foreground" disabled={submitting}>
                {submitting ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Tworzenie profilu...</>
                ) : "Zapisz Konto"}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                <Fingerprint className="inline h-3 w-3 mr-1" />
                Profil przegladarki zostanie wygenerowany automatycznie
              </p>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead>Email</TableHead>
                <TableHead>Proxy</TableHead>
                <TableHead>Profile ID</TableHead>
                <TableHead>Data dodania</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((acc) => (
                <TableRow key={acc.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium flex items-center">
                    <Shield className="mr-2 h-4 w-4 text-primary opacity-70" />
                    {acc.fb_email}
                  </TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs">{acc.proxy_url || "Brak"}</TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs" title={acc.browser_profile_id || ""}>
                    {acc.browser_profile_id ? acc.browser_profile_id.slice(0, 8) + "..." : "Brak"}
                  </TableCell>
                  <TableCell>{acc.created_at ? new Date(acc.created_at).toLocaleDateString("pl-PL") : "-"}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground hover:text-rose-500"
                      onClick={() => handleDelete(acc.id)}
                    >
                      Usuń
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {accounts.length === 0 && !isLoading && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                    Brak kont
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
