"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { api, type CIRun, type SimilarFailure, type IssueDraft } from "@/lib/api"
import { formatDistanceToNow } from "date-fns"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  GitBranch,
  Clock,
  AlertTriangle,
  CheckCircle,
  ArrowLeft,
  Loader2,
  Copy,
  Sparkles,
  Search,
  FileText,
} from "lucide-react"

export default function RunDetailPage() {
  const params = useParams()
  const router = useRouter()
  const [run, setRun] = useState<CIRun | null>(null)
  const [similarFailures, setSimilarFailures] = useState<SimilarFailure[]>([])
  const [issueDraft, setIssueDraft] = useState<IssueDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true)
        const data = await api.getRun(params.id as string)
        setRun(data)
      } catch (err) {
        setError((err as Error).message)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [params.id])

  async function handleTriage() {
    try {
      setActionLoading("triage")
      await api.triageRun(params.id as string, true)
      const refreshed = await api.getRun(params.id as string)
      setRun(refreshed)

      setActionLoading("similar")
      const similar = await api.similarFailures(params.id as string)
      setSimilarFailures(similar.items)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleGenerateIssue() {
    try {
      setActionLoading("issue")
      const data = await api.generateIssueDraft(params.id as string, "github", true)
      setIssueDraft(data)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleFindSimilar() {
    try {
      setActionLoading("similar")
      const data = await api.similarFailures(params.id as string)
      setSimilarFailures(data.items)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setActionLoading(null)
    }
  }

  async function handleCopy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1800)
    } catch (err) {
      console.error("Failed to copy:", err)
    }
  }

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
          <p className="text-sm font-medium text-rose-700">Something went wrong</p>
          <p className="mt-2 text-sm text-slate-600">{error}</p>
          <Button className="mt-4" variant="outline" onClick={() => router.push("/")}>
            Back to dashboard
          </Button>
        </div>
      </div>
    )
  }

  if (!run) {
    return (
      <div className="app-shell flex items-center justify-center text-slate-500">
        CI run not found
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-container flex items-center justify-between gap-4 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="rounded-xl p-2 text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900"
              aria-label="Back to dashboard"
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold text-slate-900">{run.repo_name}</h1>
              <p className="truncate text-sm text-slate-500">{run.pipeline_id}</p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            {run.status === "failed" ? (
              <Button
                variant="default"
                onClick={handleTriage}
                disabled={actionLoading === "triage"}
              >
                {actionLoading === "triage" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                {run.triage_result ? "Re-run triage" : "Run triage"}
              </Button>
            ) : (
              <span className="status-passed">
                <CheckCircle className="h-3.5 w-3.5" />
                Passed
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="app-container space-y-5 py-8">
        <Card>
          <CardHeader>
            <CardTitle>CI run details</CardTitle>
            <CardDescription>Source metadata for this pipeline execution</CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <dt className="meta-label">Repository</dt>
                <dd className="meta-value">{run.repo_name}</dd>
              </div>
              <div>
                <dt className="meta-label">Branch</dt>
                <dd className="meta-value inline-flex items-center gap-1.5">
                  <GitBranch className="h-3.5 w-3.5 text-slate-400" />
                  {run.branch}
                </dd>
              </div>
              <div>
                <dt className="meta-label">Commit</dt>
                <dd className="meta-value font-mono text-xs">{run.commit_sha}</dd>
              </div>
              <div>
                <dt className="meta-label">Environment</dt>
                <dd className="meta-value">{run.environment}</dd>
              </div>
              <div>
                <dt className="meta-label">Status</dt>
                <dd className="mt-1">
                  {run.status === "failed" ? (
                    <span className="status-failed">
                      <AlertTriangle className="h-3.5 w-3.5" />
                      Failed
                    </span>
                  ) : (
                    <span className="status-passed">
                      <CheckCircle className="h-3.5 w-3.5" />
                      Passed
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="meta-label">Test suite</dt>
                <dd className="meta-value">{run.test_suite_name}</dd>
              </div>
              <div>
                <dt className="meta-label">Timestamp</dt>
                <dd className="meta-value">{new Date(run.timestamp).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="meta-label">Pipeline</dt>
                <dd className="meta-value">{run.pipeline_id}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {run.failed_test_names && run.failed_test_names.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Failed tests</CardTitle>
              <CardDescription>
                {run.failed_test_names.length} test{run.failed_test_names.length === 1 ? "" : "s"} failed
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {run.failed_test_names.map((test, i) => (
                  <li
                    key={i}
                    className="rounded-xl border border-rose-100 bg-rose-50/60 px-3 py-2 font-mono text-sm text-rose-900"
                  >
                    {test}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {run.failure_log && (
          <Card>
            <CardHeader>
              <CardTitle>Failure log</CardTitle>
              <CardDescription>Cleaned excerpt from the CI output</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="log-block whitespace-pre-wrap break-words">
                {(run.failure_log.cleaned_log_text || "").slice(0, 2000) || "No cleaned log available."}
              </pre>
            </CardContent>
          </Card>
        )}

        {run.triage_result && (
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>TriageAI result</CardTitle>
                  <CardDescription>Automated diagnosis for this failure</CardDescription>
                </div>
                <span className="rounded-md bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                  {(run.triage_result.confidence_score * 100).toFixed(0)}% confidence
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-5">
              <div>
                <h4 className="meta-label mb-2">Category</h4>
                <span className="category-chip">
                  {formatCategory(run.triage_result.failure_category)}
                </span>
              </div>
              <div>
                <h4 className="meta-label mb-1.5">Summary</h4>
                <p className="text-sm leading-relaxed text-slate-700">{run.triage_result.summary}</p>
              </div>
              <div>
                <h4 className="meta-label mb-1.5">Root cause</h4>
                <p className="text-sm leading-relaxed text-slate-700">
                  {run.triage_result.root_cause || "Not available"}
                </p>
              </div>
              <div>
                <h4 className="meta-label mb-2">Suggested steps</h4>
                <ol className="space-y-2">
                  {(run.triage_result.suggested_steps || []).map((step, i) => (
                    <li
                      key={i}
                      className="flex gap-3 rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2.5 text-sm text-slate-700"
                    >
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                        {i + 1}
                      </span>
                      <span className="leading-relaxed pt-0.5">{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
              {run.triage_result.owner_guess && (
                <div>
                  <h4 className="meta-label mb-1.5">Estimated owner</h4>
                  <p className="text-sm text-slate-700">{run.triage_result.owner_guess}</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {run.status === "failed" && (
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleFindSimilar} disabled={actionLoading === "similar"}>
              {actionLoading === "similar" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              Find similar failures
            </Button>
            <Button
              onClick={handleGenerateIssue}
              disabled={actionLoading === "issue"}
              variant="outline"
            >
              {actionLoading === "issue" ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <FileText className="mr-2 h-4 w-4" />
              )}
              Generate issue draft
            </Button>
          </div>
        )}

        {similarFailures.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Similar historical failures</CardTitle>
              <CardDescription>Top {similarFailures.length} closest past matches</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {similarFailures.map((similar) => (
                  <div
                    key={similar.ci_run_id}
                    className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 transition-colors hover:border-teal-200 hover:bg-white"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-900">{similar.repo_name}</span>
                          <span className="text-sm text-slate-500">{similar.branch}</span>
                        </div>
                        <div className="mt-1 flex items-center gap-1.5 text-xs text-slate-500">
                          <Clock className="h-3 w-3" />
                          {formatDistanceToNow(new Date(similar.timestamp), { addSuffix: true })}
                        </div>
                      </div>
                      <span className="category-chip shrink-0">
                        {(similar.similarity_score * 100).toFixed(0)}% similar
                      </span>
                    </div>
                    {similar.summary && (
                      <p className="mt-3 text-sm leading-relaxed text-slate-700">{similar.summary}</p>
                    )}
                    {similar.root_cause && (
                      <p className="mt-1 text-sm text-slate-500">{similar.root_cause}</p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {issueDraft && (
          <Card>
            <CardHeader>
              <CardTitle>Issue draft</CardTitle>
              <CardDescription>Ready to paste into GitHub or Jira</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="meta-label mb-1.5">Title</h4>
                <p className="text-sm font-medium text-slate-900">{issueDraft.title}</p>
              </div>
              <div>
                <h4 className="meta-label mb-1.5">Body</h4>
                <div className="log-block whitespace-pre-wrap">{issueDraft.body}</div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleCopy(`${issueDraft.title}\n\n${issueDraft.body}`)}
              >
                <Copy className="mr-2 h-4 w-4" />
                {copied ? "Copied" : "Copy to clipboard"}
              </Button>
            </CardContent>
          </Card>
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
