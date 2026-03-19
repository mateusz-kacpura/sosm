"use client"

import { useState, useCallback, useEffect, useMemo, Fragment } from "react"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import {
  X, Maximize2, Minimize2, ClipboardPaste, Wand2, Trash2, Plus, RefreshCw,
  ImagePlus, Film, Check,
} from "lucide-react"
import { api, uploadMedia } from "@/lib/api"
import {
  getBgColor,
  SPREAD_STEPS, formatSpread,
} from "@/app/campaigns/spreadsheet"
import {
  type ScheduleEntry,
  DAY_LABELS, pad, formatJitter, formatRecurringDays, generateSchedule,
  usePopover, RecurringSubRow, BgPickerPopover, MediaPickerPopover, DefaultMediaSection,
} from "./schedule-shared"

export type FanpageEntry = ScheduleEntry

export interface PostFanpagesConfig {
  fanpages: FanpageEntry[]
  default_content: string
  background_style: string
  active_hours_start: string
  active_hours_end: string
  spread_minutes: number
  default_media_files: string[]
}

interface FanpageScheduleModalProps {
  config: PostFanpagesConfig
  onSave: (config: PostFanpagesConfig) => void
  onClose: () => void
  accounts?: { id: number; fb_email: string; fanpages: { id: number; fanpage_url: string; fanpage_name: string | null }[] }[]
}

function parseFanpageUrls(text: string): string[] {
  const regex = /(https?:\/\/)?(www\.|m\.)?facebook\.com\/(?!groups\/)[^\s)]+/gi
  const matches = text.match(regex) || []
  return matches.map((url) => {
    let clean = url.replace(/\/+$/, "")
    if (!clean.startsWith("http")) clean = "https://" + clean
    clean = clean.replace("m.facebook.com", "www.facebook.com")
    return clean
  })
}

function makeEmptyFanpage(): FanpageEntry {
  return { url: "", content: "", planned_date: "", planned_time: "", recurring: false, recurring_days: [], recurring_time: "10:00", recurring_jitter: 15, background_style: "", media_files: [] }
}

