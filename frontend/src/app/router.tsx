import { createBrowserRouter } from "react-router-dom";

import { ForgotPasswordPage } from "./(auth)/ForgotPasswordPage";
import { LoginPage } from "./(auth)/LoginPage";
import { RegisterPage } from "./(auth)/RegisterPage";
import { ResetPasswordPage } from "./(auth)/ResetPasswordPage";
import { DashboardPage } from "./dashboard/DashboardPage";
import { CleaningPipelinePage } from "./data-hub/CleaningPipelinePage";
import { DatasetUploadPage } from "./data-hub/DatasetUploadPage";
import { FormatStandardPage } from "./data-hub/FormatStandardPage";
import { QualityDashboardPage } from "./data-hub/QualityDashboardPage";
import { TemplateLibraryPage } from "./training/TemplateLibraryPage";
import { TrainingWizardPage } from "./training/TrainingWizardPage";
import { TrainingMonitorPage } from "./training/TrainingMonitorPage";
import { TrainingSnapshotsPage } from "./training/TrainingSnapshotsPage";
import { TrainingExperimentsPage } from "./training/TrainingExperimentsPage";
import { EvaluationSuitePage } from "./evaluation/EvaluationSuitePage";
import { EvaluationReportPage } from "./evaluation/EvaluationReportPage";
import { WorkspacesPage } from "./workspaces/WorkspacesPage";
import { ModelRegistryPage } from "./models/ModelRegistryPage";
import { ModelDeploymentPage } from "./deployment/DeploymentPage";
import { InferenceConsolePage } from "./inference/InferenceConsolePage";

export const appRouter = createBrowserRouter([
  {
    path: "/",
    element: <LoginPage />
  },
  {
    path: "/register",
    element: <RegisterPage />
  },
  {
    path: "/forgot-password",
    element: <ForgotPasswordPage />
  },
  {
    path: "/reset-password",
    element: <ResetPasswordPage />
  },
  {
    path: "/dashboard",
    element: <DashboardPage />
  },
  {
    path: "/workspaces",
    element: <WorkspacesPage />
  },
  {
    path: "/data-hub/upload",
    element: <DatasetUploadPage />
  },
  {
    path: "/data-hub/cleaning",
    element: <CleaningPipelinePage />
  },
  {
    path: "/data-hub/quality",
    element: <QualityDashboardPage />
  },
  {
    path: "/data-hub/formats",
    element: <FormatStandardPage />
  },
  {
    path: "/training/templates",
    element: <TemplateLibraryPage />
  },
  {
    path: "/training/wizard",
    element: <TrainingWizardPage />
  },
  {
    path: "/training/monitor",
    element: <TrainingMonitorPage />
  },
  {
    path: "/training/snapshots",
    element: <TrainingSnapshotsPage />
  },
  {
    path: "/training/experiments",
    element: <TrainingExperimentsPage />
  },
  {
    path: "/evaluation/suite",
    element: <EvaluationSuitePage />
  },
  {
    path: "/evaluation/reports/:jobId",
    element: <EvaluationReportPage />
  },
  {
    path: "/models/registry",
    element: <ModelRegistryPage />
  },
  {
    path: "/deployment",
    element: <ModelDeploymentPage />
  },
  {
    path: "/inference",
    element: <InferenceConsolePage />
  }
]);
