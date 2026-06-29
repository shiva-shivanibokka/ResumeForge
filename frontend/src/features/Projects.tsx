import { useStore } from "../store";
import { ProgressLog } from "../components/ProgressLog";
import { Button, Card, ErrorNote, SectionTitle, Spinner } from "../components/ui";

export function Projects() {
  const s = useStore();
  const fetching = s.busy === "projects";
  const a = s.analysis;
  const keywords = [...(a?.required_keywords ?? []), ...(a?.preferred_keywords ?? [])];
  const matchedSkills =
    ((a?.gap as Record<string, unknown> | undefined)?.already_have as string[] | undefined) ?? [];

  return (
    <div className="space-y-5">
      {matchedSkills.length > 0 && (
        <Card>
          <SectionTitle eyebrow="Step 02 · Heat" title="Skills already matching the JD" hint="The job asks for these and your resume already shows them — they'll be kept." />
          <div className="flex flex-wrap gap-2">
            {matchedSkills.map((skill) => (
              <span
                key={skill}
                className="inline-flex items-center gap-1 rounded-full border border-teal/40 bg-teal/10 px-3 py-1.5 text-xs font-medium text-teal"
              >
                ✓ {skill}
              </span>
            ))}
          </div>
        </Card>
      )}

      {keywords.length > 0 && (
        <Card>
          <SectionTitle title="Missing keywords to work in" hint="The job asks for these and your resume is light on them. Pick the ones that are genuinely true for you — they'll be added to your skills and woven into the resume." />
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
                    on ? "border-violet/60 bg-violet/10 font-medium text-violet" : "border-steel-2 bg-graphite-2 text-ash-2 hover:border-violet/50",
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

        {s.cacheStatus?.cached && (
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-[10px] border border-teal/40 bg-teal/10 px-3.5 py-2.5 text-xs text-ash-2">
            <span className="font-medium text-teal">✓ {s.cacheStatus.count} projects embedded</span>
            <span>·</span>
            <span>cached{s.cacheStatus.embedded_at ? ` ${new Date(s.cacheStatus.embedded_at).toLocaleDateString()}` : ""} — ranking is instant.</span>
            <span className="text-ash">Pushed new repos?</span>
            <button
              onClick={() => s.fetchProjects(true)}
              disabled={fetching}
              className="font-medium text-violet underline-offset-2 hover:underline disabled:opacity-50"
            >
              Re-embed
            </button>
          </div>
        )}

        {s.ranked.length === 0 && (
          <Button onClick={() => s.fetchProjects(false)} disabled={fetching}>
            {fetching ? <Spinner /> : "⛏"}{" "}
            {fetching ? "Working…" : s.cacheStatus?.cached ? "Rank my projects" : "Pull from GitHub"}
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
                    on ? "border-violet/50 bg-violet/[0.06]" : "border-steel-2 bg-graphite-2 hover:border-violet/40",
                  ].join(" ")}
                >
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs ${on ? "border-violet bg-violet text-white" : "border-steel-2 text-transparent"}`}>
                    ✓
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-chalk">{p.name}</span>
                      {typeof p.match_score === "number" && (
                        <span className="shrink-0 rounded-full border border-violet/40 bg-violet/10 px-2 py-0.5 font-[var(--font-mono)] text-[0.65rem] font-medium text-violet">
                          {p.match_score}% match
                        </span>
                      )}
                    </span>
                    {p.one_line && <span className="mt-0.5 block text-xs text-ash">{p.one_line}</span>}
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
