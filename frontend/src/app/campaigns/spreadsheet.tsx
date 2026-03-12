"use client"

import { useEffect, useState, useRef, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Trash2, Clock, ClipboardPaste, Wand2, ArrowUpDown, ArrowUp, ArrowDown, Type } from "lucide-react"

export interface GroupRow {
  url: string
  content: string
  background_style: string
  planned_date: string
  planned_time: string
}

// Facebook post background options
// Solid colors (visible directly in the composer)
// Decorative backgrounds (visible after clicking expand button, identified by index)
export const FB_BACKGROUNDS: { id: string; color: string; label: string }[] = [
  { id: "red", color: "#E2013B", label: "Czerwony" },
  { id: "black", color: "#111111", label: "Czarny" },
  // Decorative backgrounds (approximate preview colors)
  { id: "deco_0", color: "#E0DFDD", label: "Jasnoszary" },
  { id: "deco_1", color: "#9B9B9B", label: "Szary" },
  { id: "deco_2", color: "#2D2D2D", label: "Czarny deko" },
  { id: "deco_3", color: "#F5A9B8", label: "Rozowy" },
  { id: "deco_4", color: "#D44C47", label: "Czerwony deko" },
  { id: "deco_5", color: "#8B2252", label: "Ciemnoczerwony" },
  { id: "deco_6", color: "#E8758F", label: "Rozowy 2" },
  { id: "deco_7", color: "#E8A0BF", label: "Rozowy 3" },
  { id: "deco_8", color: "#C0392B", label: "Karmazynowy" },
  { id: "deco_9", color: "#D2B48C", label: "Bezowy" },
  { id: "deco_10", color: "#E67E22", label: "Pomaranczowy" },
  { id: "deco_11", color: "#8B4513", label: "Brazowy" },
  { id: "deco_12", color: "#F5DEB3", label: "Jasnozolty" },
  { id: "deco_13", color: "#F1C40F", label: "Zolty" },
  { id: "deco_14", color: "#B8860B", label: "Ciemnozolty" },
  { id: "deco_15", color: "#90EE90", label: "Jasnozielony" },
  { id: "deco_16", color: "#7CFC00", label: "Jasnozielony 2" },
  { id: "deco_17", color: "#808000", label: "Oliwkowy" },
  { id: "deco_18", color: "#98FB98", label: "Jasnozielony 3" },
  { id: "deco_19", color: "#2ECC71", label: "Zielony" },
  { id: "deco_20", color: "#1B5E20", label: "Zielony 2" },
  { id: "deco_21", color: "#87CEEB", label: "Jasnoniebieski" },
  { id: "deco_22", color: "#40E0D0", label: "Turkusowy" },
  { id: "deco_23", color: "#006400", label: "Zielony 3" },
  { id: "deco_24", color: "#ADD8E6", label: "Jasnoniebieski 2" },
  { id: "deco_25", color: "#6495ED", label: "Jasnoniebieski 3" },
  { id: "deco_26", color: "#4682B4", label: "Stalowoniebiesk" },
  { id: "deco_27", color: "#D8BFD8", label: "Jasnofioletowy" },
  { id: "deco_28", color: "#9B59B6", label: "Fioletowy" },
  { id: "deco_29", color: "#4A0080", label: "Ciemnofioletowy" },
  { id: "deco_30", color: "#FFB6C1", label: "Rozowy 4" },
  { id: "deco_31", color: "#DDA0DD", label: "Jasnofioletowy 2" },
  { id: "deco_32", color: "#912C87", label: "Ciemnofioletowy solid" },
]

export const BG_CONTENT_LIMIT = 100

export function getBgColor(id: string): string | undefined {
  return FB_BACKGROUNDS.find(b => b.id === id)?.color
}

