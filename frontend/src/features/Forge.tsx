import { useState } from "react";
import { useStore } from "../store";
import { ProgressLog } from "../components/ProgressLog";
import { ScoreGauge } from "../components/ScoreGauge";
import { DownloadBar, PdfPreview } from "../components/DownloadBar";
import { Button, Card, ErrorNote, Label, SectionTitle, Select, Spinner, Textarea } from "../components/ui";

export function Forge() {
  const s = useStore();
  const [edit, setEdit] = useState("");
  const generating = s.busy === "generate";
  const editing = s.busy === "editResume";
  const hasResult = Boolean(s.resume.pdfId || s.resume.docxId);

  if (generating || (!hasResult && s.generateLog.length > 0)) {
    return (
      <Card>
        <SectionTitle eyebrow="Step 03 · Forge" title="At the anvil…" hint="Matching projects, building the A4 layout with auto-fit, then scoring against the job." />
        <div className="space-y-3">
          <ProgressLog lines={s.generateLog} live={generating} />
          {generating && <Button variant="ghost" onClick={() => s.cancel()}>Cancel</Button>}
          {s.error && <ErrorNote message={s.error} />}
        </div>
      </Card>
    );
  }

  if (!hasResult) {
    return (
      <Card>
        <SectionTitle eyebrow="Step 03 · Forge" title="Nothing forged yet" hint="Head back to Heat, choose your projects, and forge the resume." />
        {s.error && <ErrorNote message={s.error} />}
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle eyebrow="Step 03 · Forge" title={s.jobLabel || "Your forged resume"} hint="Scored against the job. Higher heat means a stronger match." />
        {s.scores && (
          <div className="grid gap-5 sm:grid-cols-2">
            <ScoreGauge label="ATS readiness" score={Number(s.scores.ats_score ?? 0)} />
            <ScoreGauge label="JD match" score={Number(s.scores.match_score ?? 0)} />
          </div>
        )}
        <div className="mt-4">
          <DownloadBar pdfId={s.resume.pdfId} docxId={s.resume.docxId} pdfName={s.resume.pdfName} docxName={s.resume.docxName} />
        </div>
      </Card>

      <Card>
        <SectionTitle title="Refine" hint="Tell the editor what to change, or just adjust the format and rebuild." />
        <div className="space-y-3">
          <Textarea rows={3} placeholder='e.g. "Shorten the summary and lead the first project with the latency metric."' value={edit} onChange={(e) => setEdit(e.target.value)} />
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-32">
              <Label htmlFor="page">Length</Label>
              <Select id="page" value={s.pageOption} onChange={(e) => s.set("pageOption", e.target.value as "1-page" | "2-page")}>
                <option value="1-page">1 page</option>
                <option value="2-page">2 pages</option>
              </Select>
            </div>
            <div className="w-40">
              <Label htmlFor="font">Font</Label>
              <Select id="font" value={s.fontFamily} onChange={(e) => s.set("fontFamily", e.target.value)}>
                <option>Calibri</option>
                <option>Georgia</option>
                <option>Arial</option>
                <option>Garamond</option>
              </Select>
            </div>
            <div className="w-36">
              <Label htmlFor="size">Size</Label>
              <Select id="size" value={s.fontSize} onChange={(e) => s.set("fontSize", e.target.value)}>
                <option value="auto">Auto-fit</option>
                <option value="11">11 pt</option>
                <option value="10.5">10.5 pt</option>
                <option value="10">10 pt</option>
                <option value="9.5">9.5 pt</option>
                <option value="9">9 pt</option>
                <option value="8.5">8.5 pt</option>
                <option value="8">8 pt</option>
              </Select>
            </div>
            <Button onClick={() => s.editResume(edit).then(() => setEdit(""))} disabled={editing}>
              {editing ? <Spinner /> : "🔧"} {editing ? "Reworking…" : "Apply & rebuild"}
            </Button>
            <Button variant="ghost" onClick={() => s.goTo("letter")}>
              Next: cover letter →
            </Button>
          </div>
          {s.error && <ErrorNote message={s.error} />}
        </div>
      </Card>

      <Card>
        <SectionTitle title="Preview" />
        <PdfPreview pdfId={s.resume.pdfId} title="Resume preview" />
      </Card>
    </div>
  );
}
