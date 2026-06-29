import { useEffect } from "react";
import { motion } from "motion/react";
import { useStore } from "./store";
import { Stepper } from "./features/Stepper";
import { Materials } from "./features/Materials";
import { Projects } from "./features/Projects";
import { Forge } from "./features/Forge";
import { CoverLetter } from "./features/CoverLetter";

function Header() {
  return (
    <header className="border-b border-steel/70">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
        <div className="flex items-center gap-3">
          <img src="/favicon.svg" alt="" className="h-8 w-8" />
          <div>
            <div className="font-[var(--font-display)] text-lg font-black tracking-tight">
              Resume<span className="heat-text">Forge</span>
            </div>
            <div className="eyebrow">Forge a resume the job can't ignore</div>
          </div>
        </div>
        <a
          href="https://github.com/shiva-shivanibokka/ResumeForge"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden text-xs text-ash transition hover:text-chalk sm:block"
        >
          GitHub
        </a>
      </div>
    </header>
  );
}

const STEP_VIEW = {
  materials: <Materials />,
  projects: <Projects />,
  forge: <Forge />,
  letter: <CoverLetter />,
} as const;

export default function App() {
  const step = useStore((s) => s.step);
  const loadProviders = useStore((s) => s.loadProviders);

  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  return (
    <div className="min-h-dvh">
      <Header />
      <main className="mx-auto grid max-w-6xl gap-6 px-4 py-6 sm:px-6 lg:grid-cols-[240px_1fr] lg:py-10">
        <aside className="lg:sticky lg:top-10 lg:self-start">
          <Stepper />
        </aside>
        <motion.section
          key={step}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          {STEP_VIEW[step]}
        </motion.section>
      </main>
      <footer className="mx-auto max-w-6xl px-4 py-10 text-center text-xs text-ash sm:px-6">
        ResumeForge · bring your own key · Gemini &amp; Groq run free
      </footer>
    </div>
  );
}
