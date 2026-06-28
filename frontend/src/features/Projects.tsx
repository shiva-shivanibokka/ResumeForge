import { useStore } from "../store";
import { ProgressLog } from "../components/ProgressLog";
import { Button, Card, ErrorNote, SectionTitle, Spinner } from "../components/ui";

export function Projects() {
  const s = useStore();
  const fetching = s.busy === "projects";
  const a = s.analysis;
  const keywords = [...(a?.required_keywords ?? []), ...(a?.preferred_keywords ?? [])];

  return (
    <div className="space-y-5">
      {keywords.length > 0 && (
        <Card>
          <SectionTitle eyebrow="Step 02 · Heat" title="Missing keywords to work in" hint="The job asks for these and your resume is light on them. Pick the ones that are genuinely true for you — they'll be woven into the forged resume." />
          <div className="flex flex-wrap gap-2">
            {keywords.map((k) => {
              const on = s.selectedKeywords.includes(k.keyword);
              return (
                <button
                  key={k.keyword}
                  title={k.explanation}
                  onClick={() => s.toggleKeyword(k.keyword)}
                  className={[
                    "rounded-full border px-3 py-1.5 text-xs transition",
                    on ? "border-ember/60 bg-ember/15 text-amber" : "border-steel bg-graphite-2 text-ash-2 hover:border-steel-2",
                  ].join(" ")}
                >
                  {on ? "✓ " : "+ "}
                  {k.keyword}
                </button>
              );
            })}
          </div>
        </Card>
      )}

      <Card>
        <SectionTitle title="Pull your projects" hint="We crawl your public GitHub, summarize each repo, and rank the most relevant for this job." />
        {s.ranked.length === 0 && (
          <Button onClick={() => s.fetchProjects()} disabled={fetching}>
            {fetching ? <Spinner /> : "⛏"} {fetching ? "Mining repos…" : "Pull from GitHub"}
          </Button>
        )}
        {(fetching || s.projectsLog.length > 0) && (
          <div className="mt-4 space-y-3">
            <ProgressLog lines={s.projectsLog} live={fetching} />
            {fetching && (
              <Button variant="ghost" onClick={() => s.cancel()}>
                Cancel
              </Button>
            )}
          </div>
        )}
      </Card>

      {s.ranked.length > 0 && (
        <Card>
          <SectionTitle title="Choose what to feature" hint={`Selected ${s.selectedProjects.length} — the top 4 are pre-picked. Toggle to taste.`} />
          <div className="space-y-2">
            {s.ranked.map((p) => {
              const on = s.selectedProjects.some((x) => x.name === p.name);
              return (
                <button
                  key={p.name}
                  onClick={() => s.toggleProject(p)}
                  className={[
                    "flex w-full items-start gap-3 rounded-[10px] border p-3.5 text-left transition",
                    on ? "border-ember/50 bg-ember/[0.07]" : "border-steel bg-graphite-2 hover:border-steel-2",
                  ].join(" ")}
                >
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${on ? "border-ember bg-ember text-[#1a0c02]" : "border-steel-2 text-transparent"}`}>
                    ✓
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold text-chalk">{p.name}</span>
                    {p.relevance_reason && <span className="mt-0.5 block text-xs text-ash">{p.relevance_reason}</span>}
                    {p.tech_stack && p.tech_stack.length > 0 && (
                      <span className="mt-1.5 block font-[var(--font-mono)] text-[0.7rem] text-ash">
                        {p.tech_stack.slice(0, 6).join(" · ")}
                      </span>
                    )}
                  </span>
                </button>
              );
            })}
          </div>
        </Card>
      )}

      {s.error && <ErrorNote message={s.error} />}

      <div className="flex justify-end">
        <Button onClick={() => s.generate()} disabled={s.selectedProjects.length === 0 || fetching}>
          🔨 Forge the resume
        </Button>
      </div>
    </div>
  );
}
