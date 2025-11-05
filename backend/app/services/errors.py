"""Custom service-level exceptions."""


class AuthenticationError(Exception):
    """Raised when credentials are invalid or user state disallows login."""


class RateLimitExceeded(Exception):
    """Raised when too many attempts occur in a given window."""


class VerificationError(Exception):
    """Raised when verification code validation fails."""


class AccessDeniedError(Exception):
    """Raised when current user lacks required permissions."""


class WorkspaceNotFoundError(Exception):
    """Raised when requested workspace does not exist."""


class ProjectNotFoundError(Exception):
    """Raised when requested project does not exist."""


class WorkspaceConflictError(Exception):
    """Raised when workspace constraints (e.g., name uniqueness) are violated."""


class ProjectConflictError(Exception):
    """Raised when project constraints are violated."""


class RoleNotFoundError(Exception):
    """Raised when requested role does not exist or is inaccessible."""


class RoleConflictError(Exception):
    """Raised when role constraints (e.g., duplicate name) are violated."""


class DatasetNotFoundError(Exception):
    """Raised when dataset or dataset version cannot be found."""


class DatasetConflictError(Exception):
    """Raised when dataset constraints (e.g., duplicate name) are violated."""


class DatasetSizeExceededError(Exception):
    """Raised when uploaded dataset exceeds configured size limits."""


class DatasetVersionError(Exception):
    """Raised when dataset version creation rules are violated."""


class TrainingTemplateError(Exception):
    """Raised when training template operations fail."""


class TrainingJobError(Exception):
    """Raised when training job creation or execution fails."""


class TrainingValidationError(Exception):
    """Raised when training configuration validation fails."""


class TrainingSnapshotError(Exception):
    """Raised when training snapshot operations fail."""


class TrainingExperimentError(Exception):
    """Raised when training experiment metadata or comparison fails."""


class ModelRegistryError(Exception):
    """Raised when model registry operations fail."""


class ModelVersionPromotionError(ModelRegistryError):
    """Raised when model version promotion violates evaluation or policy rules."""
