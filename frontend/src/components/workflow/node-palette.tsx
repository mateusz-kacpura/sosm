"use client"

import {
  Play, Square, LogIn, FileText, Heart, MessageCircle, Send,
  Clock, GitBranch, Repeat, Shuffle, Merge, Variable, Webhook,
  type LucideIcon,
} from "lucide-react"

interface PaletteItem {
  type: string
  label: string
  icon: LucideIcon
}

const CATEGORIES: { name: string; color: string; items: PaletteItem[] }[] = [
  {
    name: "Trigger",
    color: "text-emerald-400",
    items: [
      { type: "start", label: "Start", icon: Play },
      { type: "end", label: "Koniec", icon: Square },
    ],
  },
  {
    name: "Facebook",
    color: "text-blue-400",
    items: [
      { type: "login", label: "Logowanie FB", icon: LogIn },
      { type: "post_group", label: "Post na grupie", icon: FileText },
      { type: "post_fanpage", label: "Post na fanpage", icon: FileText },
      { type: "like_page", label: "Polub stronę", icon: Heart },
      { type: "comment", label: "Komentarz", icon: MessageCircle },
      { type: "send_message", label: "Wyślij wiadomość", icon: Send },
    ],
  },
  {
    name: "Flow",
    color: "text-amber-400",
    items: [
      { type: "wait", label: "Czekaj", icon: Clock },
      { type: "if_else", label: "Warunek", icon: GitBranch },
      { type: "loop", label: "Pętla", icon: Repeat },
      { type: "random_choice", label: "Losowy wybór", icon: Shuffle },
      { type: "merge", label: "Złącz", icon: Merge },
    ],
  },
  {
    name: "Utility",
    color: "text-purple-400",
    items: [
      { type: "variable", label: "Zmienna", icon: Variable },
      { type: "webhook", label: "Webhook", icon: Webhook },
    ],
  },
]

const DEFAULT_LABELS: Record<string, string> = {}
CATEGORIES.forEach((cat) =>
  cat.items.forEach((item) => {
    DEFAULT_LABELS[item.type] = item.label
  }),
)
export { DEFAULT_LABELS }

export function NodePalette() {
  const onDragStart = (event: React.DragEvent, nodeType: string, label: string) => {
    event.dataTransfer.setData("application/reactflow-type", nodeType)
    event.dataTransfer.setData("application/reactflow-label", label)
    event.dataTransfer.effectAllowed = "move"
  }

  return (
    <div className="w-52 shrink-0 border-r border-primary/10 bg-card overflow-y-auto">
      <div className="p-3 border-b border-primary/10">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Węzły
        </h3>
      </div>
      {CATEGORIES.map((cat) => (
        <div key={cat.name} className="p-2">
          <div className={`text-[10px] font-semibold uppercase tracking-wider mb-1.5 px-1 ${cat.color}`}>
            {cat.name}
          </div>
          <div className="space-y-0.5">
            {cat.items.map((item) => (
              <div
                key={item.type}
                draggable
                onDragStart={(e) => onDragStart(e, item.type, item.label)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg cursor-grab
                           hover:bg-secondary/50 active:cursor-grabbing transition-colors"
              >
                <item.icon className={`h-3.5 w-3.5 ${cat.color}`} />
                <span className="text-xs">{item.label}</span>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
