import { motion } from "motion/react";

// The signature element: a forge temperature gauge. A score (0–10) reads as heat
// — cold steel at the low end, white-hot at the top — directly tying the forge
// metaphor to the product's actual scoring output.
export function ScoreGauge({ label, score }: { label: string; score: number }) {
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));
  const tier = score >= 8 ? "Forged" : score >= 6 ? "Tempered" : score >= 4 ? "Heating" : "Cold";

  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="eyebrow">{label}</span>
        <span className="font-[var(--font-mono)] text-sm text-ash-2">
          <span className="text-chalk">{score.toFixed(1)}</span>
          <span className="text-ash">/10</span>
        </span>
      </div>
      <div
        className="relative h-3 overflow-hidden rounded-full border border-steel bg-[#0c0d10]"
        role="meter"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={10}
        aria-label={`${label}: ${score} out of 10`}
      >
        <motion.div
          className="heat-gradient h-full rounded-full"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
        <motion.div
          className="absolute top-1/2 h-4 w-[2px] -translate-y-1/2 bg-whitehot shadow-[0_0_8px_2px_rgba(255,244,230,0.7)]"
          initial={{ left: 0, opacity: 0 }}
          animate={{ left: `calc(${pct}% - 1px)`, opacity: 1 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />
      </div>
      <div className="mt-1 font-[var(--font-mono)] text-[0.65rem] uppercase tracking-wider text-ash">
        {tier}
      </div>
    </div>
  );
}
