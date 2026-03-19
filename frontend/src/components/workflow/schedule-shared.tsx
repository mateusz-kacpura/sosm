"use client"

import { useState, useCallback, useRef, useEffect } from "react"
import { X, ImagePlus, Film, Plus } from "lucide-react"
import { Label } from "@/components/ui/label"
import { uploadMedia, api } from "@/lib/api"
import {
  FB_BACKGROUNDS, getBgColor,
  SPREAD_STEPS,
} from "@/app/campaigns/spreadsheet"

// ── Types ──

export interface ScheduleEntry {
  url: string
  content: string
  planned_date: string
  planned_time: string
  recurring: boolean
  recurring_days: number[]   // 0=Mon ... 6=Sun
  recurring_time: string     // "HH:MM"
  recurring_jitter: number   // 0-120 minutes
  background_style: string
  media_files: string[]
}

// ── Constants ──

export const DAY_LABELS = ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"] as const

// ── Utility functions ──

export function pad(n: number): string {
  return n.toString().padStart(2, "0")
}

export function formatJitter(minutes: number): string {
  if (minutes === 0) return "dokładnie"
  if (minutes < 60) return `\u00B1${minutes} min`
  const h = minutes / 60
  return `\u00B1${h % 1 === 0 ? h : h.toFixed(1)}h`
}

export function formatRecurringDays(days: number[]): string {
  if (days.length === 0) return "brak dni"
  if (days.length === 7) return "codziennie"
  if (days.length === 5 && [0, 1, 2, 3, 4].every((d) => days.includes(d))) return "dni robocze"
  if (days.length === 2 && [5, 6].every((d) => days.includes(d))) return "weekendy"
  return days.map((d) => DAY_LABELS[d]).join(", ")
}

// ── Schedule generator ──

export function generateSchedule<T extends ScheduleEntry>(
  urls: string[],
  defaultContent: string,
  startHour: string,
  endHour: string,
  spreadIdx: number,
  extraFields: Record<string, unknown> = {},
): T[] {
  if (urls.length === 0) return []

  const spreadMin = SPREAD_STEPS[spreadIdx]
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

  return urls.map((url) => {
    const dt = new Date(tomorrow)
    dt.setDate(dt.getDate() + cursorDay)
    dt.setHours(Math.floor(cursorMin / 60), Math.round(cursorMin % 60), 0, 0)

    if (spreadMin > 0) {
      const jitter = 1 + (Math.random() * 0.2 - 0.1)
      cursorMin += Math.round(spreadMin * jitter)
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
      content: defaultContent,
      planned_date: `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}`,
      planned_time: `${pad(Math.floor(finalMin / 60))}:${pad(Math.round(finalMin % 60))}`,
      recurring: false,
      recurring_days: [],
      recurring_time: "10:00",
      recurring_jitter: 15,
      background_style: "",
      media_files: [],
      ...extraFields,
    } as unknown as T
  })
}

// ── Popover hook ──

