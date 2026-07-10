"use client"

import { useEffect, useState } from "react"
import { api, type CIRunListItem } from "@/lib/api"
import { formatDistanceToNow } from "date-fns"
import Link from "next/link"
import { GitBranch, GitCommit, Clock, AlertCircle, CheckCircle2, Loader2 } from "lucide-react"

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
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center text-red-500">
        Error: {error}
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        No CI runs found. Ingest a failure to get started.
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <h1 className="text-2xl font-bold text-gray-900">BuildLens AI</h1>
          <p className="text-sm text-gray-500">CI Failure Triage Platform</p>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="space-y-4">
          {runs.map((run) => (
            <Link key={run.id} href={`/runs/${run.id}`}>
              <div className="bg-white rounded-lg border hover:border-gray-300 hover:shadow-md transition-all cursor-pointer p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <h2 className="font-semibold text-lg">{run.repo_name}</h2>
                    <div className="flex items-center gap-1 text-sm text-gray-500">
                      <GitBranch className="w-4 h-4" />
                      {run.branch}
                    </div>
                  </div>
                  {run.status === "failed" ? (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-red-50 text-red-700 text-sm font-medium">
                      <AlertCircle className="w-4 h-4" />
                      Failed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-green-50 text-green-700 text-sm font-medium">
                      <CheckCircle2 className="w-4 h-4" />
                      Passed
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm text-gray-600 mb-3">
                  <div className="flex items-center gap-2">
                    <GitCommit className="w-4 h-4" />
                    <code className="text-xs">{run.commit_sha.slice(0, 8)}</code>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    {formatDistanceToNow(new Date(run.timestamp), { addSuffix: true })}
                  </div>
                </div>

                {run.triage_summary && (
                  <div className="text-sm text-gray-700">
                    <span className="font-medium text-gray-900">AI Analysis:</span> {run.triage_summary}
                  </div>
                )}

                {run.triage_category && (
                  <div className="mt-3">
                    <span className="inline-block px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded">
                      {formatCategory(run.triage_category)}
                    </span>
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
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
