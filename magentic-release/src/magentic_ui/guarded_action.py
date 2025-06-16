from .approval_guard import (
    BaseApprovalGuard,
    MaybeRequiresApproval,
    DEFAULT_REQUIRES_APPROVAL,
)
from .tools.tool_metadata import get_tool_metadata, REQUIRE_APPROVAL_KEY
from autogen_core.tools import ToolSchema
from autogen_core.models import LLMMessage
from autogen_agentchat.messages import (
    MultiModalMessage,
    TextMessage,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
    cast,
    Protocol,
    TypeVar,
    Union,
    Callable,
    Generic,
)
from dataclasses import dataclass

from inspect import iscoroutinefunction

from abc import ABC, abstractmethod

TReturn = TypeVar("TReturn", covariant=True)
TStream = TypeVar("TStream", covariant=True)


class SyncActionCallable(Protocol[TReturn]):
    def __call__(self, *args: Any, **kwargs: Any) -> TReturn: ...


class AsyncActionCallable(Protocol[TReturn]):
    async def __call__(self, *args: Any, **kwargs: Any) -> TReturn: ...


ActionCallable = SyncActionCallable[TReturn] | AsyncActionCallable[TReturn]


class CallableInvoker(Generic[TReturn]):
    def __init__(self, callable: ActionCallable[TReturn]) -> None:
        self._callable = callable
        self._is_async = iscoroutinefunction(callable)

    async def __call__(self, *args: Any, **kwargs: Any) -> TReturn:
        if self._is_async:
            return await cast(AsyncActionCallable[TReturn], self._callable)(
                *args, **kwargs
            )
        else:
            return cast(SyncActionCallable[TReturn], self._callable)(*args, **kwargs)


class ApprovalDeniedError(Exception):
    """Exception raised when an action is denied by the approval guard."""

    ...


DescriptionGenerator = Callable[[Dict[str, Any]], Union[TextMessage, MultiModalMessage]]


@dataclass
class BaseGuardedAction(Generic[TReturn], ABC):
    name: str
    action: CallableInvoker[TReturn]
    prepare: Optional[CallableInvoker[None]] = None
    cleanup: Optional[CallableInvoker[None]] = None

    @abstractmethod
    def _get_baseline(self) -> MaybeRequiresApproval: ...

    async def invoke_with_approval(
        self,
        call_arguments: Dict[str, Any],
        action_description: Union[
            TextMessage,
            MultiModalMessage,
            ActionCallable[TextMessage]
            | ActionCallable[MultiModalMessage]
            | ActionCallable[TextMessage | MultiModalMessage],
        ],
        action_context: List[LLMMessage],
        action_guard: Optional[BaseApprovalGuard],
        action_description_for_user: Optional[
            Union[TextMessage, MultiModalMessage]
        ] = None,
    ) -> TReturn:
        """
        Invokes the action with approval if the action guard is provided.
        Args:
            call_arguments (Dict[str, Any]): The arguments to pass to the action.
            action_description (TextMessage | MultiModalMessage): The description of the action to be approved in it's raw form.
            action_context (List[LLMMessage]): The context of the action to be approved.
            action_guard (ApprovalGuard, optional): The action guard to use to approve the action.
            action_description_for_user (TextMessage | MultiModalMessage, optional): The description of the action for the user.
        """
        needs_approval: bool = False
        if action_guard is not None:
            baseline: MaybeRequiresApproval = self._get_baseline()
            llm_guess: MaybeRequiresApproval = baseline

            if REQUIRE_APPROVAL_KEY in call_arguments:
                if call_arguments[REQUIRE_APPROVAL_KEY]:
                    llm_guess = "always"
                else:
                    llm_guess = "never"

            # Check if the action needs approval
            needs_approval = await action_guard.requires_approval(
                baseline,
                llm_guess,
                action_context,
            )

        if self.prepare is not None:
            await self.prepare()

        try:
            if needs_approval:
                assert action_guard is not None

                if callable(action_description):
                    # If action_description is a callable, convert it to an Invoker and call it
                    invoker = CallableInvoker(action_description)
                    action_description = await invoker(**call_arguments)

                # Get approval for the action
                if action_description_for_user is None:
                    approved = await action_guard.get_approval(action_description)
                else:
                    approved = await action_guard.get_approval(
                        action_description_for_user
                    )

                if not approved:
                    raise ApprovalDeniedError(
                        "Action was denied by the approval guard."
                    )

            # Invoke the action
            result = await self.action(**call_arguments)

            if self.cleanup is not None:
                await self.cleanup()

            return result
        except Exception:
            if self.cleanup is not None:
                await self.cleanup()

            raise


class GuardedAction(BaseGuardedAction[TReturn], Generic[TReturn]):
    def __init__(
        self,
        name: str,
        action: ActionCallable[TReturn],
        prepare: Optional[ActionCallable[None]] = None,
        cleanup: Optional[ActionCallable[None]] = None,
    ) -> None:
        super().__init__(
            name,
            CallableInvoker(action),
            CallableInvoker(prepare) if prepare else None,
            CallableInvoker(cleanup) if cleanup else None,
        )

    @staticmethod
    def from_schema(
        tool_schema: ToolSchema,
        action: ActionCallable[TReturn],
        prepare: Optional[ActionCallable[None]] = None,
        cleanup: Optional[ActionCallable[None]] = None,
    ) -> "GuardedAction[TReturn]":
        return GuardedAction(
            name=tool_schema.get("name"),
            action=CallableInvoker(action),
            prepare=CallableInvoker(prepare) if prepare else None,
            cleanup=CallableInvoker(cleanup) if cleanup else None,
        )

    def _get_baseline(self) -> MaybeRequiresApproval:
        metadata = get_tool_metadata(self.name)

        return metadata.get("requires_approval", DEFAULT_REQUIRES_APPROVAL)


class TrivialGuardedAction(BaseGuardedAction[None]):
    def __init__(
        self, name: str, baseline_override: Optional[MaybeRequiresApproval] = None
    ) -> None:
        super().__init__(name, CallableInvoker(lambda: None), None, None)
        self._baseline_override: MaybeRequiresApproval | None = baseline_override

    def _get_baseline(self) -> MaybeRequiresApproval:
        return (
            self._baseline_override
            if self._baseline_override is not None
            else DEFAULT_REQUIRES_APPROVAL
        )