export function usePopover(width: number, height: number, triggerAttr: string) {
  const [state, setState] = useState({ show: false, target: 0, pos: { top: 0, left: 0 } })
  const ref = useRef<HTMLDivElement>(null)

  const open = useCallback((rowIdx: number, anchorEl: HTMLElement) => {
    const rect = anchorEl.getBoundingClientRect()
    let left = rect.left
    if (left + width > window.innerWidth - 8) left = window.innerWidth - width - 8
    if (left < 8) left = 8
    const spaceBelow = window.innerHeight - rect.bottom
    const top = spaceBelow > height ? rect.bottom + 4 : rect.top - height
    setState({ show: true, target: rowIdx, pos: { top, left } })
  }, [width, height])

  const close = useCallback(() => setState((prev) => ({ ...prev, show: false })), [])

  useEffect(() => {
    if (!state.show) return
    const onMouseDown = (e: MouseEvent) => {
      const el = e.target as HTMLElement
      if (ref.current?.contains(el)) return
      if (el.closest(`[${triggerAttr}]`)) return
      close()
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") close() }
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("keydown", onKey)
    return () => { document.removeEventListener("mousedown", onMouseDown); document.removeEventListener("keydown", onKey) }
  }, [state.show, triggerAttr, close])

  return { show: state.show, target: state.target, pos: state.pos, ref, open, close }
}

// ── Shared components ──

interface RecurringSubRowProps {
  entry: ScheduleEntry
  index: number
  onUpdate: (index: number, updates: Partial<ScheduleEntry>) => void
  onToggleDay: (index: number, day: number) => void
}

export function RecurringSubRow({ entry, index, onUpdate, onToggleDay }: RecurringSubRowProps) {
  return (
    <div className="bg-card border-t border-primary/5 px-3 py-2 flex items-center gap-3 flex-wrap">
      <span className="text-[10px] text-muted-foreground uppercase tracking-wider shrink-0">Powtarzaj:</span>
      <div className="flex items-center gap-1">
        {DAY_LABELS.map((label, dayIdx) => (
          <button
            key={dayIdx}
            onClick={() => onToggleDay(index, dayIdx)}
            className={`h-6 w-7 rounded text-[10px] font-medium transition-colors ${
              entry.recurring_days.includes(dayIdx)
                ? "bg-primary text-primary-foreground"
                : "bg-secondary/50 text-muted-foreground hover:bg-secondary"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <span className="text-[10px] text-muted-foreground shrink-0">o</span>
      <input
        type="time"
        value={entry.recurring_time}
        onChange={(e) => onUpdate(index, { recurring_time: e.target.value })}
        className="h-6 rounded-md border border-primary/10 bg-secondary/50 px-1.5 text-[11px] w-[70px]"
      />
      <div className="flex items-center gap-1.5 shrink-0" title="Losowość czasu publikacji">
        <span className="text-[10px] text-muted-foreground">🎲</span>
        <input
          type="range"
          min={0} max={120} step={5}
          value={entry.recurring_jitter}
          onChange={(e) => onUpdate(index, { recurring_jitter: Number(e.target.value) })}
          className="w-16 h-1 rounded-full appearance-none cursor-pointer bg-secondary accent-primary"
        />
        <span className="text-[10px] text-primary font-semibold w-12">
          {formatJitter(entry.recurring_jitter)}
        </span>
      </div>
      <span className="text-[10px] text-muted-foreground ml-auto">
        {formatRecurringDays(entry.recurring_days)}
      </span>
    </div>
  )
}

interface BgPickerPopoverProps {
  entries: ScheduleEntry[]
  target: number
  pos: { top: number; left: number }
  popoverRef: React.RefObject<HTMLDivElement | null>
  onUpdate: (index: number, updates: Partial<ScheduleEntry>) => void
  onClose: () => void
  label?: string
}

export function BgPickerPopover({ entries, target, pos, popoverRef, onUpdate, onClose, label = "Tło" }: BgPickerPopoverProps) {
  const activeBg = entries[target]?.background_style || ""
  return (
    <div
      ref={popoverRef}
      className="fixed z-[70] bg-card border border-primary/10 rounded-lg shadow-xl p-3"
      style={{ top: pos.top, left: pos.left, width: 280 }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
          {label}
        </span>
        <button
          onClick={() => { onUpdate(target, { background_style: "" }); onClose() }}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          Brak
        </button>
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {FB_BACKGROUNDS.map((bg) => (
          <button
            key={bg.id}
            onClick={() => { onUpdate(target, { background_style: bg.id, media_files: [] }); onClose() }}
            className={`h-7 w-7 rounded-md border transition-all cursor-pointer hover:scale-110 ${
              activeBg === bg.id ? "border-primary ring-2 ring-primary/30 scale-110" : "border-primary/10"
            }`}
            style={{ backgroundColor: bg.color }}
            title={bg.label}
          />
        ))}
      </div>
    </div>
  )
}

interface MediaPickerPopoverProps {
  entries: ScheduleEntry[]
  target: number
  pos: { top: number; left: number }
  popoverRef: React.RefObject<HTMLDivElement | null>
  allUploadedFiles: string[]
  onUpdate: (index: number, updates: Partial<ScheduleEntry>) => void
  onUpload: (e: React.ChangeEvent<HTMLInputElement>, rowIdx: number) => void
  uploading: boolean
  onClose: () => void
  label?: string
}

export function MediaPickerPopover({
  entries, target, pos, popoverRef, allUploadedFiles,
  onUpdate, onUpload, uploading, onClose, label = "Media",
}: MediaPickerPopoverProps) {
  const entry = entries[target]
  if (!entry) return null
  const entryMedia = entry.media_files || []
  const libraryFiles = allUploadedFiles.filter((f) => !entryMedia.includes(f))

  return (
    <div
      ref={popoverRef}
      className="fixed z-[70] bg-card border border-primary/10 rounded-lg shadow-xl p-3"
      style={{ top: pos.top, left: pos.left, width: 300 }}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
          {label}
        </span>
        <button
          onClick={() => { onUpdate(target, { media_files: [] }); onClose() }}
          className="text-[10px] text-muted-foreground hover:text-foreground"
        >
          Brak
        </button>
      </div>

      {entryMedia.length > 0 && (
        <div className="mb-2">
          <div className="flex flex-wrap gap-1.5">
            {entryMedia.map((filename) => {
              const isVideo = filename.endsWith(".mp4") || filename.endsWith(".mov")
              return (
                <div key={filename} className="relative group/thumb">
                  <div className="h-12 w-12 rounded border border-primary/20 bg-secondary/50 flex items-center justify-center overflow-hidden">
                    {isVideo ? (
                      <Film className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <img
                        src={`/api/media/file/${filename}`}
                        alt={filename}
                        className="h-full w-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                      />
                    )}
                  </div>
                  <button
                    onClick={() => onUpdate(target, { media_files: entryMedia.filter((f) => f !== filename) })}
                    className="absolute -top-1 -right-1 h-3.5 w-3.5 rounded-full bg-rose-500 text-white flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-opacity"
                  >
                    <X className="h-2 w-2" />
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {libraryFiles.length > 0 && (
        <div className="mb-2">
          <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Z biblioteki</span>
          <div className="flex flex-wrap gap-1.5 mt-1">
            {libraryFiles.map((filename) => {
              const isVideo = filename.endsWith(".mp4") || filename.endsWith(".mov")
              return (
                <button
                  key={filename}
                  onClick={() => onUpdate(target, { media_files: [...entryMedia, filename], background_style: "" })}
                  className="h-10 w-10 rounded border border-dashed border-primary/20 bg-secondary/30 flex items-center justify-center overflow-hidden hover:border-primary/50 hover:bg-secondary/60 transition-colors cursor-pointer"
                  title={filename.replace(/^[a-f0-9]+_/, "")}
                >
                  {isVideo ? (
                    <Film className="h-3.5 w-3.5 text-muted-foreground" />
                  ) : (
                    <img
                      src={`/api/media/file/${filename}`}
                      alt={filename}
                      className="h-full w-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                    />
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}

      <label className={`flex items-center gap-1.5 text-[10px] cursor-pointer transition-colors ${uploading ? "text-muted-foreground" : "text-primary hover:text-primary/80"}`}>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime"
          multiple
          onChange={(e) => onUpload(e, target)}
          disabled={uploading}
          className="hidden"
        />
        <Plus className="h-3 w-3" />
        {uploading ? "Przesyłanie..." : "Upload nowy plik"}
      </label>
    </div>
  )
}

interface DefaultMediaSectionProps {
  files: string[]
  onUpload: (e: React.ChangeEvent<HTMLInputElement>) => void
  onRemove: (filename: string) => void
  uploading: boolean
  onApplyAll?: () => void
  hasEntries: boolean
}

export function DefaultMediaSection({ files, onUpload, onRemove, uploading, onApplyAll, hasEntries }: DefaultMediaSectionProps) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label className="text-xs flex items-center gap-1.5">
          <ImagePlus className="h-3.5 w-3.5 text-primary" />
          Media (zdjęcia / filmy)
        </Label>
        <label className={`text-[10px] cursor-pointer transition-colors ${uploading ? "text-muted-foreground" : "text-primary hover:text-primary/80"}`}>
          <input
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime"
            multiple
            onChange={onUpload}
            disabled={uploading}
            className="hidden"
          />
          {uploading ? "Przesyłanie..." : "+ Dodaj pliki"}
        </label>
      </div>
      {files.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {files.map((filename) => {
            const isVideo = filename.endsWith(".mp4") || filename.endsWith(".mov")
            return (
              <div key={filename} className="relative group">
                <div className="h-16 w-16 rounded-md border border-primary/10 bg-secondary/50 flex items-center justify-center overflow-hidden">
                  {isVideo ? (
                    <Film className="h-6 w-6 text-muted-foreground" />
                  ) : (
                    <img
                      src={`/api/media/file/${filename}`}
                      alt={filename}
                      className="h-full w-full object-cover"
                      onError={(e) => { (e.target as HTMLImageElement).style.display = "none" }}
                    />
                  )}
                </div>
                <button
                  onClick={() => onRemove(filename)}
                  className="absolute -top-1.5 -right-1.5 h-4 w-4 rounded-full bg-rose-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
                <p className="text-[8px] text-muted-foreground truncate w-16 mt-0.5" title={filename}>
                  {filename.replace(/^[a-f0-9]+_/, "")}
                </p>
              </div>
            )
          })}
        </div>
      )}
      {files.length > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-[10px] text-muted-foreground">
            {files.length} {files.length === 1 ? "plik" : files.length < 5 ? "pliki" : "plików"}
            {" · "}Media i tło wzajemnie się wykluczają
          </p>
          {hasEntries && onApplyAll && (
            <button
              onClick={onApplyAll}
              className="text-[10px] text-primary hover:text-primary/80 transition-colors"
            >
              Zastosuj do wszystkich
            </button>
          )}
        </div>
      )}
    </div>
  )
}
