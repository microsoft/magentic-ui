"""
Backend Translation Tool

Provides multi-language text retrieval functionality
"""

from typing import Optional
from ..datamodel import Settings


# Translation text dictionary
TRANSLATIONS = {
    "zh-CN": {
        "backend": {
            "user_requested_stop_cancellation": "用户请求停止/取消",
            "run_cancelled_by_user": "运行被用户取消",
            "connection_closed": "连接已关闭",
            "server_shutdown": "服务器关闭",
            "run_interrupted_by_server_shutdown": "运行因服务器关闭而中断",
            "error_occurred_while_processing": "处理此运行时发生错误",
            "magentic_ui_timed_out_waiting_for_input": "Magentic-UI 在等待您的输入时超时。要恢复，请在输入框中输入后续消息，或者您可以简单地输入 'continue'。",
            "no_active_connection_for_run": "运行 {run_id} 没有活动连接",
            "run_not_found_in_database": "在数据库中未找到运行 {run_id}",
            "run_has_no_user_id": "运行 {run_id} 没有用户ID",
            "no_final_result_captured": "未捕获到运行 {run_id} 的最终结果",
            "stream_cancelled_or_connection_closed": "运行 {run_id} 的流被取消或连接已关闭",
            "stream_error_for_run": "运行 {run_id} 的流错误",
            "connection_error_for_run": "运行 {run_id} 的连接错误",
            "websocket_disconnected_while_sending": "发送消息时WebSocket断开连接，运行 {run_id}",
            "error_sending_message_for_run": "发送消息时出错，运行 {run_id}",
            "attempted_to_send_message_to_closed_connection": "尝试向已关闭的连接发送消息，运行 {run_id}",
            "received_input_response_for_inactive_run": "收到非活动运行的输入响应 {run_id}",
            "stopping_run": "正在停止运行 {run_id}",
            "error_stopping_run": "停止运行 {run_id} 时出错",
            "disconnecting_run": "正在断开运行 {run_id} 的连接",
            "cleaning_up_active_connections": "正在清理 {count} 个活动连接",
            "websocket_manager_cleanup_timed_out": "WebSocketManager清理超时",
            "error_during_websocket_manager_cleanup": "WebSocketManager清理期间出错",
            "timeout_disconnecting_run": "断开运行 {run_id} 连接超时",
            "error_disconnecting_run": "断开运行 {run_id} 连接时出错",
            "input_response_timeout_for_run": "运行 {run_id} 的输入响应超时",
            "error_handling_input_for_run": "处理运行 {run_id} 的输入时出错",
            "run_was_closed": "运行已关闭",
            "no_input_queue_for_run": "运行 {run_id} 没有输入队列",
            "sending_input_request_for_run": "正在发送运行 {run_id} 的输入请求",
            "failed_to_parse_plan": "解析计划失败",
            "failed_to_update_plan": "更新计划失败",
            "failed_to_parse_attached_files": "解析附加文件失败",
            "cannot_format_unrecognized_message_type": "无法格式化无法识别的消息类型",
            "message_formatting_error": "消息格式化错误",
            "file_not_found": "文件未找到",
            "path_is_not_a_file": "路径不是文件",
            "access_denied_file_path_outside_workspace": "访问被拒绝：文件路径在workspace目录外",
            "invalid_file_path": "无效的文件路径",
            "unsupported_file_type": "不支持的文件类型",
            "failed_to_parse_uploaded_file": "解析上传文件失败",
            "error_loading_teams": "加载团队时出错",
            "session_updated_successfully": "会话更新成功",
            "session_created_successfully": "会话创建成功",
            "please_check_form_for_errors": "请检查表单是否有错误",
            "edit_session": "编辑会话",
            "create_session": "创建会话",
            "missing_session_or_user_information": "缺少会话或用户信息",
            "creating_plan_from_conversation": "正在从对话创建计划...",
            "plan_created_successfully": "计划创建成功！",
            "failed_to_create_plan": "创建计划失败",
            "unknown_error": "未知错误",
            "this_plan_has_been_saved_to_your_library": "此计划已保存到您的库中",
            "plan_learned": "计划已学习",
            "creating_a_plan_from_this_conversation": "正在从对话创建计划",
            "learning_plan": "学习计划中...",
            "learn_a_reusable_plan_from_this_conversation": "从对话中学习可重用计划并保存到您的库中",
            "learn_plan": "学习计划"
        }
    },
    "en-US": {
        "backend": {
            "user_requested_stop_cancellation": "User requested stop/cancellation",
            "run_cancelled_by_user": "Run cancelled by user",
            "connection_closed": "Connection closed",
            "server_shutdown": "server_shutdown",
            "run_interrupted_by_server_shutdown": "Run interrupted by server shutdown",
            "error_occurred_while_processing": "An error occurred while processing this run",
            "magentic_ui_timed_out_waiting_for_input": "Magentic-UI timed out while waiting for your input. To resume, please enter a follow-up message in the input box or you can simply type 'continue'.",
            "no_active_connection_for_run": "No active connection for run {run_id}",
            "run_not_found_in_database": "Run {run_id} not found in database",
            "run_has_no_user_id": "Run {run_id} has no user ID",
            "no_final_result_captured": "No final result captured for completed run {run_id}",
            "stream_cancelled_or_connection_closed": "Stream cancelled or connection closed for run {run_id}",
            "stream_error_for_run": "Stream error for run {run_id}",
            "connection_error_for_run": "Connection error for run {run_id}",
            "websocket_disconnected_while_sending": "WebSocket disconnected while sending message for run {run_id}",
            "error_sending_message_for_run": "Error sending message for run {run_id}",
            "attempted_to_send_message_to_closed_connection": "Attempted to send message to closed connection for run {run_id}",
            "received_input_response_for_inactive_run": "Received input response for inactive run {run_id}",
            "stopping_run": "Stopping run {run_id}",
            "error_stopping_run": "Error stopping run {run_id}",
            "disconnecting_run": "Disconnecting run {run_id}",
            "cleaning_up_active_connections": "Cleaning up {count} active connections",
            "websocket_manager_cleanup_timed_out": "WebSocketManager cleanup timed out",
            "error_during_websocket_manager_cleanup": "Error during WebSocketManager cleanup",
            "timeout_disconnecting_run": "Timeout disconnecting run {run_id}",
            "error_disconnecting_run": "Error disconnecting run {run_id}",
            "input_response_timeout_for_run": "Input response timeout for run {run_id}",
            "error_handling_input_for_run": "Error handling input for run {run_id}",
            "run_was_closed": "Run was closed",
            "no_input_queue_for_run": "No input queue for run {run_id}",
            "sending_input_request_for_run": "Sending input request for run {run_id}",
            "failed_to_parse_plan": "Failed to parse plan",
            "failed_to_update_plan": "Failed to update plan",
            "failed_to_parse_attached_files": "Failed to parse attached_files",
            "cannot_format_unrecognized_message_type": "Cannot format unrecognized message type",
            "message_formatting_error": "Message formatting error",
            "file_not_found": "File not found",
            "path_is_not_a_file": "Path is not a file",
            "access_denied_file_path_outside_workspace": "Access denied: File path outside workspace",
            "invalid_file_path": "Invalid file path",
            "unsupported_file_type": "Unsupported file type",
            "failed_to_parse_uploaded_file": "Failed to parse uploaded file",
            "error_loading_teams": "Error loading teams",
            "session_updated_successfully": "Session updated successfully",
            "session_created_successfully": "Session created successfully",
            "please_check_form_for_errors": "Please check the form for errors",
            "edit_session": "Edit Session",
            "create_session": "Create Session",
            "missing_session_or_user_information": "Missing session or user information",
            "creating_plan_from_conversation": "Creating plan from conversation...",
            "plan_created_successfully": "Plan created successfully!",
            "failed_to_create_plan": "Failed to create plan",
            "unknown_error": "Unknown error",
            "this_plan_has_been_saved_to_your_library": "This plan has been saved to your library",
            "plan_learned": "Plan Learned",
            "creating_a_plan_from_this_conversation": "Creating a plan from this conversation",
            "learning_plan": "Learning Plan...",
            "learn_a_reusable_plan_from_this_conversation": "Learn a reusable plan from this conversation and save it to your library",
            "learn_plan": "Learn Plan"
        }
    }
}

