import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

// Keeps a render error from blanking the whole forge.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("UI error:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="mx-auto max-w-md p-10 text-center">
          <h1 className="font-[var(--font-display)] text-2xl font-bold text-chalk">
            The forge hit a snag
          </h1>
          <p className="mt-2 text-sm text-ash">{this.state.error.message}</p>
          <button
            className="btn-forge mt-5 rounded-[10px] px-4 py-2.5 text-sm"
            onClick={() => window.location.reload()}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
