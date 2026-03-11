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
import { Badge } from "@/components/ui/badge"
import { 
  Dialog, 
  DialogContent, 
  DialogDescription, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from "@/components/ui/dialog"
import { Megaphone, Plus, Link as LinkIcon, FileText, Clock, Play, Pause } from "lucide-react"

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([])
  const [isDialogOpen, setIsDialogOpen] = useState(false)

  // Form State
  const [name, setName] = useState("")
  const [groups, setGroups] = useState("")
  const [content, setContent] = useState("")
  const [interval, setInterval] = useState("60")

  useEffect(() => {
    setCampaigns([
      { id: 1, name: "Promocja Kursu AI", account: "marcin.fb@gmail.com", groups: 12, status: "W TOKU", lastRun: "10 min temu" },
      { id: 2, name: "Wyprzedaż Garażowa", account: "tester.sosm@wp.pl", groups: 5, status: "ZATRZYMANE", lastRun: "1 godz temu" },
    ])
  }, [])

  const handleCreateCampaign = (e: React.FormEvent) => {
    e.preventDefault()
    const newId = campaigns.length + 1
    setCampaigns([...campaigns, { 
      id: newId, 
      name, 
      account: "marcin.fb@gmail.com", 
      groups: groups.split('\n').filter(l => l.trim()).length, 
      status: "OCZEKUJE", 
      lastRun: "Brak" 
    }])
    setName("")
    setGroups("")
    setContent("")
    setIsDialogOpen(false)
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight text-foreground">Kampanie Automatyzacji</h2>
          <p className="text-muted-foreground">Planuj i zarządzaj publikacjami w grupach.</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button className="bg-primary text-primary-foreground hover:bg-primary/90">
              <Plus className="mr-2 h-4 w-4" /> Nowa Kampania
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl bg-card border-primary/20 text-foreground">
            <DialogHeader>
              <DialogTitle className="text-primary">Kreator Nowej Kampanii</DialogTitle>
              <DialogDescription>
                Zdefiniuj treść oraz listę grup docelowych. System zajmie się resztą.
              </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleCreateCampaign} className="grid grid-cols-2 gap-6 pt-4">
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="name">Nazwa Kampanii</Label>
                  <Input 
                    id="name" 
                    placeholder="np. Letnia Promocja" 
                    className="bg-secondary/50 border-primary/10"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="interval">Interwał (minuty)</Label>
                  <div className="flex items-center space-x-2">
                    <Clock className="h-4 w-4 text-primary" />
                    <Input 
                      id="interval" 
                      type="number" 
                      className="bg-secondary/50 border-primary/10"
                      value={interval}
                      onChange={(e) => setInterval(e.target.value)}
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="groups">Linki do Grup (jeden w linii)</Label>
                  <textarea 
                    id="groups"
                    className="flex min-h-[120px] w-full rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    placeholder="https://facebook.com/groups/..."
                    value={groups}
                    onChange={(e) => setGroups(e.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-4">
                 <div className="space-y-2">
                  <Label htmlFor="content">Treść Posta</Label>
                  <textarea 
                    id="content"
                    className="flex min-h-[200px] w-full rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary"
                    placeholder="Cześć wszystkim! Chciałbym zaprosić..."
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full bg-primary text-primary-foreground mt-4 font-bold">Uruchom Kampanię</Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Card className="border-primary/10 bg-card/50">
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow className="border-primary/10 hover:bg-transparent">
                <TableHead>Nazwa</TableHead>
                <TableHead>Konto Wykonawcze</TableHead>
                <TableHead>Liczba Grup</TableHead>
                <TableHead>Ostatni przebieg</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Akcje</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {campaigns.map((camp) => (
                <TableRow key={camp.id} className="border-primary/5 hover:bg-secondary/50">
                  <TableCell className="font-medium">
                    <div className="flex flex-col">
                       <span>{camp.name}</span>
                       <span className="text-[10px] text-muted-foreground uppercase tracking-widest">ID: {camp.id}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-muted-foreground text-xs">{camp.account}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="border-primary/20 text-primary">
                      <LinkIcon className="mr-1 h-3 w-3" /> {camp.groups} grup
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs italic text-muted-foreground">{camp.lastRun}</TableCell>
                  <TableCell>
                    {camp.status === "W TOKU" ? (
                       <Badge className="bg-primary/20 text-primary border-primary/30">
                         <Play className="mr-1 h-3 w-3 fill-primary" /> Aktywna
                       </Badge>
                    ) : (
                      <Badge variant="secondary" className="bg-secondary/50 text-muted-foreground">
                        <Pause className="mr-1 h-3 w-3 fill-muted-foreground" /> Wstrzymana
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" className="bg-primary/5 hover:bg-primary/20 text-primary border border-primary/10 mr-2">Edytuj</Button>
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
