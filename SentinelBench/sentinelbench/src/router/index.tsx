import { createBrowserRouter } from "react-router-dom";
import { Suspense } from "react";
import Home from "../pages/Home";
import NotFound from "../pages/NotFound";
import RouteErrorBoundary from "../components/RouteErrorBoundary";
import { routes } from "./routes";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
    errorElement: <RouteErrorBoundary />,
  },
  ...routes
    .filter((route) => route.component !== null)
    .map((route) => {
      const Component = route.component!;
      return {
        path: route.path,
        element: (
          <Suspense fallback={<div>Loading...</div>}>
            <Component />
          </Suspense>
        ),
        errorElement: <RouteErrorBoundary />,
      };
    }),
  {
    path: "*",
    element: <NotFound />,
    errorElement: <RouteErrorBoundary />,
  },
]);
