from typing import Optional, Tuple
from enum import Enum
from loguru import logger
from dataclasses import dataclass


class ModelErrorType(Enum):
    """Types of model errors that can occur."""

    NETWORK_ERROR = "network_error"
    API_VERSION_ERROR = "api_version_error"
    AUTHENTICATION_ERROR = "authentication_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    UNKNOWN_ERROR = "unknown_error"

    @property
    def user_message(self) -> str:
        return {
            ModelErrorType.API_VERSION_ERROR: (
                "Model API version incompatibility detected. "
                "Please update your model provider's API version or configuration."
            ),
            ModelErrorType.NETWORK_ERROR: (
                "Network connection error occurred while communicating with the model. "
                "Please check your internet connection and try again."
            ),
            ModelErrorType.AUTHENTICATION_ERROR: (
                "Authentication failed with the model provider. "
                "Please verify your API key and credentials."
            ),
            ModelErrorType.RATE_LIMIT_ERROR: (
                "Rate limit exceeded for the model provider. "
                "Please wait before making additional requests."
            ),
            ModelErrorType.UNKNOWN_ERROR: (
                "An unexpected error occurred while communicating with the model."
            ),
        }[self]


class ModelErrorHandler:
    """
    Centralized error handler for model client interactions.

    This class provides methods to classify, log, and handle different types
    of errors that can occur when interacting with model clients.
    """

    _error_keywords = {
        ModelErrorType.API_VERSION_ERROR: [
            "tool_choice",
            "tool choice",
            "badrequest",
            "api version",
            "2024-06-01",
        ],
        ModelErrorType.NETWORK_ERROR: [
            "connection",
            "timeout",
            "network",
            "unreachable",
            "dns",
        ],
        ModelErrorType.AUTHENTICATION_ERROR: [
            "unauthorized",
            "authentication",
            "api key",
            "invalid key",
        ],
        ModelErrorType.RATE_LIMIT_ERROR: ["rate limit", "quota", "too many requests"],
    }

    @staticmethod
    def classify_error(error: Exception) -> ModelErrorType:
        """
        Classify the type of error based on the exception details.

        Args:
            error: The exception that occurred

        Returns:
            ModelErrorType: The classified error type
        """
        error_str = str(error).lower()
        for error_type, keywords in ModelErrorHandler._error_keywords.items():
            if any(keyword in error_str for keyword in keywords):
                return error_type
        return ModelErrorType.UNKNOWN_ERROR

    @staticmethod
    def get_user_friendly_message(
        error_type: ModelErrorType, original_error: str
    ) -> str:
        """
        Get a user-friendly error message based on the error type.

        Args:
            error_type: The classified error type
            original_error: The original error message

        Returns:
            str: A user-friendly error message
        """
        return f"{error_type.user_message} Original error: {original_error}"

    @staticmethod
    def log_error(error: Exception, context: str = "") -> None:
        """
        Log the error with appropriate level and context.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
        """
        error_type = ModelErrorHandler.classify_error(error)
        context_prefix = f"[{context}] " if context else ""
        log_methods = {
            ModelErrorType.NETWORK_ERROR: logger.warning,
            ModelErrorType.API_VERSION_ERROR: logger.error,
            ModelErrorType.AUTHENTICATION_ERROR: logger.error,
            ModelErrorType.RATE_LIMIT_ERROR: logger.warning,
            ModelErrorType.UNKNOWN_ERROR: logger.error,
        }
        log_methods[error_type](
            f"{context_prefix}{error_type.name.replace('_', ' ').title()}: {error}"
        )

    @staticmethod
    def handle_model_error(
        error: Exception, context: str = "", should_raise: bool = False
    ) -> Tuple[ModelErrorType, str]:
        """
        Handle a model error by logging it and returning error information.

        Args:
            error: The exception that occurred
            context: Additional context about where the error occurred
            should_raise: Whether to re-raise the exception after handling

        Returns:
            Tuple[ModelErrorType, str]: The error type and user-friendly message

        Raises:
            Exception: Re-raises the original exception if should_raise is True
        """
        error_type = ModelErrorHandler.classify_error(error)
        ModelErrorHandler.log_error(error, context)
        user_message = ModelErrorHandler.get_user_friendly_message(
            error_type, str(error)
        )

        if should_raise:
            raise error

        return error_type, user_message

    @staticmethod
    def is_recoverable_error(error_type: ModelErrorType) -> bool:
        """
        Determine if an error type is potentially recoverable.

        Args:
            error_type: The classified error type

        Returns:
            bool: True if the error might be recoverable with retry
        """
        return error_type in {
            ModelErrorType.NETWORK_ERROR,
            ModelErrorType.RATE_LIMIT_ERROR,
        }


@dataclass
class ModelErrorException(Exception):
    """
    Custom exception for model errors with additional metadata.
    """

    message: str
    error_type: ModelErrorType
    original_error: Optional[Exception] = None

    def __post_init__(self):
        super().__init__(self.message)
        self.is_recoverable = ModelErrorHandler.is_recoverable_error(self.error_type)
