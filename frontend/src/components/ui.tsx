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

export function SectionTitle({ eyebrow, title, hint }: { eyebrow?: string; title: string; hint?: string }) {
  return (
    <div className="mb-5">
      <div className="mb-2.5 flex items-center gap-2.5">
        <span className="section-mark" aria-hidden="true" />
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
      </div>
      <h2 className="font-[var(--font-display)] text-xl font-extrabold tracking-tight text-chalk sm:text-[1.7rem]">
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

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-[10px] border border-red-300 bg-red-50 px-3.5 py-2.5 text-sm text-red-700"
    >
      {message}
    </div>
  );
}
