import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
  errorInfo?: ErrorInfo;
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo
    });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-gradient-to-br from-red-50 via-orange-50 to-yellow-50 p-6 flex items-center justify-center">
          <div className="max-w-2xl mx-auto">
            <div className="bg-white rounded-2xl shadow-2xl border border-red-200/50 backdrop-blur-sm overflow-hidden">
              {/* Header */}
              <div className="bg-gradient-to-r from-red-500 to-orange-500 p-6 text-white">
                <div className="flex items-center space-x-3">
                  <div className="text-4xl">⚠️</div>
                  <div>
                    <h1 className="text-2xl font-bold">Unexpected Application Error!</h1>
                    <p className="text-red-100 mt-1">Something went wrong in the application</p>
                  </div>
                </div>
              </div>

              {/* Error Details */}
              <div className="p-6 space-y-6">
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <h3 className="font-semibold text-red-800 mb-2">Error Details:</h3>
                  <code className="text-sm text-red-700 bg-red-100 px-2 py-1 rounded block">
                    {this.state.error?.message || 'Unknown error occurred'}
                  </code>
                </div>

                {/* Stack Trace (Collapsible) */}
                <details className="bg-gray-50 border border-gray-200 rounded-lg">
                  <summary className="p-4 cursor-pointer font-medium text-gray-700 hover:bg-gray-100 transition-colors">
                    View Technical Details
                  </summary>
                  <div className="p-4 pt-0">
                    <pre className="text-xs text-gray-600 overflow-auto max-h-64 bg-white p-3 rounded border">
                      {this.state.error?.stack}
                      {this.state.errorInfo?.componentStack}
                    </pre>
                  </div>
                </details>

                {/* Recovery Actions */}
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="font-semibold text-blue-800 mb-3">Try these steps:</h3>
                  <ul className="space-y-2 text-blue-700">
                    <li className="flex items-start space-x-2">
                      <span className="text-blue-500 mt-1">•</span>
                      <span>Refresh the page to reload the application</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className="text-blue-500 mt-1">•</span>
                      <span>Clear your browser cache and cookies</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className="text-blue-500 mt-1">•</span>
                      <span>Try using a different browser or incognito mode</span>
                    </li>
                  </ul>
                </div>

                {/* Contact Information */}
                <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg p-4">
                  <div className="flex items-start space-x-3">
                    <div className="text-2xl">🔬</div>
                    <div>
                      <h3 className="font-semibold text-purple-800 mb-2">Microsoft AI Frontiers</h3>
                      <p className="text-purple-700 mb-3">
                        If this error persists, please contact our development team for assistance.
                      </p>
                      <div className="bg-white border border-purple-200 rounded-lg p-3">
                        <p className="text-sm text-purple-600 mb-1">Contact Email:</p>
                        <a 
                          href="mailto:mkunzlermaldaner@ufl.edu"
                          className="text-purple-800 font-medium hover:text-purple-900 transition-colors"
                        >
                          mkunzlermaldaner@ufl.edu
                        </a>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex space-x-4">
                  <button
                    onClick={() => window.location.reload()}
                    className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-3 rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all duration-200 shadow-sm font-medium"
                  >
                    🔄 Reload Page
                  </button>
                  <button
                    onClick={() => window.history.back()}
                    className="flex-1 bg-gradient-to-r from-gray-500 to-gray-600 text-white px-6 py-3 rounded-lg hover:from-gray-600 hover:to-gray-700 transition-all duration-200 shadow-sm font-medium"
                  >
                    ← Go Back
                  </button>
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="text-center mt-6 text-gray-500 text-sm">
              💿 Hey developer 👋<br />
              You can provide a way better UX than this when your app throws errors by providing your own ErrorBoundary or errorElement prop on your route.
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;