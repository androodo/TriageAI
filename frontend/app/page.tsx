"use client"

import { useEffect, useState } from "react"
import { api, type CIRunListItem } from "@/lib/api"
import { formatDistanceToNow } from "date-fns"
import Link from "next/link"
import {
  GitBranch,
  GitCommit,
  Clock,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Activity,
} from "lucide-react"

export default function HomePage() {
  const [runs, setRuns] = useState<CIRunListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function loadRuns() {
      try {
        setLoading(true)
        const data = await api.listRuns()
        setRuns(data.items)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    loadRuns()
  }, [])

  if (loading) {
    return (
      <div className="app-shell flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-teal-700/70" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="app-shell flex items-center justify-center px-4">
        <div className="max-w-md rounded-2xl border border-rose-200 bg-white p-6 text-center shadow-soft">
          <p className="text-sm font-medium text-rose-700">Couldn’t load CI runs</p>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-container flex items-center justify-between py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-700 text-white shadow-sm">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-slate-900">TriageAI</h1>
              <p className="text-sm text-slate-500">CI failure diagnosis</p>
            </div>
          </div>
          <div className="hidden text-sm text-slate-500 sm:block">
            {runs.length} recent run{runs.length === 1 ? "" : "s"}
          </div>
        </div>
      </header>

      <main className="app-container py-8">
        {runs.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 px-6 py-16 text-center shadow-soft">
            <p className="text-base font-medium text-slate-800">No CI runs yet</p>
            <p className="mt-2 text-sm text-slate-500">
              Ingest a failure to see triage results here.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {runs.map((run) => (
              <Link key={run.id} href={`/runs/${run.id}`} className="block group">
                <article className="rounded-2xl border border-slate-200/80 bg-white/90 p-5 shadow-soft transition-all duration-200 group-hover:-translate-y-0.5 group-hover:border-teal-200 group-hover:shadow-md">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="truncate text-base font-semibold text-slate-900">
                          {run.repo_name}
                        </h2>
                        <span className="inline-flex items-center gap-1 text-sm text-slate-500">
                          <GitBranch className="h-3.5 w-3.5" />
                          {run.branch}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-4 text-sm text-slate-500">
                        <span className="inline-flex items-center gap-1.5">
                          <GitCommit className="h-3.5 w-3.5" />
                          <code className="font-mono text-xs text-slate-700">
                            {run.commit_sha.slice(0, 8)}
                          </code>
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          {formatDistanceToNow(new Date(run.timestamp), { addSuffix: true })}
                        </span>
                      </div>
                    </div>
                    {run.status === "failed" ? (
                      <span className="status-failed shrink-0">
                        <AlertCircle className="h-3.5 w-3.5" />
                        Failed
                      </span>
                    ) : (
                      <span className="status-passed shrink-0">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        Passed
                      </span>
                    )}
                  </div>

                  {run.triage_summary && (
                    <p className="mt-4 text-sm leading-relaxed text-slate-700">
                      <span className="font-semibold text-slate-900">AI Analysis · </span>
                      {run.triage_summary}
                    </p>
                  )}

                  {run.triage_category && (
                    <div className="mt-3">
                      <span className="category-chip">{formatCategory(run.triage_category)}</span>
                    </div>
                  )}
                </article>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}

function formatCategory(cat: string): string {
  return cat
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}
