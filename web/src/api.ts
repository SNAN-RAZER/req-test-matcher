import type { Health, Report } from "./types";
import type { LogLine } from "./Terminal";

export async function fetchHealth(): Promise<Health> {
  const res = await fetch("/api/health");
  return res.json();
}

export async function startJob(reqFiles: File[], testFiles: File[]): Promise<string> {
  const data = new FormData();
  reqFiles.forEach((f) => data.append("req_files", f));
  testFiles.forEach((f) => data.append("test_files", f));
  const res = await fetch("/api/analyze", { method: "POST", body: data });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : res.statusText);
  if (!body.job_id) throw new Error("API did not return a job id");
  return body.job_id as string;
}

export function watchJob(
  jobId: string,
  onLog: (line: LogLine) => void,
  onDone: (report: Report | null, error: string | null) => void
): () => void {
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data);
      if (data.type === "result") {
        es.close();
        onDone(data.report || null, data.error || null);
        return;
      }
      onLog(data);
    } catch {
      onLog({ agent: "ui", action: "parse", detail: ev.data });
    }
  };
  es.onerror = () => {
    /* EventSource retries; ignore until result */
  };
  return () => es.close();
}

export async function downloadExcel(report: Report): Promise<void> {
  const res = await fetch("/api/export.xlsx", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Excel export failed");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "req-test-traceability.xlsx";
  a.click();
  URL.revokeObjectURL(url);
}
