"use client"

import { useState, useCallback, useRef, useEffect, useMemo, Fragment } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  X, Maximize2, Minimize2, ClipboardPaste, Wand2, Trash2, Plus, RefreshCw,
  ImagePlus, Film,
} from "lucide-react"
import { api, uploadMedia } from "@/lib/api"
import {
  FB_BACKGROUNDS, getBgColor,
  SPREAD_STEPS, formatSpread,
} from "@/app/campaigns/spreadsheet"

const DAY_LABELS = ["Pn", "Wt", "Śr", "Cz", "Pt", "Sb", "Nd"] as const
// 0=Monday ... 6=Sunday (ISO week)

export interface GroupEntry {
  url: string
  content: string
  planned_date: string
  planned_time: string
  recurring: boolean
  recurring_days: number[]  // 0=Mon ... 6=Sun
  recurring_time: string    // "HH:MM"
  recurring_jitter: number  // 0-120 minutes of random deviation
  background_style: string  // per-group bg override (empty = use global)
  media_files: string[]     // uploaded filenames
}

export interface PostGroupsConfig {
  groups: GroupEntry[]
  default_content: string
  background_style: string  // kept for backward compat, not used in new UI
  active_hours_start: string
  active_hours_end: string
  spread_minutes: number
  publish_as_fanpage: string  // fanpage URL or "" (personal profile)
  default_media_files: string[]  // shared media for all groups
}

interface GroupScheduleModalProps {
  config: PostGroupsConfig
  onSave: (config: PostGroupsConfig) => void
  onClose: () => void
}

function parseGroupUrls(text: string): string[] {
  const regex = /(https?:\/\/)?(www\.|m\.)?facebook\.com\/groups\/[^\s)]+/gi
  const matches = text.match(regex) || []
  return matches.map((url) => {
    let clean = url.replace(/\/+$/, "")
    if (!clean.startsWith("http")) clean = "https://" + clean
    clean = clean.replace("m.facebook.com", "www.facebook.com")
    return clean
  })
}

function pad(n: number) {
  return n.toString().padStart(2, "0")
}

function makeEmptyGroup(): GroupEntry {
  return { url: "", content: "", planned_date: "", planned_time: "", recurring: false, recurring_days: [], recurring_time: "10:00", recurring_jitter: 15, background_style: "", media_files: [] }
}

function formatJitter(minutes: number): string {
  if (minutes === 0) return "dokładnie"
  if (minutes < 60) return `\u00B1${minutes} min`
  const h = minutes / 60
  return `\u00B1${h % 1 === 0 ? h : h.toFixed(1)}h`
}

function generateSchedule(
  urls: string[],
  defaultContent: string,
  startHour: string,
  endHour: string,
  spreadIdx: number,
): GroupEntry[] {
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
    }
  })
}

function formatRecurringDays(days: number[]): string {
  if (days.length === 0) return "brak dni"
  if (days.length === 7) return "codziennie"
  if (days.length === 5 && [0,1,2,3,4].every((d) => days.includes(d))) return "dni robocze"
  if (days.length === 2 && [5,6].every((d) => days.includes(d))) return "weekendy"
  return days.map((d) => DAY_LABELS[d]).join(", ")
}