export function BackgroundPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const btnRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  const openPicker = useCallback(() => {
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      const popW = 280
      let left = rect.left
      if (left + popW > window.innerWidth - 8) left = window.innerWidth - popW - 8
      if (left < 8) left = 8
      const spaceBelow = window.innerHeight - rect.bottom
      const top = spaceBelow > 320 ? rect.bottom + 4 : rect.top - 320
      setPos({ top, left })
    }
    setOpen(true)
  }, [])

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (
        popoverRef.current && !popoverRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onMouseDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const select = (id: string) => {
    onChange(id)
    setOpen(false)
  }

  const activeBg = FB_BACKGROUNDS.find(b => b.id === value)

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        className="h-9 w-full rounded-md border border-primary/10 bg-secondary/50 flex items-center justify-center focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        onClick={openPicker}
        title={activeBg ? activeBg.label : "Brak tla"}
      >
        {activeBg ? (
          <div
            className="w-6 h-6 rounded-sm border border-primary/20"
            style={{ backgroundColor: activeBg.color }}
          />
        ) : (
          <Type className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {open && (
        <div
          ref={popoverRef}
          className="fixed z-[100] bg-popover border border-primary/10 rounded-xl shadow-2xl p-3 w-[280px]"
          style={{ top: pos.top, left: pos.left }}
        >
          <div className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider mb-2">
            Tlo posta (maks. {BG_CONTENT_LIMIT} znakow)
          </div>

          {/* None option */}
          <button
            type="button"
            className={`w-full text-left text-xs px-2 py-1.5 rounded-md mb-2 transition-colors ${
              !value ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-secondary"
            }`}
            onClick={() => select("")}
          >
            Brak tla
          </button>

          {/* Solid colors */}
          <div className="text-[10px] text-muted-foreground mb-1.5">Jednolite</div>
          <div className="flex gap-1.5 mb-3">
            {FB_BACKGROUNDS.filter(b => !b.id.startsWith("deco_")).map(bg => (
              <button
                key={bg.id}
                type="button"
                className={`w-8 h-8 rounded-md border-2 transition-all ${
                  value === bg.id ? "border-primary scale-110" : "border-transparent hover:border-primary/30"
                }`}
                style={{ backgroundColor: bg.color }}
                onClick={() => select(bg.id)}
                title={bg.label}
              />
            ))}
          </div>

          {/* Decorative */}
          <div className="text-[10px] text-muted-foreground mb-1.5">Dekoracyjne</div>
          <div className="grid grid-cols-11 gap-1 max-h-[160px] overflow-y-auto">
            {FB_BACKGROUNDS.filter(b => b.id.startsWith("deco_")).map(bg => (
              <button
                key={bg.id}
                type="button"
                className={`w-[22px] h-[22px] rounded-sm border transition-all ${
                  value === bg.id ? "border-primary ring-1 ring-primary scale-110" : "border-primary/10 hover:border-primary/40"
                }`}
                style={{ backgroundColor: bg.color }}
                onClick={() => select(bg.id)}
                title={bg.label}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export function ClockPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false)
  const [phase, setPhase] = useState<"hour" | "minute">("hour")
  const [selectedHour, setSelectedHour] = useState(12)
  const [selectedMinute, setSelectedMinute] = useState(0)
  const btnRef = useRef<HTMLButtonElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragging = useRef(false)
  const [pos, setPos] = useState({ top: 0, left: 0 })

  const pad = (n: number) => n.toString().padStart(2, "0")
  const SIZE = 220
  const CENTER = SIZE / 2
  const RADIUS = 85
  const INNER_R = 55

  const openPicker = useCallback(() => {
    if (value) {
      const [h, m] = value.split(":").map(Number)
      setSelectedHour(h)
      setSelectedMinute(m)
    } else {
      setSelectedHour(12)
      setSelectedMinute(0)
    }
    setPhase("hour")
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect()
      const popW = 252
      let left = rect.right - popW
      if (left < 8) left = 8
      const spaceBelow = window.innerHeight - rect.bottom
      const top = spaceBelow > 340 ? rect.bottom + 4 : rect.top - 340
      setPos({ top, left })
    }
    setOpen(true)
  }, [value])

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (
        popoverRef.current && !popoverRef.current.contains(e.target as Node) &&
        btnRef.current && !btnRef.current.contains(e.target as Node)
      ) {
        setOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("mousedown", onMouseDown)
      document.removeEventListener("keydown", onKey)
    }
  }, [open])

  const getAngle = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return 0
    const rect = svg.getBoundingClientRect()
    const x = e.clientX - rect.left - CENTER
    const y = e.clientY - rect.top - CENTER
    let angle = Math.atan2(x, -y) * (180 / Math.PI)
    if (angle < 0) angle += 360
    return angle
  }, [])

  const getDist = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current
    if (!svg) return 0
    const rect = svg.getBoundingClientRect()
    const x = e.clientX - rect.left - CENTER
    const y = e.clientY - rect.top - CENTER
    return Math.sqrt(x * x + y * y)
  }, [])

  const handleClockInteraction = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    const angle = getAngle(e)
    if (phase === "hour") {
      let hour = Math.round(angle / 30)
      if (hour === 0) hour = 12
      const dist = getDist(e)
      if (dist < (RADIUS + INNER_R) / 2) {
        hour = hour === 12 ? 0 : hour + 12
      }
      setSelectedHour(hour)
    } else {
      let minute = Math.round(angle / 6)
      if (minute === 60) minute = 0
      setSelectedMinute(minute)
    }
  }, [phase, getAngle, getDist])

  const handleMouseDown = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    dragging.current = true
    handleClockInteraction(e)
  }, [handleClockInteraction])

  const handleMouseMove = useCallback((e: React.MouseEvent<SVGSVGElement>) => {
    if (!dragging.current) return
    handleClockInteraction(e)
  }, [handleClockInteraction])

  const latestHour = useRef(selectedHour)
  const latestMinute = useRef(selectedMinute)
  latestHour.current = selectedHour
  latestMinute.current = selectedMinute

  const handleMouseUp = useCallback(() => {
    if (!dragging.current) return
    dragging.current = false
    if (phase === "hour") {
      setPhase("minute")
    } else {
      onChange(`${pad(latestHour.current)}:${pad(latestMinute.current)}`)
      setOpen(false)
    }
  }, [phase, onChange])

  const handAngle = phase === "hour"
    ? ((selectedHour % 12) || 12) * 30
    : selectedMinute * 6
  const isInner = phase === "hour" && (selectedHour === 0 || selectedHour > 12)
  const handLen = isInner ? INNER_R : RADIUS - 8
  const handX = CENTER + handLen * Math.sin((handAngle * Math.PI) / 180)
  const handY = CENTER - handLen * Math.cos((handAngle * Math.PI) / 180)

  const numPos = (index: number, count: number, r: number) => {
    const angle = (index * (360 / count)) * (Math.PI / 180)
    return {
      x: CENTER + r * Math.sin(angle),
      y: CENTER - r * Math.cos(angle),
    }
  }

  const hours12 = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
  const hours24inner = [0, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
  const minuteLabels = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]

  return (
    <div className="relative">
      <button
        ref={btnRef}
        type="button"
        className="h-9 w-full rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs text-left flex items-center justify-between focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
        onClick={openPicker}
      >
        <span className={value ? "text-foreground" : "text-muted-foreground"}>
          {value || "--:--"}
        </span>
        <Clock className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
      </button>

      {open && (
        <div
          ref={popoverRef}
          className="fixed z-[100] bg-popover border border-primary/10 rounded-xl shadow-2xl p-4 w-[252px]"
          style={{ top: pos.top, left: pos.left }}
        >
          <div className="flex items-center justify-center gap-1 mb-3">
            <button
              type="button"
              className={`text-lg font-semibold px-2.5 py-0.5 rounded-md transition-colors ${phase === "hour" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => setPhase("hour")}
            >
              {pad(selectedHour)}
            </button>
            <span className="text-lg font-semibold text-muted-foreground">:</span>
            <button
              type="button"
              className={`text-lg font-semibold px-2.5 py-0.5 rounded-md transition-colors ${phase === "minute" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"}`}
              onClick={() => setPhase("minute")}
            >
              {pad(selectedMinute)}
            </button>
          </div>

          <svg
            ref={svgRef}
            width={SIZE}
            height={SIZE}
            className="select-none cursor-pointer mx-auto block"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={() => { dragging.current = false }}
          >
            <circle cx={CENTER} cy={CENTER} r={CENTER - 2} fill="none" stroke="var(--primary)" strokeWidth={1.5} opacity={0.25} />
            <circle cx={CENTER} cy={CENTER} r={CENTER - 4} fill="var(--secondary)" opacity={0.5} />

            {Array.from({ length: 12 }, (_, i) => {
              const a = (i * 30) * (Math.PI / 180)
              const outer = CENTER - 6
              const inner = CENTER - 14
              return (
                <line
                  key={`tick-${i}`}
                  x1={CENTER + inner * Math.sin(a)} y1={CENTER - inner * Math.cos(a)}
                  x2={CENTER + outer * Math.sin(a)} y2={CENTER - outer * Math.cos(a)}
                  stroke="var(--primary)" strokeWidth={1.5} opacity={0.3}
                  className="pointer-events-none"
                />
              )
            })}

            <line
              x1={CENTER} y1={CENTER}
              x2={handX} y2={handY}
              stroke="var(--primary)" strokeWidth={2} strokeLinecap="round"
            />
            <circle cx={CENTER} cy={CENTER} r={5} fill="var(--primary)" />
            <circle cx={handX} cy={handY} r={16} fill="var(--primary)" opacity={0.25} />
            <circle cx={handX} cy={handY} r={16} fill="none" stroke="var(--primary)" strokeWidth={1} opacity={0.4} />

            {phase === "hour" ? (
              <>
                {hours12.map((h, i) => {
                  const { x, y } = numPos(i, 12, RADIUS)
                  const isSelected = selectedHour === h
                  return (
                    <text
                      key={h} x={x} y={y}
                      textAnchor="middle" dominantBaseline="central"
                      fontSize={14} fontFamily="inherit"
                      fill={isSelected ? "var(--primary)" : "var(--foreground)"}
                      fontWeight={isSelected ? 700 : 500}
                      className="pointer-events-none"
                    >
                      {h}
                    </text>
                  )
                })}
                {hours24inner.map((h, i) => {
                  const { x, y } = numPos(i, 12, INNER_R)
                  const isSelected = selectedHour === h
                  return (
                    <text
                      key={h} x={x} y={y}
                      textAnchor="middle" dominantBaseline="central"
                      fontSize={10} fontFamily="inherit"
                      fill={isSelected ? "var(--primary)" : "var(--muted-foreground)"}
                      fontWeight={isSelected ? 700 : 400}
                      className="pointer-events-none"
                    >
                      {h}
                    </text>
                  )
                })}
              </>
            ) : (
              <>
                {minuteLabels.map((m, i) => {
                  const { x, y } = numPos(i, 12, RADIUS)
                  const isSelected = selectedMinute === m
                  return (
                    <text
                      key={m} x={x} y={y}
                      textAnchor="middle" dominantBaseline="central"
                      fontSize={14} fontFamily="inherit"
                      fill={isSelected ? "var(--primary)" : "var(--foreground)"}
                      fontWeight={isSelected ? 700 : 500}
                      className="pointer-events-none"
                    >
                      {pad(m)}
                    </text>
                  )
                })}
                {Array.from({ length: 60 }, (_, m) => {
                  if (m % 5 === 0) return null
                  const { x, y } = numPos(m, 60, RADIUS - 6)
                  return (
                    <circle
                      key={m} cx={x} cy={y} r={1.2}
                      fill="var(--muted-foreground)" opacity={0.4}
                      className="pointer-events-none"
                    />
                  )
                })}
              </>
            )}
          </svg>

          <div className="flex items-center justify-between mt-3 px-1">
            <button
              type="button"
              className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => { onChange(""); setOpen(false) }}
            >
              Wyczysc
            </button>
            <button
              type="button"
              className="text-[11px] text-primary hover:text-primary/80 font-semibold transition-colors"
              onClick={() => { onChange(`${pad(selectedHour)}:${pad(selectedMinute)}`); setOpen(false) }}
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

//                          #   URL   Content  Bg  Date  Time  Del
export const DEFAULT_COL_WIDTHS = [40, 240, 300, 50, 140, 90, 40]
export const MIN_COL_WIDTHS = [40, 120, 120, 40, 110, 70, 40]

export function colTemplate(widths: number[]) {
  return widths.map(w => `${w}px`).join(" ")
}

export function SpreadsheetRow({ row, index, total, onUpdate, onRemove, colWidths }: {
  row: GroupRow
  index: number
  total: number
  onUpdate: (index: number, field: keyof GroupRow, value: string) => void
  onRemove: (index: number) => void
  colWidths: number[]
}) {
  const hasBg = !!row.background_style
  const contentLimit = hasBg ? BG_CONTENT_LIMIT : undefined

  return (
    <div className="grid gap-0 px-0 py-2.5 items-start" style={{ gridTemplateColumns: colTemplate(colWidths) }}>
      <span className="text-xs text-muted-foreground font-mono pt-2 px-2 text-center">{index + 1}.</span>
      <div className="px-1.5">
        <Input
          placeholder="https://facebook.com/groups/..."
          className="bg-secondary/50 border-primary/10 h-9 text-xs"
          value={row.url}
          onChange={(e) => onUpdate(index, "url", e.target.value)}
          required
        />
      </div>
      <div className="px-1.5">
        <div className="relative">
          <textarea
            className={`flex min-h-[36px] w-full rounded-md border bg-secondary/50 px-3 py-2 text-xs focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-y ${
              hasBg && row.content.length > BG_CONTENT_LIMIT
                ? "border-rose-500/50"
                : "border-primary/10"
            }`}
            placeholder="Tresc posta..."
            value={row.content}
            onChange={(e) => {
              const val = contentLimit ? e.target.value.slice(0, contentLimit) : e.target.value
              onUpdate(index, "content", val)
            }}
            maxLength={contentLimit}
            required
          />
          {hasBg && (
            <span className={`absolute bottom-1 right-2 text-[9px] ${
              row.content.length >= BG_CONTENT_LIMIT ? "text-rose-500" : "text-muted-foreground/50"
            }`}>
              {row.content.length}/{BG_CONTENT_LIMIT}
            </span>
          )}
        </div>
      </div>
      <div className="px-1">
        <BackgroundPicker
          value={row.background_style}
          onChange={(v) => onUpdate(index, "background_style", v)}
        />
      </div>
      <div className="px-1.5">
        <input
          type="date"
          className="h-9 w-full rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          value={row.planned_date}
          onChange={(e) => onUpdate(index, "planned_date", e.target.value)}
        />
      </div>
      <div className="px-1.5">
        <ClockPicker
          value={row.planned_time}
          onChange={(v) => onUpdate(index, "planned_time", v)}
        />
      </div>
      <div className="flex justify-center">
        {total > 1 ? (
          <Button type="button" variant="ghost" size="icon" onClick={() => onRemove(index)} className="text-rose-500/60 hover:text-rose-500 h-9 w-9">
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        ) : <span />}
      </div>
    </div>
  )
}

// Exponential spread steps: minutes -> hours -> days
export const SPREAD_STEPS = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120, 180, 240, 360, 480, 720, 1440, 2880, 4320]

export function formatSpread(minutes: number): string {
  if (minutes === 0) return "brak"
  if (minutes < 60) return `\u00B1${minutes} min`
  if (minutes < 1440) {
    const h = minutes / 60
    return `\u00B1${h % 1 === 0 ? h : h.toFixed(1)}h`
  }
  const d = minutes / 1440
  if (d === 1) return `\u00B11 dzien`
  return `\u00B1${d % 1 === 0 ? d : d.toFixed(1)} dni`
}

export function ScheduleGenerator({ onGenerate }: { onGenerate: (rows: GroupRow[]) => void }) {
  const [rawText, setRawText] = useState("")
  const [startHour, setStartHour] = useState("08:00")
  const [endHour, setEndHour] = useState("20:00")
  const [spreadIdx, setSpreadIdx] = useState(3)

  const spreadMin = SPREAD_STEPS[spreadIdx]

  const pad = (n: number) => n.toString().padStart(2, "0")

  const parseUrls = (text: string): string[] => {
    const regex = /(https?:\/\/)?(www\.|m\.)?facebook\.com\/groups\/[^\s)]+/gi
    const matches = text.match(regex) || []
    return matches.map(url => {
      let clean = url.replace(/\/+$/, "")
      if (!clean.startsWith("http")) clean = "https://" + clean
      clean = clean.replace("m.facebook.com", "www.facebook.com")
      return clean
    })
  }

  const generate = () => {
    const urls = parseUrls(rawText)
    if (urls.length === 0) return

    const [sh, sm] = startHour.split(":").map(Number)
    const [eh, em] = endHour.split(":").map(Number)
    const startMinutes = sh * 60 + sm
    const endMinutes = eh * 60 + em
    const windowMinutes = endMinutes - startMinutes

    const tomorrow = new Date()
    tomorrow.setDate(tomorrow.getDate() + 1)
    tomorrow.setHours(0, 0, 0, 0)

    let cursorDay = 0
    let cursorMin = startMinutes

    const rows: GroupRow[] = urls.map((url) => {
      const dt = new Date(tomorrow)
      dt.setDate(dt.getDate() + cursorDay)
      dt.setHours(Math.floor(cursorMin / 60), Math.round(cursorMin % 60), 0, 0)

      if (spreadMin > 0) {
        const jitter = 1 + (Math.random() * 0.2 - 0.1)
        const interval = Math.round(spreadMin * jitter)
        cursorMin += interval

        while (cursorMin > endMinutes) {
          cursorMin = cursorMin - endMinutes + startMinutes
          cursorDay++
        }
      } else {
        cursorMin += Math.round(windowMinutes / 2)
        if (cursorMin > endMinutes) {
          cursorMin = startMinutes + Math.round(windowMinutes / 2)
          cursorDay++
        }
      }

      const finalMin = dt.getHours() * 60 + dt.getMinutes()

      return {
        url,
        content: "",
        background_style: "",
        planned_date: `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`,
        planned_time: `${pad(Math.floor(finalMin / 60))}:${pad(Math.round(finalMin % 60))}`,
      }
    })

    onGenerate(rows)
  }

  const parsedCount = parseUrls(rawText).length

  return (
    <div className="border border-primary/10 rounded-lg bg-card/50 p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <ClipboardPaste className="h-4 w-4 text-primary" />
        Wklej liste grup
      </div>

      <textarea
        className="w-full min-h-[120px] rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-xs font-mono focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-y placeholder:text-muted-foreground/50"
        placeholder={"Wklej URL-e grup Facebook (po jednym w linii)...\nhttps://www.facebook.com/groups/nazwa-grupy/\nhttps://www.facebook.com/groups/inna-grupa/"}
        value={rawText}
        onChange={(e) => setRawText(e.target.value)}
      />

      {parsedCount > 0 && (
        <p className="text-[11px] text-muted-foreground">
          Rozpoznano <span className="text-primary font-semibold">{parsedCount}</span> {parsedCount === 1 ? "grupe" : parsedCount < 5 ? "grupy" : "grup"}
        </p>
      )}

      <div className="flex items-end gap-4 flex-wrap">
        <div className="space-y-1">
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Okno godzin</label>
          <div className="flex items-center gap-1">
            <input
              type="time"
              className="h-8 rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs"
              value={startHour}
              onChange={(e) => setStartHour(e.target.value)}
            />
            <span className="text-xs text-muted-foreground">-</span>
            <input
              type="time"
              className="h-8 rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs"
              value={endHour}
              onChange={(e) => setEndHour(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1 min-w-[160px]">
          <label className="text-[10px] text-muted-foreground uppercase tracking-wider flex items-center justify-between">
            <span>Rozrzut</span>
            <span className="text-primary font-semibold normal-case tracking-normal">
              {formatSpread(spreadMin)}
            </span>
          </label>
          <input
            type="range"
            min={0}
            max={SPREAD_STEPS.length - 1}
            step={1}
            value={spreadIdx}
            onChange={(e) => setSpreadIdx(Number(e.target.value))}
            className="w-full h-1.5 rounded-full appearance-none cursor-pointer bg-secondary accent-primary"
          />
        </div>
        <Button
          type="button"
          size="sm"
          className="bg-primary text-primary-foreground font-semibold h-8 px-4"
          onClick={generate}
          disabled={parsedCount === 0}
        >
          <Wand2 className="mr-1.5 h-3.5 w-3.5" />
          Generuj ({parsedCount})
        </Button>
      </div>
    </div>
  )
}

const HEADER_LABELS = ["#", "Grupa (URL)", "Tresc posta", "Tlo", "Data", "Godzina", ""]
const RESIZABLE_COLS = [1, 2, 4, 5]

export type SortDir = "asc" | "desc" | null

export function SpreadsheetHeader({ colWidths, onResizeStart, sortDir, onToggleSort }: {
  colWidths: number[]
  onResizeStart: (colIndex: number, e: React.MouseEvent) => void
  sortDir: SortDir
  onToggleSort: () => void
}) {
  const SortIcon = sortDir === "asc" ? ArrowUp : sortDir === "desc" ? ArrowDown : ArrowUpDown

  return (
    <div
      className="grid gap-0 py-2.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider border-b border-primary/5 bg-secondary/20"
      style={{ gridTemplateColumns: colTemplate(colWidths) }}
    >
      {HEADER_LABELS.map((label, i) => (
        <div key={i} className="relative px-2 select-none">
          {i === 4 ? (
            <button
              type="button"
              className="flex items-center gap-1 hover:text-primary transition-colors cursor-pointer uppercase text-[10px] font-medium tracking-wider"
              onClick={onToggleSort}
            >
              <span>{label}</span>
              <SortIcon className={`h-3 w-3 ${sortDir ? "text-primary" : ""}`} />
            </button>
          ) : (
            <span>{label}</span>
          )}
          {RESIZABLE_COLS.includes(i) && (
            <div
              className="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize hover:bg-primary/30 active:bg-primary/50 transition-colors"
              onMouseDown={(e) => onResizeStart(i, e)}
            />
          )}
        </div>
      ))}
    </div>
  )
}
