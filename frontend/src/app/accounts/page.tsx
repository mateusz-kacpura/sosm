"use client"

import { useEffect, useState, useCallback, Fragment } from "react"
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
import { PlusCircle, Shield, Globe, Mail, Key, Fingerprint, Loader2, ChevronDown, ChevronRight, Plus, Trash2, ExternalLink } from "lucide-react"
import { api } from "@/lib/api"

interface FanpageData {
  id: number
  account_id: number
  fanpage_url: string
  fanpage_name: string | null
  created_at: string
}

interface AccountData {
  id: number
  fb_email: string
  fb_password?: string
  proxy_url: string | null
  browser_profile_id: string | null
  created_at: string
  fanpages: FanpageData[]
}

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<AccountData[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [proxy, setProxy] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [creatingProfileFor, setCreatingProfileFor] = useState<number | null>(null)

  // Fanpage management state
  const [expandedAccount, setExpandedAccount] = useState<number | null>(null)
  const [newFanpageUrl, setNewFanpageUrl] = useState("")
  const [newFanpageName, setNewFanpageName] = useState("")
  const [addingFanpage, setAddingFanpage] = useState(false)

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

  const handleCreateProfile = async (id: number) => {
    setCreatingProfileFor(id)
    setError(null)
    try {
      await api.accounts.createProfile(id)
      await fetchAccounts()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setCreatingProfileFor(null)
    }
  }

  const handleAddFanpage = useCallback(async (accountId: number) => {
    if (!newFanpageUrl.trim()) return
    setAddingFanpage(true)
    try {
      await api.accounts.fanpages.create(accountId, {
        fanpage_url: newFanpageUrl.trim(),
        fanpage_name: newFanpageName.trim() || undefined,
      })
      setNewFanpageUrl("")
      setNewFanpageName("")
      await fetchAccounts()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setAddingFanpage(false)
    }
  }, [newFanpageUrl, newFanpageName])

  const handleDeleteFanpage = useCallback(async (accountId: number, fanpageId: number) => {
    try {
      await api.accounts.fanpages.delete(accountId, fanpageId)
      await fetchAccounts()
    } catch (err: any) {
      setError(err.message)
    }
  }, [])

  const toggleExpand = useCallback((accountId: number) => {
    setExpandedAccount((prev) => prev === accountId ? null : accountId)
    setNewFanpageUrl("")
    setNewFanpageName("")
  }, [])

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
                <TableHead>Fanpage&apos;e</TableHead>
                <TableHead>Data dodania</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((acc) => (
                <Fragment key={acc.id}>
                  <TableRow className="border-primary/5 hover:bg-secondary/50">
                    <TableCell className="font-medium flex items-center">
                      <Shield className="mr-2 h-4 w-4 text-primary opacity-70" />
                      {acc.fb_email}
                    </TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs">{acc.proxy_url || "Brak"}</TableCell>
                    <TableCell className="text-muted-foreground font-mono text-xs" title={acc.browser_profile_id || ""}>
                      {acc.browser_profile_id ? (
                        acc.browser_profile_id.slice(0, 8) + "..."
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 text-xs border-primary/20 hover:bg-primary/10"
                          onClick={() => handleCreateProfile(acc.id)}
                          disabled={creatingProfileFor === acc.id}
                        >
                          {creatingProfileFor === acc.id ? (
                            <><Loader2 className="mr-1 h-3 w-3 animate-spin" /> Tworzenie...</>
                          ) : (
                            <><Fingerprint className="mr-1 h-3 w-3" /> Utwórz profil</>
                          )}
                        </Button>
                      )}
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => toggleExpand(acc.id)}
                        className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors"
                      >
                        {expandedAccount === acc.id ? (
                          <ChevronDown className="h-3 w-3" />
                        ) : (
                          <ChevronRight className="h-3 w-3" />
                        )}
                        <span className="text-primary font-semibold">{acc.fanpages?.length || 0}</span>
                        <span>{(acc.fanpages?.length || 0) === 1 ? "fanpage" : "fanpage'y"}</span>
                      </button>
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

                  {/* Expandable fanpage section */}
                  {expandedAccount === acc.id && (
                    <TableRow className="border-primary/5 bg-secondary/20 hover:bg-secondary/20">
                      <TableCell colSpan={6} className="py-3">
                        <div className="pl-6 space-y-3">
                          <div className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                            Fanpage&apos;e konta {acc.fb_email}
                          </div>

                          {/* Existing fanpages */}
                          {(acc.fanpages || []).length > 0 && (
                            <div className="space-y-1.5">
                              {acc.fanpages.map((fp) => (
                                <div key={fp.id} className="flex items-center gap-2 group">
                                  <ExternalLink className="h-3 w-3 text-primary shrink-0" />
                                  <span className="text-xs font-mono text-foreground truncate max-w-[300px]" title={fp.fanpage_url}>
                                    {fp.fanpage_url}
                                  </span>
                                  {fp.fanpage_name && (
                                    <span className="text-xs text-muted-foreground">({fp.fanpage_name})</span>
                                  )}
                                  <button
                                    onClick={() => handleDeleteFanpage(acc.id, fp.id)}
                                    className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-rose-400"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Add new fanpage form */}
                          <div className="flex items-end gap-2">
                            <div className="flex-1 max-w-[350px]">
                              <Label className="text-[10px] text-muted-foreground">URL fanpage</Label>
                              <Input
                                value={newFanpageUrl}
                                onChange={(e) => setNewFanpageUrl(e.target.value)}
                                placeholder="https://www.facebook.com/nazwa-fanpage"
                                className="h-7 text-xs font-mono bg-secondary/50 border-primary/10"
                              />
                            </div>
                            <div className="w-36">
                              <Label className="text-[10px] text-muted-foreground">Nazwa (opcjonalnie)</Label>
                              <Input
                                value={newFanpageName}
                                onChange={(e) => setNewFanpageName(e.target.value)}
                                placeholder="Mój fanpage"
                                className="h-7 text-xs bg-secondary/50 border-primary/10"
                              />
                            </div>
                            <Button
                              size="sm"
                              className="h-7 px-2 text-xs"
                              onClick={() => handleAddFanpage(acc.id)}
                              disabled={addingFanpage || !newFanpageUrl.trim()}
                            >
                              {addingFanpage ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <><Plus className="h-3 w-3 mr-1" /> Dodaj</>
                              )}
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
              ))}
              {accounts.length === 0 && !isLoading && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground py-8">
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
