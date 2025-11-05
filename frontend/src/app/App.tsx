import { Suspense } from "react";
import { RouterProvider } from "react-router-dom";

import { appRouter } from "./router";

export default function App() {
  return (
    <Suspense fallback={<div className="p-6">正在加载界面...</div>}>
      <RouterProvider router={appRouter} />
    </Suspense>
  );
}