export function GroupScheduleModal({ config, onSave, onClose }: GroupScheduleModalProps) {
  const [fullscreen, setFullscreen] = useState(false)
  const [groups, setGroups] = useState<GroupEntry[]>(() =>
    (config.groups || []).map((g) => ({
      url: g.url || "",
      content: g.content || "",
      planned_date: g.planned_date || "",
      planned_time: g.planned_time || "",
      recurring: g.recurring ?? false,
      recurring_days: g.recurring_days || [],
      recurring_time: g.recurring_time || "10:00",
      recurring_jitter: g.recurring_jitter ?? 15,
      background_style: g.background_style || "",
      media_files: g.media_files || [],
    }))
  )
  const [defaultContent, setDefaultContent] = useState(config.default_content || "")
  const [activeHoursStart, setActiveHoursStart] = useState(config.active_hours_start || "08:00")
  const [activeHoursEnd, setActiveHoursEnd] = useState(config.active_hours_end || "20:00")
  const [spreadIdx, setSpreadIdx] = useState(() => {
    const idx = SPREAD_STEPS.indexOf(config.spread_minutes)
    return idx >= 0 ? idx : 3
  })
  const [publishAsFanpage, setPublishAsFanpage] = useState(config.publish_as_fanpage || "")
  const [defaultMediaFiles, setDefaultMediaFiles] = useState<string[]>(config.default_media_files || [])
  const [mediaUploading, setMediaUploading] = useState(false)
  const [rawText, setRawText] = useState("")
  const [showBgPicker, setShowBgPicker] = useState(false)
  const [bgPickerTarget, setBgPickerTarget] = useState<number>(0)
  const bgPopoverRef = useRef<HTMLDivElement>(null)
  const [bgPos, setBgPos] = useState({ top: 0, left: 0 })
  const [showMediaPicker, setShowMediaPicker] = useState(false)
  const [mediaPickerTarget, setMediaPickerTarget] = useState<number>(0)
  const mediaPopoverRef = useRef<HTMLDivElement>(null)
  const [mediaPos, setMediaPos] = useState({ top: 0, left: 0 })

  const spreadMin = SPREAD_STEPS[spreadIdx]
  const parsedCount = parseGroupUrls(rawText).length

  // All unique uploaded files: default + per-group (for library picker)
  const allUploadedFiles = useMemo(() => {
    const set = new Set([...defaultMediaFiles])
    groups.forEach((g) => g.media_files.forEach((f) => set.add(f)))
    return Array.from(set)
  }, [defaultMediaFiles, groups])

  const openBgPicker = useCallback((rowIdx: number, anchorEl: HTMLElement) => {
    const rect = anchorEl.getBoundingClientRect()
    const popW = 280
    let left = rect.left
    if (left + popW > window.innerWidth - 8) left = window.innerWidth - popW - 8
    if (left < 8) left = 8
    const spaceBelow = window.innerHeight - rect.bottom
    const top = spaceBelow > 320 ? rect.bottom + 4 : rect.top - 320
    setBgPos({ top, left })
    setBgPickerTarget(rowIdx)
    setShowBgPicker(true)
  }, [])

  useEffect(() => {
    if (!showBgPicker) return
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (bgPopoverRef.current?.contains(target)) return
      if (target.closest("[data-bg-row-btn]")) return
      setShowBgPicker(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setShowBgPicker(false) }
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("keydown", onKey)
    return () => { document.removeEventListener("mousedown", onMouseDown); document.removeEventListener("keydown", onKey) }
  }, [showBgPicker])

  const openMediaPicker = useCallback((rowIdx: number, anchorEl: HTMLElement) => {
    const rect = anchorEl.getBoundingClientRect()
    const popW = 300
    let left = rect.left
    if (left + popW > window.innerWidth - 8) left = window.innerWidth - popW - 8
    if (left < 8) left = 8
    const spaceBelow = window.innerHeight - rect.bottom
    const top = spaceBelow > 280 ? rect.bottom + 4 : rect.top - 280
    setMediaPos({ top, left })
    setMediaPickerTarget(rowIdx)
    setShowMediaPicker(true)
  }, [])

  useEffect(() => {
    if (!showMediaPicker) return
    const onMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (mediaPopoverRef.current?.contains(target)) return
      if (target.closest("[data-media-row-btn]")) return
      setShowMediaPicker(false)
    }
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setShowMediaPicker(false) }
    document.addEventListener("mousedown", onMouseDown)
    document.addEventListener("keydown", onKey)
    return () => { document.removeEventListener("mousedown", onMouseDown); document.removeEventListener("keydown", onKey) }
  }, [showMediaPicker])

  const handleGenerate = useCallback(() => {
    const urls = parseGroupUrls(rawText)
    if (urls.length === 0) return
    const newEntries = generateSchedule(urls, defaultContent, activeHoursStart, activeHoursEnd, spreadIdx)
    setGroups((prev) => [...prev, ...newEntries])
    setRawText("")
  }, [rawText, defaultContent, activeHoursStart, activeHoursEnd, spreadIdx])

  const applyDefaultToEmpty = useCallback(() => {
    if (!defaultContent) return
    setGroups((prev) => prev.map((g) => g.content ? g : { ...g, content: defaultContent }))
  }, [defaultContent])

  const removeGroup = useCallback((index: number) => {
    setGroups((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const updateGroup = useCallback((index: number, updates: Partial<GroupEntry>) => {
    setGroups((prev) => prev.map((g, i) => i === index ? { ...g, ...updates } : g))
  }, [])

  const toggleRecurringDay = useCallback((index: number, day: number) => {
    setGroups((prev) => prev.map((g, i) => {
      if (i !== index) return g
      const days = g.recurring_days.includes(day)
        ? g.recurring_days.filter((d) => d !== day)
        : [...g.recurring_days, day].sort()
      return { ...g, recurring_days: days }
    }))
  }, [])

  const handleMediaUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files
    if (!fileList || fileList.length === 0) return
    setMediaUploading(true)
    try {
      const result = await uploadMedia(Array.from(fileList))
      const newNames = (result.files || []).map((f: any) => f.filename)
      setDefaultMediaFiles((prev) => [...prev, ...newNames])
    } catch (err) {
      console.error("Media upload failed:", err)
    } finally {
      setMediaUploading(false)
      e.target.value = ""
    }
  }, [])

  const removeDefaultMedia = useCallback((filename: string) => {
    setDefaultMediaFiles((prev) => prev.filter((f) => f !== filename))
    api.media.delete(filename).catch(() => {})
  }, [])

  const handlePerGroupMediaUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>, rowIdx: number) => {
    const fileList = e.target.files
    if (!fileList || fileList.length === 0) return
    setMediaUploading(true)
    try {
      const result = await uploadMedia(Array.from(fileList))
      const newNames = (result.files || []).map((f: any) => f.filename)
      setGroups((prev) => prev.map((g, i) =>
        i === rowIdx ? { ...g, media_files: [...g.media_files, ...newNames], background_style: "" } : g
      ))
    } catch (err) {
      console.error("Media upload failed:", err)
    } finally {
      setMediaUploading(false)
      e.target.value = ""
    }
  }, [])

  const applyMediaToAll = useCallback(() => {
    if (defaultMediaFiles.length === 0) return
    setGroups((prev) => prev.map((g) => ({ ...g, media_files: [...defaultMediaFiles], background_style: g.media_files.length > 0 || defaultMediaFiles.length > 0 ? "" : g.background_style })))
  }, [defaultMediaFiles])

  const handleSave = useCallback(() => {
    onSave({
      groups,
      default_content: defaultContent,
      background_style: "",
      active_hours_start: activeHoursStart,
      active_hours_end: activeHoursEnd,
      spread_minutes: spreadMin,
      publish_as_fanpage: publishAsFanpage,
      default_media_files: defaultMediaFiles,
    })
    onClose()
  }, [groups, defaultContent, activeHoursStart, activeHoursEnd, spreadMin, publishAsFanpage, defaultMediaFiles, onSave, onClose])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !showBgPicker && !showMediaPicker) onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose, showBgPicker, showMediaPicker])

  const recurringCount = groups.filter((g) => g.recurring).length

  const modalCls = fullscreen
    ? "fixed inset-0 z-[60] flex flex-col bg-background"
    : "fixed inset-0 z-[60] flex items-center justify-center bg-black/50"

  const panelCls = fullscreen
    ? "flex flex-col h-full"
    : "flex flex-col bg-card border border-primary/10 rounded-xl shadow-2xl w-[900px] max-w-[95vw] max-h-[90vh]"

  return (
    <div className={modalCls} onClick={fullscreen ? undefined : (e) => { if (e.target === e.currentTarget) onClose() }}>
      <div className={panelCls}>
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-primary/10 shrink-0">
          <h2 className="text-sm font-semibold">Posty na grupach — Harmonogram</h2>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setFullscreen(!fullscreen)}
              className="p-1.5 rounded-md hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
            >
              {fullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-secondary/50 text-muted-foreground hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
          {/* Publish as fanpage */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={!!publishAsFanpage}
                onChange={(e) => setPublishAsFanpage(e.target.checked ? publishAsFanpage || "https://www.facebook.com/" : "")}
                className="rounded"
              />
              Publikuj jako fanpage
            </label>
            {!!publishAsFanpage && (
              <input
                value={publishAsFanpage}
                onChange={(e) => setPublishAsFanpage(e.target.value)}
                className="w-full h-8 rounded-md border border-primary/10 bg-secondary/50 px-3 text-xs font-mono
                           focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary
                           placeholder:text-muted-foreground/50"
                placeholder="https://www.facebook.com/nazwa-fanpage"
              />
            )}
          </div>

          {/* Default Media */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs flex items-center gap-1.5">
                <ImagePlus className="h-3.5 w-3.5 text-primary" />
                Media (zdjęcia / filmy)
              </Label>
              <label className={`text-[10px] cursor-pointer transition-colors ${mediaUploading ? "text-muted-foreground" : "text-primary hover:text-primary/80"}`}>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime"
                  multiple
                  onChange={handleMediaUpload}
                  disabled={mediaUploading}
                  className="hidden"
                />
                {mediaUploading ? "Przesyłanie..." : "+ Dodaj pliki"}
              </label>
            </div>
            {defaultMediaFiles.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {defaultMediaFiles.map((filename) => {
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
                        onClick={() => removeDefaultMedia(filename)}
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
            {defaultMediaFiles.length > 0 && (
              <div className="flex items-center justify-between">
                <p className="text-[10px] text-muted-foreground">
                  {defaultMediaFiles.length} {defaultMediaFiles.length === 1 ? "plik" : defaultMediaFiles.length < 5 ? "pliki" : "plików"}
                  {" · "}Media i tło wzajemnie się wykluczają
                </p>
                {groups.length > 0 && (
                  <button
                    onClick={applyMediaToAll}
                    className="text-[10px] text-primary hover:text-primary/80 transition-colors"
                  >
                    Zastosuj do wszystkich
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Default Content */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Domyślna treść posta</Label>
              {groups.length > 0 && (
                <button
                  onClick={applyDefaultToEmpty}
                  className="text-[10px] text-primary hover:text-primary/80 transition-colors"
                >
                  Zastosuj do pustych
                </button>
              )}
            </div>
            <textarea
              value={defaultContent}
              onChange={(e) => setDefaultContent(e.target.value)}
              className="w-full min-h-[70px] rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-xs resize-y
                         focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary
                         placeholder:text-muted-foreground/50"
              placeholder="Domyślna treść — każda grupa może mieć własną treść poniżej..."
            />
          </div>

          {/* URL paste + schedule generator */}
          <div className="border border-primary/10 rounded-lg bg-card/50 p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <ClipboardPaste className="h-4 w-4 text-primary" />
              Wklej listę grup
            </div>

            <textarea
              className="w-full min-h-[100px] rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-xs font-mono
                         focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-y
                         placeholder:text-muted-foreground/50"
              placeholder={"Wklej URL-e grup Facebook (po jednym w linii)...\nhttps://www.facebook.com/groups/nazwa-grupy/\nhttps://www.facebook.com/groups/inna-grupa/"}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />

            {parsedCount > 0 && (
              <p className="text-[11px] text-muted-foreground">
                Rozpoznano <span className="text-primary font-semibold">{parsedCount}</span>{" "}
                {parsedCount === 1 ? "grupę" : parsedCount < 5 ? "grupy" : "grup"}
              </p>
            )}

            <div className="flex items-end gap-4 flex-wrap">
              <div className="space-y-1">
                <label className="text-[10px] text-muted-foreground uppercase tracking-wider">Okno godzin</label>
                <div className="flex items-center gap-1">
                  <input
                    type="time"
                    className="h-8 rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs"
                    value={activeHoursStart}
                    onChange={(e) => setActiveHoursStart(e.target.value)}
                  />
                  <span className="text-xs text-muted-foreground">-</span>
                  <input
                    type="time"
                    className="h-8 rounded-md border border-primary/10 bg-secondary/50 px-2 text-xs"
                    value={activeHoursEnd}
                    onChange={(e) => setActiveHoursEnd(e.target.value)}
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
                onClick={handleGenerate}
                disabled={parsedCount === 0}
              >
                <Wand2 className="mr-1.5 h-3.5 w-3.5" />
                Generuj ({parsedCount})
              </Button>
            </div>
          </div>

          {/* Groups table */}
          {groups.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs">
                  Grupy ({groups.length})
                  {recurringCount > 0 && (
                    <span className="ml-2 text-primary">· {recurringCount} cyklicznych</span>
                  )}
                </Label>
                <button
                  onClick={() => setGroups([])}
                  className="text-[10px] text-rose-400 hover:text-rose-300 transition-colors"
                >
                  Wyczyść wszystko
                </button>
              </div>

              <div className="border border-primary/10 rounded-lg overflow-hidden">
                {/* Table header */}
                <div className="grid grid-cols-[minmax(200px,1fr)_minmax(160px,1fr)_100px_70px_32px_32px_36px_36px] gap-px bg-primary/5 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                  <div className="px-3 py-1.5 bg-card">URL grupy</div>
                  <div className="px-2 py-1.5 bg-card">Treść posta</div>
                  <div className="px-2 py-1.5 bg-card">Data</div>
                  <div className="px-2 py-1.5 bg-card">Godz.</div>
                  <div className="px-1 py-1.5 bg-card text-center" title="Kolor tła">🎨</div>
                  <div className="px-1 py-1.5 bg-card text-center" title="Media (zdjęcia/filmy)">
                    <ImagePlus className="h-3 w-3 mx-auto" />
                  </div>
                  <div className="px-1 py-1.5 bg-card text-center" title="Publikacja cykliczna">
                    <RefreshCw className="h-3 w-3 mx-auto" />
                  </div>
                  <div className="px-2 py-1.5 bg-card"></div>
                </div>

                {/* Rows */}
                <div className="max-h-[400px] overflow-y-auto">
                  {groups.map((g, i) => (
                    <Fragment key={i}>
                      {/* Main row */}
                      <div className="grid grid-cols-[minmax(200px,1fr)_minmax(160px,1fr)_100px_70px_32px_32px_36px_36px] gap-px bg-primary/5 text-xs border-t border-primary/5 first:border-t-0">
                        <div className="px-2 py-1.5 bg-card">
                          <input
                            value={g.url}
                            onChange={(e) => updateGroup(i, { url: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none truncate font-mono"
                            placeholder="https://facebook.com/groups/..."
                          />
                        </div>
                        <div className="px-2 py-1.5 bg-card">
                          <input
                            value={g.content}
                            onChange={(e) => updateGroup(i, { content: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none truncate"
                            placeholder="Treść (lub domyślna)"
                            title={g.content || "Użyje domyślnej treści"}
                          />
                        </div>
                        <div className="px-1 py-1.5 bg-card">
                          <input
                            type="date"
                            value={g.planned_date}
                            onChange={(e) => updateGroup(i, { planned_date: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none"
                          />
                        </div>
                        <div className="px-1 py-1.5 bg-card">
                          <input
                            type="time"
                            value={g.planned_time}
                            onChange={(e) => updateGroup(i, { planned_time: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none"
                          />
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            data-bg-row-btn
                            onClick={(e) => openBgPicker(i, e.currentTarget)}
                            className={`h-5 w-5 rounded border cursor-pointer transition-all hover:scale-110 ${
                              g.background_style ? "border-primary/30" : "border-primary/10 hover:border-primary/30"
                            } ${g.media_files.length > 0 ? "opacity-30 pointer-events-none" : ""}`}
                            style={{
                              backgroundColor: g.background_style
                                ? getBgColor(g.background_style) || "#333"
                                : "transparent",
                            }}
                            title={g.media_files.length > 0 ? "Wyłączone — grupa ma media" : g.background_style || "Brak tła"}
                          />
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            data-media-row-btn
                            onClick={(e) => openMediaPicker(i, e.currentTarget)}
                            className={`relative h-5 w-5 rounded border cursor-pointer transition-all hover:scale-110 ${
                              g.media_files.length > 0
                                ? "border-primary/30 bg-primary/10"
                                : "border-primary/10 hover:border-primary/30"
                            } ${g.background_style ? "opacity-30 pointer-events-none" : ""}`}
                            title={g.background_style ? "Wyłączone — grupa ma tło" : g.media_files.length > 0 ? `${g.media_files.length} media` : "Brak mediów"}
                          >
                            <ImagePlus className="h-3 w-3 mx-auto text-muted-foreground" />
                            {g.media_files.length > 0 && (
                              <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-primary text-[7px] text-primary-foreground flex items-center justify-center font-bold">
                                {g.media_files.length}
                              </span>
                            )}
                          </button>
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            onClick={() => updateGroup(i, { recurring: !g.recurring, recurring_days: !g.recurring ? [0,1,2,3,4] : g.recurring_days })}
                            className={`p-1 rounded transition-colors ${
                              g.recurring
                                ? "text-primary bg-primary/10"
                                : "text-muted-foreground/40 hover:text-muted-foreground"
                            }`}
                            title={g.recurring ? "Cykliczna: włączona" : "Cykliczna: wyłączona"}
                          >
                            <RefreshCw className="h-3 w-3" />
                          </button>
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            onClick={() => removeGroup(i)}
                            className="text-muted-foreground hover:text-rose-400 transition-colors"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </div>

                      {/* Recurring schedule sub-row */}
                      {g.recurring && (
                        <div className="bg-card border-t border-primary/5 px-3 py-2 flex items-center gap-3 flex-wrap">
                          <span className="text-[10px] text-muted-foreground uppercase tracking-wider shrink-0">Powtarzaj:</span>
                          <div className="flex items-center gap-1">
                            {DAY_LABELS.map((label, dayIdx) => (
                              <button
                                key={dayIdx}
                                onClick={() => toggleRecurringDay(i, dayIdx)}
                                className={`h-6 w-7 rounded text-[10px] font-medium transition-colors ${
                                  g.recurring_days.includes(dayIdx)
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
                            value={g.recurring_time}
                            onChange={(e) => updateGroup(i, { recurring_time: e.target.value })}
                            className="h-6 rounded-md border border-primary/10 bg-secondary/50 px-1.5 text-[11px] w-[70px]"
                          />
                          <div className="flex items-center gap-1.5 shrink-0" title="Losowość czasu publikacji">
                            <span className="text-[10px] text-muted-foreground">🎲</span>
                            <input
                              type="range"
                              min={0}
                              max={120}
                              step={5}
                              value={g.recurring_jitter}
                              onChange={(e) => updateGroup(i, { recurring_jitter: Number(e.target.value) })}
                              className="w-16 h-1 rounded-full appearance-none cursor-pointer bg-secondary accent-primary"
                            />
                            <span className="text-[10px] text-primary font-semibold w-12">
                              {formatJitter(g.recurring_jitter)}
                            </span>
                          </div>
                          <span className="text-[10px] text-muted-foreground ml-auto">
                            {formatRecurringDays(g.recurring_days)}
                          </span>
                        </div>
                      )}
                    </Fragment>
                  ))}
                </div>
              </div>

              {/* Add single group */}
              <button
                onClick={() => setGroups((prev) => [...prev, makeEmptyGroup()])}
                className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground transition-colors"
              >
                <Plus className="h-3 w-3" />
                Dodaj wiersz
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-primary/10 shrink-0">
          <span className="text-xs text-muted-foreground">
            {groups.length} {groups.length === 1 ? "grupa" : groups.length < 5 ? "grupy" : "grup"}
            {recurringCount > 0 ? ` · ${recurringCount} cyklicznych` : ""}
            {publishAsFanpage ? " · jako fanpage" : ""}
            {defaultContent ? ` · ${defaultContent.length} zn.` : ""}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onClose}>
              Anuluj
            </Button>
            <Button size="sm" onClick={handleSave} className="bg-primary text-primary-foreground">
              Zapisz
            </Button>
          </div>
        </div>
      </div>

      {/* Background picker popover (per-row only) */}
      {showBgPicker && (
        <div
          ref={bgPopoverRef}
          className="fixed z-[70] bg-card border border-primary/10 rounded-lg shadow-xl p-3"
          style={{ top: bgPos.top, left: bgPos.left, width: 280 }}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
              Tło grupy
            </span>
            <button
              onClick={() => {
                updateGroup(bgPickerTarget, { background_style: "" })
                setShowBgPicker(false)
              }}
              className="text-[10px] text-muted-foreground hover:text-foreground"
            >
              Brak
            </button>
          </div>
          <div className="grid grid-cols-7 gap-1.5">
            {FB_BACKGROUNDS.map((bg) => {
              const activeBg = groups[bgPickerTarget]?.background_style || ""
              return (
                <button
                  key={bg.id}
                  onClick={() => {
                    updateGroup(bgPickerTarget, { background_style: bg.id, media_files: [] })
                    setShowBgPicker(false)
                  }}
                  className={`h-7 w-7 rounded-md border transition-all cursor-pointer hover:scale-110 ${
                    activeBg === bg.id ? "border-primary ring-2 ring-primary/30 scale-110" : "border-primary/10"
                  }`}
                  style={{ backgroundColor: bg.color }}
                  title={bg.label}
                />
              )
            })}
          </div>
        </div>
      )}

      {/* Media picker popover (per-row only) */}
      {showMediaPicker && (() => {
        const targetGroup = groups[mediaPickerTarget]
        if (!targetGroup) return null
        const groupMedia = targetGroup.media_files || []
        // Library: all uploaded files NOT already assigned to this group
        const libraryFiles = allUploadedFiles.filter((f) => !groupMedia.includes(f))

        return (
          <div
            ref={mediaPopoverRef}
            className="fixed z-[70] bg-card border border-primary/10 rounded-lg shadow-xl p-3"
            style={{ top: mediaPos.top, left: mediaPos.left, width: 300 }}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                Media grupy
              </span>
              <button
                onClick={() => {
                  updateGroup(mediaPickerTarget, { media_files: [] })
                  setShowMediaPicker(false)
                }}
                className="text-[10px] text-muted-foreground hover:text-foreground"
              >
                Brak
              </button>
            </div>

            {/* Current group media */}
            {groupMedia.length > 0 && (
              <div className="mb-2">
                <div className="flex flex-wrap gap-1.5">
                  {groupMedia.map((filename) => {
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
                          onClick={() => {
                            updateGroup(mediaPickerTarget, {
                              media_files: groupMedia.filter((f) => f !== filename),
                            })
                          }}
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

            {/* Library (all uploaded files not yet in this group) */}
            {libraryFiles.length > 0 && (
              <div className="mb-2">
                <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Z biblioteki</span>
                <div className="flex flex-wrap gap-1.5 mt-1">
                  {libraryFiles.map((filename) => {
                    const isVideo = filename.endsWith(".mp4") || filename.endsWith(".mov")
                    return (
                      <button
                        key={filename}
                        onClick={() => {
                          updateGroup(mediaPickerTarget, {
                            media_files: [...groupMedia, filename],
                            background_style: "",
                          })
                        }}
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

            {/* Upload new file */}
            <label className={`flex items-center gap-1.5 text-[10px] cursor-pointer transition-colors ${mediaUploading ? "text-muted-foreground" : "text-primary hover:text-primary/80"}`}>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/gif,video/mp4,video/quicktime"
                multiple
                onChange={(e) => handlePerGroupMediaUpload(e, mediaPickerTarget)}
                disabled={mediaUploading}
                className="hidden"
              />
              <Plus className="h-3 w-3" />
              {mediaUploading ? "Przesyłanie..." : "Upload nowy plik"}
            </label>
          </div>
        )
      })()}
    </div>
  )
}
