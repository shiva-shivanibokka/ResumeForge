import { useEffect } from "react";
import { motion } from "motion/react";
import { useStore } from "./store";
import { Stepper } from "./features/Stepper";
import { Materials } from "./features/Materials";
import { Projects } from "./features/Projects";
import { Forge } from "./features/Forge";
import { CoverLetter } from "./features/CoverLetter";

function Logo() {
  return (
    <svg width="44" height="44" viewBox="0 0 44 44" aria-hidden="true" className="shrink-0">
      <defs>
        <linearGradient id="rf-logo" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7c5cfc" />
          <stop offset="0.55" stopColor="#ec4899" />
          <stop offset="1" stopColor="#ff5a1f" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="42" height="42" rx="13" fill="url(#rf-logo)" />
      {/* a forge hammer */}
      <g transform="rotate(-38 22 22)" fill="#fff">
        <rect x="20.2" y="12.5" width="3.6" height="20" rx="1.8" />
        <rect x="12.5" y="10.5" width="19" height="6.6" rx="2.6" />
      </g>
    </svg>
  );
}

function Header() {
  return (
    <header className="site-header">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3.5 sm:px-6">
        <div className="flex items-center gap-3.5">
          <Logo />
          <div>
            <div className="font-[var(--font-display)] text-2xl font-black leading-none tracking-tight">
              Resume<span className="heat-text">Forge</span>
            </div>
            <p className="mt-1 font-[var(--font-display)] text-[0.95rem] font-medium leading-tight text-ash-2">
              Forge a resume the job <span className="heat-text font-bold">can&rsquo;t ignore</span>.
            </p>
          </div>
        </div>
        <a
          href="https://github.com/shiva-shivanibokka/ResumeForge"
          target="_blank"
          rel="noopener noreferrer"
          className="chip-link hidden items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-ash-2 sm:flex"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
            <path d="M12 .5A11.5 11.5 0 0 0 .5 12a11.5 11.5 0 0 0 7.86 10.92c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.54-3.88-1.54-.53-1.34-1.3-1.7-1.3-1.7-1.06-.72.08-.71.08-.71 1.17.08 1.79 1.2 1.79 1.2 1.04 1.79 2.73 1.27 3.4.97.1-.76.41-1.27.74-1.56-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.69 5.4-5.25 5.68.42.37.8 1.1.8 2.22v3.29c0 .31.21.67.8.56A11.5 11.5 0 0 0 23.5 12 11.5 11.5 0 0 0 12 .5Z" />
          </svg>
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
