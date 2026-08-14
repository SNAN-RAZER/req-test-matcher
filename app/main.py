from __future__ import annotations

import json
import shutil
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import settings
from app.excel_export import report_to_xlsx
from app.graph import run_analysis
from app.jobs import create_job, finish_job, get_job
from app.llm import ping_ollama
from app.models import AnalysisReport

APP_DIR = Path(__file__).resolve().parent
ROOT = APP_DIR.parent
WEB_DIST = ROOT / "web" / "dist"

ALLOWED = {
    ".pdf", ".xlsx", ".xlsm", ".xls", ".pptx", ".ppt", ".docx", ".doc",
    ".txt", ".md", ".csv", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif",
}

app = FastAPI(title="Req-Test Matcher", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    built = (WEB_DIST / "index.html").exists()
    return {**ping_ollama(), "ui": "react" if built else "missing-build"}


def _save_uploads(files: list[UploadFile], dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for f in files:
        if not f.filename:
            continue
        suffix = Path(f.filename).suffix.lower()
        if suffix not in ALLOWED:
            raise HTTPException(400, f"Unsupported file type: {f.filename}")
        target = dest / Path(f.filename).name
        with target.open("wb") as out:
            shutil.copyfileobj(f.file, out)
        paths.append(str(target))
    return paths


@app.post("/api/analyze")
async def analyze(
    req_files: list[UploadFile] = File(default=[]),
    test_files: list[UploadFile] = File(default=[]),
):
    status = ping_ollama()
    if not status.get("ok"):
        raise HTTPException(503, f"Ollama is not reachable at {settings.ollama_host}. {status.get('error')}")
    req_paths = _save_uploads(req_files, settings.upload_dir / uuid.uuid4().hex / "requirements")
    test_paths = _save_uploads(test_files, settings.upload_dir / uuid.uuid4().hex / "tests")
    if not req_paths or not test_paths:
        raise HTTPException(400, "Upload at least one requirements file and one test-case file.")
    job = create_job()
    job.emit(
        {
            "type": "log",
            "agent": "api",
            "action": "queued",
            "detail": f"{len(req_paths)} requirement files, {len(test_paths)} test files",
        }
    )

    def _run() -> None:
        try:
            report = run_analysis(req_paths, test_paths, on_log=job.emit)
            finish_job(job, report=report.model_dump())
        except Exception as exc:
            finish_job(job, error=str(exc))

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job.id}


@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Unknown job")

    async def gen():
        import asyncio

        idx = 0
        while True:
            chunk, idx, done = job.snapshot_from(idx)
            for ev in chunk:
                yield f"data: {json.dumps(ev, default=str)}\n\n"
            if done:
                payload = {"type": "result", "report": job.report, "error": job.error}
                yield f"data: {json.dumps(payload, default=str)}\n\n"
                break
            await asyncio.sleep(0.2)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


class ExportBody(BaseModel):
    report: dict


@app.post("/api/export.xlsx")
def export_xlsx(body: ExportBody):
    try:
        report = AnalysisReport.model_validate(body.report)
    except Exception as exc:
        raise HTTPException(400, f"Invalid report: {exc}") from exc
    data = report_to_xlsx(report)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="req-test-traceability.xlsx"'},
    )


if WEB_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIST / "assets")), name="assets")


@app.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Not found")
    candidate = WEB_DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    index = WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(
        503,
        "React UI is not built. From the project folder run: cd web && npm install && npm run build",
    )


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=False)


if __name__ == "__main__":
    main()
