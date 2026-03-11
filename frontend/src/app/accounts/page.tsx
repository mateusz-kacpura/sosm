"use client"

import { useEffect, useState } from "react"
import { 
  Card, 
  CardContent, 
  CardDescription, 
  CardHeader, 
  CardTitle 
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
import { PlusCircle, Shield, Globe, Mail, Key } from "lucide-react"

export default function AccountsPage() {
  const [accounts, setAccounts] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  // Form State
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [proxy, setProxy] = useState("")

  useEffect(() => {
    // Symulacja pobrania z API
    setAccounts([
      { id: 1, email: "marcin.fb@gmail.com", proxy: "185.23.44.11:8080", status: "Aktywne", created: "2024-03-10" },
      { id: 2, email: "tester.sosm@wp.pl", proxy: "Brak", status: "Aktywne", created: "2024-03-09" },
    ])
    setIsLoading(false)
  }, [])

  const handleAddAccount = (e: React.FormEvent) => {
    e.preventDefault()
    const newId = accounts.length + 1
    setAccounts([...accounts, { 
      id: newId, 
      email, 
      proxy: proxy || "Brak", 
      status: "Aktywne", 
      created: new Date().toISOString().split('T')[0] 
    }])
    setEmail("")
    setPassword("")
    setProxy("")
    setIsDialogOpen(false)
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Konta Facebook</h2>
          <p className="text-muted-foreground">Zarządzaj profilami używanymi do automatyzacji.</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
              <PlusCircle className="mr-2 h-4 w-4" /> Dodaj Konto
            </Button>
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
              <Button type="submit" className="w-full bg-primary text-primary-foreground">Zapisz Konto</Button>
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
                <TableHead>Data dodania</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {accounts.map((acc) => (
                <TableRow key={acc.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium flex items-center">
                    <Shield className="mr-2 h-4 w-4 text-primary opacity-70" />
                    {acc.email}
                  </TableCell>
                  <TableCell className="text-muted-foreground font-mono text-xs">{acc.proxy}</TableCell>
                  <TableCell>{acc.created}</TableCell>
                  <TableCell>
                    <span className="flex items-center text-emerald-500 text-xs">
                       <span className="h-2 w-2 rounded-full bg-emerald-500 mr-2 animate-pulse"></span>
                       {acc.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-rose-500">Usuń</Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
