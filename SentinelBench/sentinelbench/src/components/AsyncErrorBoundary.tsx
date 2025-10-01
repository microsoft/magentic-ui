import React, { Component, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void;
}

interface State {
  hasError: boolean;
  error?: Error;
}

class AsyncErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("AsyncErrorBoundary caught an error:", error, errorInfo);

    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  componentDidMount() {
    // Listen for unhandled promise rejections
    window.addEventListener("unhandledrejection", this.handlePromiseRejection);
  }

  componentWillUnmount() {
    window.removeEventListener(
      "unhandledrejection",
      this.handlePromiseRejection,
    );
  }

  handlePromiseRejection = (event: PromiseRejectionEvent) => {
    console.error("Unhandled promise rejection:", event.reason);

    // Only handle if it's within our component tree
    if (this.state.hasError) return;

    const error =
      event.reason instanceof Error
        ? event.reason
        : new Error(String(event.reason));

    this.setState({
      hasError: true,
      error,
    });

    if (this.props.onError) {
      this.props.onError(error, { componentStack: 'Promise rejection' } as React.ErrorInfo);
    }

    // Prevent the default browser behavior
    event.preventDefault();
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 my-4">
          <div className="flex items-start space-x-3">
            <div className="text-yellow-600 text-xl">⚠️</div>
            <div className="flex-1">
              <h3 className="text-sm font-semibold text-yellow-800">
                Task Error
              </h3>
              <p className="text-sm text-yellow-700 mt-1">
                An error occurred while running this task. The task may not
                function correctly.
              </p>
              <p className="text-xs text-yellow-600 mt-2">
                Error: {this.state.error?.message || "Unknown error"}
              </p>
              <button
                onClick={() => window.location.reload()}
                className="mt-3 px-3 py-1 bg-yellow-600 text-white text-xs rounded hover:bg-yellow-700 transition-colors"
              >
                Reload Task
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default AsyncErrorBoundary;