export function FanpageScheduleModal({ config, onSave, onClose, accounts }: FanpageScheduleModalProps) {
  const [fullscreen, setFullscreen] = useState(false)
  const [fanpages, setFanpages] = useState<FanpageEntry[]>(() =>
    (config.fanpages || []).map((fp) => ({
      url: fp.url || "",
      content: fp.content || "",
      planned_date: fp.planned_date || "",
      planned_time: fp.planned_time || "",
      recurring: fp.recurring ?? false,
      recurring_days: fp.recurring_days || [],
      recurring_time: fp.recurring_time || "10:00",
      recurring_jitter: fp.recurring_jitter ?? 15,
      background_style: fp.background_style || "",
      media_files: fp.media_files || [],
    }))
  )
  const [defaultContent, setDefaultContent] = useState(config.default_content || "")
  const [activeHoursStart, setActiveHoursStart] = useState(config.active_hours_start || "08:00")
  const [activeHoursEnd, setActiveHoursEnd] = useState(config.active_hours_end || "20:00")
  const [spreadIdx, setSpreadIdx] = useState(() => {
    const idx = SPREAD_STEPS.indexOf(config.spread_minutes)
    return idx >= 0 ? idx : 3
  })
  const [defaultMediaFiles, setDefaultMediaFiles] = useState<string[]>(config.default_media_files || [])
  const [mediaUploading, setMediaUploading] = useState(false)
  const [rawText, setRawText] = useState("")
  const bgPicker = usePopover(280, 320, "data-bg-row-btn")
  const mediaPicker = usePopover(300, 280, "data-media-row-btn")

  const spreadMin = SPREAD_STEPS[spreadIdx]
  const parsedCount = parseFanpageUrls(rawText).length

  // All fanpages from all accounts (for checkbox picker)
  const allAccountFanpages = useMemo(() => {
    if (!accounts) return []
    return accounts.flatMap((acc) =>
      (acc.fanpages || []).map((fp) => ({ ...fp, accountEmail: acc.fb_email }))
    )
  }, [accounts])

  // URLs already in the list
  const existingUrls = useMemo(() => new Set(fanpages.map((fp) => fp.url)), [fanpages])

  // All unique uploaded files: default + per-fanpage
  const allUploadedFiles = useMemo(() => {
    const set = new Set([...defaultMediaFiles])
    fanpages.forEach((fp) => fp.media_files.forEach((f) => set.add(f)))
    return Array.from(set)
  }, [defaultMediaFiles, fanpages])

  const handleGenerate = useCallback(() => {
    const urls = parseFanpageUrls(rawText)
    if (urls.length === 0) return
    const newEntries = generateSchedule<FanpageEntry>(urls, defaultContent, activeHoursStart, activeHoursEnd, spreadIdx)
    setFanpages((prev) => [...prev, ...newEntries])
    setRawText("")
  }, [rawText, defaultContent, activeHoursStart, activeHoursEnd, spreadIdx])

  const toggleAccountFanpage = useCallback((fpUrl: string, fpName: string | null) => {
    if (existingUrls.has(fpUrl)) {
      setFanpages((prev) => prev.filter((fp) => fp.url !== fpUrl))
    } else {
      setFanpages((prev) => [...prev, { ...makeEmptyFanpage(), url: fpUrl }])
    }
  }, [existingUrls])

  const applyDefaultToEmpty = useCallback(() => {
    if (!defaultContent) return
    setFanpages((prev) => prev.map((fp) => fp.content ? fp : { ...fp, content: defaultContent }))
  }, [defaultContent])

  const removeFanpage = useCallback((index: number) => {
    setFanpages((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const updateFanpage = useCallback((index: number, updates: Partial<FanpageEntry>) => {
    setFanpages((prev) => prev.map((fp, i) => i === index ? { ...fp, ...updates } : fp))
  }, [])

  const toggleRecurringDay = useCallback((index: number, day: number) => {
    setFanpages((prev) => prev.map((fp, i) => {
      if (i !== index) return fp
      const days = fp.recurring_days.includes(day)
        ? fp.recurring_days.filter((d) => d !== day)
        : [...fp.recurring_days, day].sort()
      return { ...fp, recurring_days: days }
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

  const handlePerFanpageMediaUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>, rowIdx: number) => {
    const fileList = e.target.files
    if (!fileList || fileList.length === 0) return
    setMediaUploading(true)
    try {
      const result = await uploadMedia(Array.from(fileList))
      const newNames = (result.files || []).map((f: any) => f.filename)
      setFanpages((prev) => prev.map((fp, i) =>
        i === rowIdx ? { ...fp, media_files: [...fp.media_files, ...newNames], background_style: "" } : fp
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
    setFanpages((prev) => prev.map((fp) => ({ ...fp, media_files: [...defaultMediaFiles], background_style: fp.media_files.length > 0 || defaultMediaFiles.length > 0 ? "" : fp.background_style })))
  }, [defaultMediaFiles])

  const handleSave = useCallback(() => {
    onSave({
      fanpages,
      default_content: defaultContent,
      background_style: "",
      active_hours_start: activeHoursStart,
      active_hours_end: activeHoursEnd,
      spread_minutes: spreadMin,
      default_media_files: defaultMediaFiles,
    })
    onClose()
  }, [fanpages, defaultContent, activeHoursStart, activeHoursEnd, spreadMin, defaultMediaFiles, onSave, onClose])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !bgPicker.show && !mediaPicker.show) onClose()
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [onClose, bgPicker.show, mediaPicker.show])

  const recurringCount = fanpages.filter((fp) => fp.recurring).length

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
          <h2 className="text-sm font-semibold">Posty na fanpage&apos;ach — Harmonogram</h2>
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
          {/* Pick from account fanpages */}
          {allAccountFanpages.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs">Fanpage&apos;e z konta</Label>
              <div className="grid grid-cols-2 gap-1">
                {allAccountFanpages.map((fp) => {
                  const selected = existingUrls.has(fp.fanpage_url)
                  return (
                    <label
                      key={fp.id}
                      className={`flex items-center gap-2 text-xs cursor-pointer rounded px-2 py-1 transition-colors ${
                        selected ? "bg-primary/10 text-foreground" : "hover:bg-secondary/50 text-muted-foreground"
                      }`}
                    >
                      <div className={`h-3.5 w-3.5 rounded border flex items-center justify-center shrink-0 ${
                        selected ? "bg-primary border-primary" : "border-primary/30"
                      }`}>
                        {selected && <Check className="h-2.5 w-2.5 text-primary-foreground" />}
                      </div>
                      <span className="truncate">
                        {fp.fanpage_name || fp.fanpage_url.replace(/https?:\/\/(www\.)?facebook\.com\//, "")}
                      </span>
                      <input
                        type="checkbox"
                        className="hidden"
                        checked={selected}
                        onChange={() => toggleAccountFanpage(fp.fanpage_url, fp.fanpage_name)}
                      />
                    </label>
                  )
                })}
              </div>
            </div>
          )}

          {/* Default Media */}
          <DefaultMediaSection
            files={defaultMediaFiles}
            onUpload={handleMediaUpload}
            onRemove={removeDefaultMedia}
            uploading={mediaUploading}
            onApplyAll={applyMediaToAll}
            hasEntries={fanpages.length > 0}
          />

          {/* Default Content */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-xs">Domyślna treść posta</Label>
              {fanpages.length > 0 && (
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
              placeholder="Domyślna treść — każdy fanpage może mieć własną treść poniżej..."
            />
          </div>

          {/* URL paste + schedule generator */}
          <div className="border border-primary/10 rounded-lg bg-card/50 p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <ClipboardPaste className="h-4 w-4 text-primary" />
              Wklej listę fanpage&apos;y
            </div>

            <textarea
              className="w-full min-h-[100px] rounded-md border border-primary/10 bg-secondary/50 px-3 py-2 text-xs font-mono
                         focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary resize-y
                         placeholder:text-muted-foreground/50"
              placeholder={"Wklej URL-e fanpage'y Facebook (po jednym w linii)...\nhttps://www.facebook.com/nazwa-fanpage/\nhttps://www.facebook.com/profile.php?id=123456789/"}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />

            {parsedCount > 0 && (
              <p className="text-[11px] text-muted-foreground">
                Rozpoznano <span className="text-primary font-semibold">{parsedCount}</span>{" "}
                {parsedCount === 1 ? "fanpage" : parsedCount < 5 ? "fanpage'e" : "fanpage'y"}
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

          {/* Fanpages table */}
          {fanpages.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs">
                  Fanpage&apos;e ({fanpages.length})
                  {recurringCount > 0 && (
                    <span className="ml-2 text-primary">· {recurringCount} cyklicznych</span>
                  )}
                </Label>
                <button
                  onClick={() => setFanpages([])}
                  className="text-[10px] text-rose-400 hover:text-rose-300 transition-colors"
                >
                  Wyczyść wszystko
                </button>
              </div>

              <div className="border border-primary/10 rounded-lg overflow-hidden">
                {/* Table header — no FP column (each row IS a fanpage) */}
                <div className="grid grid-cols-[minmax(180px,1fr)_minmax(140px,1fr)_100px_70px_32px_32px_36px_36px] gap-px bg-primary/5 text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">
                  <div className="px-3 py-1.5 bg-card">URL fanpage</div>
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
                  {fanpages.map((fp, i) => (
                    <Fragment key={i}>
                      {/* Main row */}
                      <div className="grid grid-cols-[minmax(180px,1fr)_minmax(140px,1fr)_100px_70px_32px_32px_36px_36px] gap-px bg-primary/5 text-xs border-t border-primary/5 first:border-t-0">
                        <div className="px-2 py-1.5 bg-card">
                          <input
                            value={fp.url}
                            onChange={(e) => updateFanpage(i, { url: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none truncate font-mono"
                            placeholder="https://facebook.com/fanpage..."
                          />
                        </div>
                        <div className="px-2 py-1.5 bg-card">
                          <input
                            value={fp.content}
                            onChange={(e) => updateFanpage(i, { content: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none truncate"
                            placeholder="Treść (lub domyślna)"
                            title={fp.content || "Użyje domyślnej treści"}
                          />
                        </div>
                        <div className="px-1 py-1.5 bg-card">
                          <input
                            type="date"
                            value={fp.planned_date}
                            onChange={(e) => updateFanpage(i, { planned_date: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none"
                          />
                        </div>
                        <div className="px-1 py-1.5 bg-card">
                          <input
                            type="time"
                            value={fp.planned_time}
                            onChange={(e) => updateFanpage(i, { planned_time: e.target.value })}
                            className="w-full bg-transparent text-xs focus:outline-none"
                          />
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            data-bg-row-btn
                            onClick={(e) => bgPicker.open(i, e.currentTarget)}
                            className={`h-5 w-5 rounded border cursor-pointer transition-all hover:scale-110 ${
                              fp.background_style ? "border-primary/30" : "border-primary/10 hover:border-primary/30"
                            } ${fp.media_files.length > 0 ? "opacity-30 pointer-events-none" : ""}`}
                            style={{
                              backgroundColor: fp.background_style
                                ? getBgColor(fp.background_style) || "#333"
                                : "transparent",
                            }}
                            title={fp.media_files.length > 0 ? "Wyłączone — fanpage ma media" : fp.background_style || "Brak tła"}
                          />
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            data-media-row-btn
                            onClick={(e) => mediaPicker.open(i, e.currentTarget)}
                            className={`relative h-5 w-5 rounded border cursor-pointer transition-all hover:scale-110 ${
                              fp.media_files.length > 0
                                ? "border-primary/30 bg-primary/10"
                                : "border-primary/10 hover:border-primary/30"
                            } ${fp.background_style ? "opacity-30 pointer-events-none" : ""}`}
                            title={fp.background_style ? "Wyłączone — fanpage ma tło" : fp.media_files.length > 0 ? `${fp.media_files.length} media` : "Brak mediów"}
                          >
                            <ImagePlus className="h-3 w-3 mx-auto text-muted-foreground" />
                            {fp.media_files.length > 0 && (
                              <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-primary text-[7px] text-primary-foreground flex items-center justify-center font-bold">
                                {fp.media_files.length}
                              </span>
                            )}
                          </button>
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            onClick={() => updateFanpage(i, { recurring: !fp.recurring, recurring_days: !fp.recurring ? [0,1,2,3,4] : fp.recurring_days })}
                            className={`p-1 rounded transition-colors ${
                              fp.recurring
                                ? "text-primary bg-primary/10"
                                : "text-muted-foreground/40 hover:text-muted-foreground"
                            }`}
                            title={fp.recurring ? "Cykliczna: włączona" : "Cykliczna: wyłączona"}
                          >
                            <RefreshCw className="h-3 w-3" />
                          </button>
                        </div>
                        <div className="flex items-center justify-center bg-card">
                          <button
                            onClick={() => removeFanpage(i)}
                            className="text-muted-foreground hover:text-rose-400 transition-colors"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </div>
                      </div>

                      {fp.recurring && (
                        <RecurringSubRow entry={fp} index={i} onUpdate={updateFanpage} onToggleDay={toggleRecurringDay} />
                      )}
                    </Fragment>
                  ))}
                </div>
              </div>

              {/* Add single fanpage */}
              <button
                onClick={() => setFanpages((prev) => [...prev, makeEmptyFanpage()])}
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
            {fanpages.length} {fanpages.length === 1 ? "fanpage" : fanpages.length < 5 ? "fanpage'e" : "fanpage'y"}
            {recurringCount > 0 ? ` · ${recurringCount} cyklicznych` : ""}
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

      {bgPicker.show && (
        <BgPickerPopover
          entries={fanpages}
          target={bgPicker.target}
          pos={bgPicker.pos}
          popoverRef={bgPicker.ref}
          onUpdate={updateFanpage}
          onClose={bgPicker.close}
          label="Tło fanpage"
        />
      )}

      {mediaPicker.show && (
        <MediaPickerPopover
          entries={fanpages}
          target={mediaPicker.target}
          pos={mediaPicker.pos}
          popoverRef={mediaPicker.ref}
          allUploadedFiles={allUploadedFiles}
          onUpdate={updateFanpage}
          onUpload={handlePerFanpageMediaUpload}
          uploading={mediaUploading}
          onClose={mediaPicker.close}
          label="Media fanpage"
        />
      )}
    </div>
  )
}
