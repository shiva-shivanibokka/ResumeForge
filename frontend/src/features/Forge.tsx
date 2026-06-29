import { useState } from "react";
import { useStore } from "../store";
import { ProgressLog } from "../components/ProgressLog";
import { ScoreGauge } from "../components/ScoreGauge";
import { DownloadBar, PdfPreview } from "../components/DownloadBar";
import { Button, Card, ErrorNote, Label, SectionTitle, Select, Spinner, Textarea } from "../components/ui";

function ScoreBlock({
  label,
  score,
  feedback,
}: {
  label: string;
  score: number;
  feedback?: string[];
}) {
  return (
    <div>
      <ScoreGauge label={label} score={score} />
      {feedback && feedback.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {feedback.map((f, i) => (
            <li key={i} className="flex gap-2 text-xs text-ash-2">
              <span className="mt-0.5 text-amber">→</span>
              <span>{f}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Forge() {
  const s = useStore();
  const [edit, setEdit] = useState("");
  const generating = s.busy === "generate";
  const editing = s.busy === "editResume";
  const reformatting = s.busy === "reformat";
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

  const missing = s.scores?.missing_keywords ?? [];

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle eyebrow="Step 03 · Forge" title={s.jobLabel || "Your forged resume"} hint="Scored against the job, with what to improve under each." />
        {s.scores && (
          <div className="grid gap-6 sm:grid-cols-2">
            <ScoreBlock label="ATS readiness" score={Number(s.scores.ats_score ?? 0)} feedback={s.scores.ats_feedback} />
            <div>
              <ScoreBlock label="JD match" score={Number(s.scores.match_score ?? 0)} feedback={s.scores.match_feedback} />
              {missing.length > 0 && (
                <div className="mt-3">
                  <div className="eyebrow mb-1.5">Still missing from the JD</div>
                  <div className="flex flex-wrap gap-1.5">
                    {missing.slice(0, 12).map((k) => (
                      <span key={k} className="rounded-full border border-amber/40 bg-amber/10 px-2 py-0.5 text-[0.7rem] text-amber">
                        {k}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        <div className="mt-5">
          <DownloadBar pdfId={s.resume.pdfId} docxId={s.resume.docxId} pdfName={s.resume.pdfName} docxName={s.resume.docxName} />
        </div>
      </Card>

      <Card>
        <SectionTitle title="Format" hint="Adjust layout and rebuild instantly — no AI, score unchanged." />
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
          <Button onClick={() => s.reformatResume()} disabled={reformatting}>
            {reformatting ? <Spinner /> : "↻"} {reformatting ? "Rebuilding…" : "Apply format"}
          </Button>
        </div>
      </Card>

      <Card>
        <SectionTitle title="Refine with AI" hint="Tell the editor what to change in the content." />
        <div className="space-y-3">
          <Textarea
            rows={3}
            placeholder='e.g. "Shorten the summary and lead the first project with the latency metric."'
            value={edit}
            onChange={(e) => setEdit(e.target.value)}
          />
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => s.editResume(edit).then(() => setEdit(""))} disabled={editing || !edit.trim()}>
              {editing ? <Spinner /> : "🤖"} {editing ? "Reworking…" : "Apply with AI"}
            </Button>
            <Button variant="ghost" onClick={() => s.goTo("letter")}>
              Next: cover letter →
            </Button>
          </div>
        </div>
      </Card>

      {s.error && <ErrorNote message={s.error} />}

      <Card>
        <SectionTitle title="Preview" />
        <PdfPreview pdfId={s.resume.pdfId} title="Resume preview" />
      </Card>
    </div>
  );
}
