import type {
  ButtonHTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

export function Button({
  variant = "forge",
  className = "",
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "forge" | "ghost" }) {
  const base = variant === "forge" ? "btn-forge" : "btn-ghost";
  return (
    <button
      className={`${base} inline-flex items-center justify-center gap-2 rounded-[10px] px-4 py-2.5 text-sm ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Working"
      className={`inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent ${className}`}
    />
  );
}

export function Card({ className = "", children }: { className?: string; children: ReactNode }) {
  return <div className={`card p-5 sm:p-6 ${className}`}>{children}</div>;
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <div className="eyebrow mb-2">{children}</div>;
}

export function SectionTitle({ eyebrow, title, hint }: { eyebrow?: string; title: string; hint?: string }) {
  return (
    <div className="mb-5">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <h2 className="font-[var(--font-display)] text-xl font-bold tracking-tight text-chalk sm:text-2xl">
        {title}
      </h2>
      {hint && <p className="mt-1.5 max-w-prose text-sm text-ash">{hint}</p>}
    </div>
  );
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-xs font-medium tracking-wide text-ash-2">
      {children}
    </label>
  );
}

export function Input({ className = "", ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`field w-full px-3 py-2.5 text-sm ${className}`} {...rest} />;
}

export function Textarea({ className = "", ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`field w-full px-3 py-2.5 text-sm leading-relaxed ${className}`} {...rest} />;
}

export function Select({ className = "", children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  return (
    <select className={`field w-full appearance-none px-3 py-2.5 text-sm ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function Badge({ children, tone = "steel" }: { children: ReactNode; tone?: "steel" | "ember" | "free" }) {
  const tones: Record<string, string> = {
    steel: "border-steel bg-graphite-2 text-ash-2",
    ember: "border-ember/40 bg-ember/10 text-amber",
    free: "border-quench/40 bg-quench/10 text-quench",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 font-[var(--font-mono)] text-[0.65rem] uppercase tracking-wider ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-[10px] border border-red-500/40 bg-red-500/10 px-3.5 py-2.5 text-sm text-red-300"
    >
      {message}
    </div>
  );
}
