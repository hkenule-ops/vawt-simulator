import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  label?: string;
}

interface State {
  error: Error | null;
}

/** Catches render errors so the whole app does not go blank. */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[ErrorBoundary${this.props.label ? `:${this.props.label}` : ""}]`, error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div
          style={{
            margin: 16,
            padding: 16,
            borderRadius: 8,
            background: "#331010",
            border: "1px solid #5c1a1a",
            color: "#fca5a5",
            fontFamily: "system-ui, sans-serif",
            fontSize: 13,
            lineHeight: 1.5,
          }}
        >
          <strong style={{ color: "#fecaca" }}>
            {this.props.label ? `${this.props.label} failed` : "UI error"}
          </strong>
          <pre style={{ whiteSpace: "pre-wrap", margin: "8px 0 0", color: "#f87171" }}>
            {this.state.error.message}
          </pre>
          <button
            type="button"
            style={{
              marginTop: 10,
              background: "#450a0a",
              color: "#fecaca",
              border: "1px solid #7f1d1d",
              borderRadius: 6,
              padding: "6px 12px",
              cursor: "pointer",
            }}
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