# Default language
DEFAULT_LANGUAGE = "en-US"


def get_language_from_settings(settings: Optional[Settings]) -> str:
    """
    Get language setting from user settings
    
    Args:
        settings: User settings object
        
    Returns:
        str: Language code (zh-CN or en-US)
    """
    if not settings or not settings.config:
        return DEFAULT_LANGUAGE
    
    # Get language configuration from settings
    config = settings.config
    if isinstance(config, dict):
        # If it's a dictionary format, look for the language field
        language = config.get("language", DEFAULT_LANGUAGE)
    else:
        # If it's a SettingsConfig object, look for the language field
        language = getattr(config, "language", DEFAULT_LANGUAGE)
    
    # Validate language code
    if language not in ["zh-CN", "en-US"]:
        return DEFAULT_LANGUAGE
    
    return language


def get_text(key: str, language: str = DEFAULT_LANGUAGE, **kwargs: str) -> str:
    """
    Get text in the specified language
    
    Args:
        key: Translation key
        language: Language code
        **kwargs: Format parameters
        
    Returns:
        str: Translated text
    """
    # Ensure language code is valid
    if language not in TRANSLATIONS:
        language = DEFAULT_LANGUAGE
    
    # Split key by dots
    keys = key.split(".")
    current_dict = TRANSLATIONS[language]
    
    # Traverse key path
    for k in keys:
        if isinstance(current_dict, dict) and k in current_dict:
            current_dict = current_dict[k]
        else:
            # If translation not found, return the key itself
            return key
    
    # If translation text is found
    if isinstance(current_dict, str):
        # Format text (if parameters exist)
        if kwargs:
            try:
                return current_dict.format(**kwargs)
            except (KeyError, ValueError):
                return current_dict
        return current_dict
    
    # If final result is not a string, return the key itself
    return key 