import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";

// The forge log: streamed pipeline progress, styled like a smithy readout.
export function ProgressLog({ lines, live }: { lines: string[]; live: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lines.length]);

  if (lines.length === 0 && !live) return null;

  return (
    <div className="forge-log max-h-56 overflow-y-auto rounded-[10px] border border-steel bg-[#0b0c0f] p-3.5">
      <AnimatePresence initial={false}>
        {lines.map((line, i) => (
          <motion.div
            key={`${i}-${line}`}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            className="flex gap-2 py-0.5"
          >
            <span className="spark select-none">▸</span>
            <span>{line}</span>
          </motion.div>
        ))}
      </AnimatePresence>
      {live && (
        <div className="flex items-center gap-2 py-0.5 text-ember">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-ember" />
          <span className="text-ash">working…</span>
        </div>
      )}
      <div ref={endRef} />
    </div>
  );
}
