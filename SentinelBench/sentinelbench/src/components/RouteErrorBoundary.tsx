import { useRouteError, isRouteErrorResponse } from 'react-router-dom';

export default function RouteErrorBoundary() {
  const error = useRouteError();

  let errorMessage: string;
  let errorStatus: number | string = 'Unknown';

  if (isRouteErrorResponse(error)) {
    errorStatus = error.status;
    errorMessage = error.data || `${error.status} ${error.statusText}`;
  } else if (error instanceof Error) {
    errorMessage = error.message;
  } else {
    errorMessage = 'An unexpected error occurred';
  }

  const is404 = errorStatus === 404;

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-orange-50 to-yellow-50 p-6 flex items-center justify-center">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl border border-red-200/50 backdrop-blur-sm overflow-hidden">
          {/* Header */}
          <div className={`p-6 text-white ${is404 ? 'bg-gradient-to-r from-blue-500 to-purple-500' : 'bg-gradient-to-r from-red-500 to-orange-500'}`}>
            <div className="flex items-center space-x-3">
              <div className="text-4xl">{is404 ? '🔍' : '⚠️'}</div>
              <div>
                <h1 className="text-2xl font-bold">
                  {is404 ? 'Page Not Found!' : 'Unexpected Application Error!'}
                </h1>
                <p className={`mt-1 ${is404 ? 'text-blue-100' : 'text-red-100'}`}>
                  {is404 ? 'The page you\'re looking for doesn\'t exist' : 'Something went wrong with the application'}
                </p>
              </div>
            </div>
          </div>

          {/* Error Details */}
          <div className="p-6 space-y-6">
            <div className={`border rounded-lg p-4 ${is404 ? 'bg-blue-50 border-blue-200' : 'bg-red-50 border-red-200'}`}>
              <h3 className={`font-semibold mb-2 ${is404 ? 'text-blue-800' : 'text-red-800'}`}>
                Error Details:
              </h3>
              <div className="space-y-2">
                <div className={`text-sm px-2 py-1 rounded inline-block ${is404 ? 'text-blue-700 bg-blue-100' : 'text-red-700 bg-red-100'}`}>
                  <strong>Status:</strong> {errorStatus}
                </div>
                <div className={`text-sm px-2 py-1 rounded block ${is404 ? 'text-blue-700 bg-blue-100' : 'text-red-700 bg-red-100'}`}>
                  <strong>Message:</strong> {errorMessage}
                </div>
              </div>
            </div>

            {/* Recovery Actions */}
            <div className={`border rounded-lg p-4 ${is404 ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'}`}>
              <h3 className={`font-semibold mb-3 ${is404 ? 'text-green-800' : 'text-blue-800'}`}>
                {is404 ? 'What you can do:' : 'Try these steps:'}
              </h3>
              <ul className={`space-y-2 ${is404 ? 'text-green-700' : 'text-blue-700'}`}>
                {is404 ? (
                  <>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Check the URL for typos</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Return to the home page and try again</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Use the navigation menu to find what you're looking for</span>
                    </li>
                  </>
                ) : (
                  <>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Refresh the page to reload the application</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Clear your browser cache and cookies</span>
                    </li>
                    <li className="flex items-start space-x-2">
                      <span className={`mt-1 ${is404 ? 'text-green-500' : 'text-blue-500'}`}>•</span>
                      <span>Try using a different browser or incognito mode</span>
                    </li>
                  </>
                )}
              </ul>
            </div>

            {/* Contact Information */}
            <div className="bg-gradient-to-r from-purple-50 to-indigo-50 border border-purple-200 rounded-lg p-4">
              <div className="flex items-start space-x-3">
                <div className="text-2xl">🔬</div>
                <div>
                  <h3 className="font-semibold text-purple-800 mb-2">Microsoft AI Frontiers</h3>
                  <p className="text-purple-700 mb-3">
                    {is404 
                      ? 'If you believe this page should exist, please contact our development team.'
                      : 'If this error persists, please contact our development team for assistance.'
                    }
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
                onClick={() => window.location.href = '/'}
                className="flex-1 bg-gradient-to-r from-blue-500 to-blue-600 text-white px-6 py-3 rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all duration-200 shadow-sm font-medium"
              >
                🏠 Go Home
              </button>
              <button
                onClick={() => window.location.reload()}
                className="flex-1 bg-gradient-to-r from-green-500 to-green-600 text-white px-6 py-3 rounded-lg hover:from-green-600 hover:to-green-700 transition-all duration-200 shadow-sm font-medium"
              >
                🔄 Reload Page
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