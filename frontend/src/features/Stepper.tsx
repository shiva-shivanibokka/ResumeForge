import { useStore, type StepId } from "../store";

const STAGES: { id: StepId; label: string; sub: string }[] = [
  { id: "materials", label: "Materials", sub: "JD · resume · GitHub" },
  { id: "projects", label: "Heat", sub: "rank projects" },
  { id: "forge", label: "Forge", sub: "build & score" },
  { id: "letter", label: "Temper", sub: "cover letter" },
];

export function Stepper() {
  const { step, reached, goTo } = useStore();

  return (
    <nav aria-label="Forge stages" className="flex gap-2 lg:flex-col lg:gap-1">
      {STAGES.map((s, i) => {
        const active = step === s.id;
        const open = reached[s.id];
        return (
          <button
            key={s.id}
            onClick={() => goTo(s.id)}
            disabled={!open}
            aria-current={active ? "step" : undefined}
            className={[
              "group flex flex-1 items-center gap-3 rounded-[10px] border px-3 py-2.5 text-left transition lg:flex-none",
              active
                ? "border-ember/50 bg-ember/10"
                : open
                  ? "border-steel bg-graphite hover:border-steel-2"
                  : "border-transparent opacity-40",
            ].join(" ")}
          >
            <span
              className={[
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-[var(--font-mono)] text-xs",
                active ? "heat-gradient text-[#1a0c02]" : "border border-steel text-ash",
              ].join(" ")}
            >
              {String(i + 1).padStart(2, "0")}
            </span>
            <span className="hidden min-w-0 lg:block">
              <span className={`block text-sm font-semibold ${active ? "text-chalk" : "text-ash-2"}`}>
                {s.label}
              </span>
              <span className="block truncate text-[0.7rem] text-ash">{s.sub}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
