export default function NotFound() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-purple-50 to-indigo-50 p-6 flex items-center justify-center">
      <div className="max-w-2xl mx-auto">
        <div className="bg-white rounded-2xl shadow-2xl border border-blue-200/50 backdrop-blur-sm overflow-hidden">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-500 to-purple-500 p-6 text-white">
            <div className="flex items-center space-x-3">
              <div className="text-4xl">🔍</div>
              <div>
                <h1 className="text-2xl font-bold">Page Not Found!</h1>
                <p className="text-blue-100 mt-1">The page you're looking for doesn't exist</p>
              </div>
            </div>
          </div>

          {/* Error Details */}
          <div className="p-6 space-y-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h3 className="font-semibold text-blue-800 mb-2">Error Details:</h3>
              <div className="space-y-2">
                <div className="text-sm text-blue-700 bg-blue-100 px-2 py-1 rounded inline-block">
                  <strong>Status:</strong> 404
                </div>
                <div className="text-sm text-blue-700 bg-blue-100 px-2 py-1 rounded block">
                  <strong>Message:</strong> Not Found
                </div>
              </div>
            </div>

            {/* Recovery Actions */}
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <h3 className="font-semibold text-green-800 mb-3">What you can do:</h3>
              <ul className="space-y-2 text-green-700">
                <li className="flex items-start space-x-2">
                  <span className="text-green-500 mt-1">•</span>
                  <span>Check the URL for typos</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-green-500 mt-1">•</span>
                  <span>Return to the home page and try again</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-green-500 mt-1">•</span>
                  <span>Use the navigation menu to find what you're looking for</span>
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
                    If you believe this page should exist, please contact our development team.
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