import { useStore } from "../store";
import { ProviderPicker } from "../components/ProviderPicker";
import { Button, Card, ErrorNote, Input, Label, SectionTitle, Spinner, Textarea } from "../components/ui";

export function Materials() {
  const s = useStore();
  const busy = s.busy === "analyse";

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle eyebrow="Step 01 · Materials" title="Bring your raw materials" hint="The job you're targeting, your current resume, and where your work lives. These get melted down and reforged for this specific role." />
        <ProviderPicker />
      </Card>

      <Card>
        <SectionTitle title="The job" hint="Paste a posting URL or the full text — whichever you have." />
        <div className="space-y-3">
          <div>
            <Label htmlFor="jdUrl">Job posting URL</Label>
            <Input id="jdUrl" placeholder="https://company.com/careers/swe-new-grad" value={s.jdUrl} onChange={(e) => s.set("jdUrl", e.target.value)} />
          </div>
          <div>
            <Label htmlFor="jdText">…or paste the job description</Label>
            <Textarea id="jdText" rows={5} placeholder="Responsibilities, requirements, tech stack…" value={s.jdText} onChange={(e) => s.set("jdText", e.target.value)} />
          </div>
        </div>
      </Card>

      <Card>
        <SectionTitle title="You" hint="Your current resume plus the links to feature on the forged one." />
        <div className="space-y-3">
          <div>
            <Label htmlFor="resume">Current resume (PDF or DOCX)</Label>
            <input
              id="resume"
              type="file"
              accept=".pdf,.docx"
              onChange={(e) => s.set("resumeFile", e.target.files?.[0] ?? null)}
              className="field w-full cursor-pointer px-3 py-2.5 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-violet/10 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-violet hover:file:bg-violet/20"
            />
            {s.resumeFile && <p className="mt-1.5 font-[var(--font-mono)] text-xs text-ash">{s.resumeFile.name}</p>}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="gh">GitHub profile URL</Label>
              <Input id="gh" placeholder="github.com/yourhandle" value={s.githubUrl} onChange={(e) => s.set("githubUrl", e.target.value)} />
            </div>
            <div>
              <Label htmlFor="li">LinkedIn URL (optional)</Label>
              <Input id="li" placeholder="linkedin.com/in/you" value={s.linkedinUrl} onChange={(e) => s.set("linkedinUrl", e.target.value)} />
            </div>
          </div>
        </div>
      </Card>

      {s.error && <ErrorNote message={s.error} />}

      <div className="flex justify-end">
        <Button onClick={() => s.analyse()} disabled={busy}>
          {busy ? <Spinner /> : "🔥"} {busy ? "Analysing…" : "Light the forge"}
        </Button>
      </div>
    </div>
  );
}
