import { useState } from "react";
import { useStore } from "../store";
import { DownloadBar, PdfPreview } from "../components/DownloadBar";
import { Button, Card, ErrorNote, Label, SectionTitle, Select, Spinner, Textarea } from "../components/ui";

export function CoverLetter() {
  const s = useStore();
  const [edit, setEdit] = useState("");
  const generating = s.busy === "coverLetter";
  const editing = s.busy === "editCover";
  const hasLetter = Boolean(s.letterText);

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle eyebrow="Step 04 · Temper" title="Cover letter" hint="A tailored letter that reuses the exact projects and metrics from your forged resume." />
        <div className="flex flex-wrap items-end gap-3">
          <div className="w-44">
            <Label htmlFor="tone">Tone</Label>
            <Select id="tone" value={s.tone} onChange={(e) => s.set("tone", e.target.value)}>
              <option>Professional</option>
              <option>Conversational</option>
              <option>Concise</option>
            </Select>
          </div>
          <Button onClick={() => s.generateCover()} disabled={generating || !s.matchedPayload}>
            {generating ? <Spinner /> : hasLetter ? "↻" : "✍"}{" "}
            {generating ? "Writing…" : hasLetter ? "Regenerate" : "Write the letter"}
          </Button>
        </div>
        {s.error && <div className="mt-3"><ErrorNote message={s.error} /></div>}
      </Card>

      {hasLetter && (
        <>
          <Card>
            <SectionTitle title="Draft" hint="Read it through, then refine or download." />
            <div className="whitespace-pre-wrap rounded-[10px] border border-steel bg-[#0b0c0f] p-4 text-sm leading-relaxed text-ash-2">
              {s.letterText}
            </div>
            <div className="mt-4 space-y-3">
              <Textarea rows={2} placeholder='e.g. "Make the opening punchier and name the team."' value={edit} onChange={(e) => setEdit(e.target.value)} />
              <div className="flex flex-wrap gap-3">
                <Button onClick={() => s.editCover(edit).then(() => setEdit(""))} disabled={editing || !edit.trim()}>
                  {editing ? <Spinner /> : "🔧"} {editing ? "Revising…" : "Apply edits"}
                </Button>
                <DownloadBar pdfId={s.cover.pdfId} docxId={s.cover.docxId} pdfName={s.cover.pdfName} docxName={s.cover.docxName} />
              </div>
            </div>
          </Card>

          <Card>
            <SectionTitle title="Preview" />
            <PdfPreview pdfId={s.cover.pdfId} title="Cover letter preview" />
          </Card>
        </>
      )}
    </div>
  );
}
