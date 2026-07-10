"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { api, type CIRun, type TriageResult, type SimilarFailure, type IssueDraft } from "@/lib/api"
import { formatDistanceToNow } from "date-fns"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import {
  GitBranch,
  GitCommit,
  Clock,
  AlertTriangle,
  CheckCircle,
  ArrowLeft,
  Loader2,
  Download,
  Copy,
} from "lucide-react"

export default function RunDetailPage() {
  const params = useParams()
  const router = useRouter()
  const [run, setRun] = useState<CIRun | null>(null)
  const [triageResult, setTriageResult] = useState<TriageResult | null>(null)
  const [similarFailures, setSimilarFailures] = useState<SimilarFailure[]>([])
  const [issueDraft, setIssueDraft] = useState<IssueDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

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
      const data = await api.triageRun(params.id as string, true)
      setTriageResult(data)

      // Then load similar failures
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

  if (!run) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        CI run not found
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.back()}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-lg font-semibold">{run.repo_name}</h1>
              <p className="text-sm text-gray-500">{run.pipeline_id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {run.status === "failed" ? (
              <Button
                variant="destructive"
                onClick={handleTriage}
                disabled={actionLoading === "triage"}
              >
                {actionLoading === "triage" ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <AlertTriangle className="w-4 h-4 mr-2" />
                )}
                {run.triage_result ? "Re-Run Triage" : "Run Triage"}
              </Button>
            ) : (
              <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-green-50 text-green-700 text-sm font-medium">
                <CheckCircle className="w-4 h-4" />
                Passed
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Run Metadata */}
        <Card>
          <CardHeader>
            <CardTitle>CI Run Details</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="font-medium text-gray-500">Repository</dt>
                <dd className="text-gray-900">{run.repo_name}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Branch</dt>
                <dd className="text-gray-900">{run.branch}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Commit</dt>
                <dd className="text-gray-900 font-mono">{run.commit_sha}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Environment</dt>
                <dd className="text-gray-900">{run.environment}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Status</dt>
                <dd className="flex items-center gap-1">
                  {run.status === "failed" ? (
                    <span className="text-red-600 flex items-center gap-1">
                      <AlertCircle className="w-4 h-4" />
                      Failed
                    </span>
                  ) : (
                    <span className="text-green-600 flex items-center gap-1">
                      <CheckCircle className="w-4 h-4" />
                      Passed
                    </span>
                  )}
                </dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Test Suite</dt>
                <dd className="text-gray-900">{run.test_suite_name}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Timestamp</dt>
                <dd className="text-gray-900">{new Date(run.timestamp).toLocaleString()}</dd>
              </div>
              <div>
                <dt className="font-medium text-gray-500">Pipeline</dt>
                <dd className="text-gray-900">{run.pipeline_id}</dd>
              </div>
            </dl>
          </CardContent>
        </Card>

        {/* Failed Tests */}
        {run.failed_test_names && run.failed_test_names.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Failed Tests</CardTitle>
              <CardDescription>{run.failed_test_names.length} test(s) failed</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {run.failed_test_names.map((test, i) => (
                  <li key={i} className="text-sm text-gray-700 font-mono">
                    • {test}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Failure Log */}
        {run.failure_log && (
          <Card>
            <CardHeader>
              <CardTitle>Failure Log</CardTitle>
              <CardDescription>Cleaned log excerpt</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <pre>{run.failure_log.cleaned_log_text.slice(0, 2000)}</pre>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Triage Result */}
        {run.triage_result && (
          <Card>
            <CardHeader>
              <CardTitle>AI Triage Result</CardTitle>
              <CardDescription>
                Confidence: {(run.triage_result.confidence_score * 100).toFixed(0)}%
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-medium mb-1">Category</h4>
                <p className="text-gray-700">{formatCategory(run.triage_result.failure_category)}</p>
              </div>
              <div>
                <h4 className="font-medium mb-1">Summary</h4>
                <p className="text-gray-700">{run.triage_result.summary}</p>
              </div>
              <div>
                <h4 className="font-medium mb-1">Root Cause</h4>
                <p className="text-gray-700">{run.triage_result.root_cause}</p>
              </div>
              <div>
                <h4 className="font-medium mb-1">Suggested Steps</h4>
                <ol className="list-decimal list-inside space-y-1 text-gray-700">
                  {run.triage_result.suggested_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </div>
              {run.triage_result.owner_guess && (
                <div>
                  <h4 className="font-medium mb-1">Estimated Owner</h4>
                  <p className="text-gray-700">{run.triage_result.owner_guess}</p>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Action Buttons */}
        {run.status === "failed" && (
          <div className="flex gap-4">
            <Button onClick={handleFindSimilar} disabled={actionLoading === "similar"}>
              {actionLoading === "similar" && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Find Similar Failures
            </Button>
            <Button onClick={handleGenerateIssue} disabled={actionLoading === "issue"} variant="outline">
              {actionLoading === "issue" && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Generate Issue Draft
            </Button>
          </div>
        )}

        {/* Similar Failures */}
        {similarFailures.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Similar Historical Failures</CardTitle>
              <CardDescription>Top {similarFailures.length} similar past failures</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {similarFailures.map((similar) => (
                  <div
                    key={similar.ci_run_id}
                    className="border rounded-lg p-4 space-y-2 hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{similar.repo_name}</span>
                        <span className="text-gray-500">{similar.branch}</span>
                      </div>
                      <span className="text-xs bg-blue-50 text-blue-700 px-2 py-1 rounded">
                        {(similar.similarity_score * 100).toFixed(0)}% similar
                      </span>
                    </div>
                    {similar.summary && (
                      <p className="text-sm text-gray-700">{similar.summary}</p>
                    )}
                    {similar.root_cause && (
                      <p className="text-sm text-gray-600">{similar.root_cause}</p>
                    )}
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <Clock className="w-3 h-3" />
                      {formatDistanceToNow(new Date(similar.timestamp))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Issue Draft */}
        {issueDraft && (
          <Card>
            <CardHeader>
              <CardTitle>Issue Draft</CardTitle>
              <CardDescription>Copy this to GitHub or Jira</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <h4 className="font-medium mb-1">Title</h4>
                <p className="text-gray-900">{issueDraft.title}</p>
              </div>
              <div>
                <h4 className="font-medium mb-1">Body</h4>
                <div className="bg-gray-50 p-4 rounded-md text-sm text-gray-700 whitespace-pre-wrap">
                  {issueDraft.body}
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => copyToClipboard(issueDraft.title + "\n\n" + issueDraft.body)}
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy to Clipboard
              </Button>
            </CardContent>
          </Card>
        )}
      </main>
    </div>
  )
}

async function copyToClipboard(text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch (err) {
    console.error("Failed to copy:", err)
  }
}

function formatCategory(cat: string): string {
  return cat
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ")
}
