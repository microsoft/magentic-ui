from dataclasses import dataclass
from typing import Optional, Union, Dict, Any

from autogen_core import ComponentModel


@dataclass
class EndpointConfigs:
    """Configuration class for Magentic UI endpoints.
    Attributes:
        orchestrator (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the orchestrator component. Default: None.
        web_surfer (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the web surfer component. Default: None.
        coder (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the coder component. Default: None.
        file_surfer (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the file surfer component. Default: None.
        action_guard (Optional[Union[ComponentModel, Dict[str, Any]]]): Configuration for the action guard component. Default: None.
    """

    orchestrator: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    web_surfer: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    coder: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    file_surfer: Optional[Union[ComponentModel, Dict[str, Any]]] = None
    action_guard: Optional[Union[ComponentModel, Dict[str, Any]]] = None
