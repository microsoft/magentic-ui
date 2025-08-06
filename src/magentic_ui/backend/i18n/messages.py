"""
后端消息类

提供便捷的多语言消息获取方法
"""

from typing import Optional
from ..datamodel import Settings
from .translations import get_text, get_language_from_settings


class BackendMessages:
    """
    后端消息类，提供便捷的多语言消息获取方法
    """
    
    def __init__(self, settings: Optional[Settings] = None):
        """
        初始化消息类
        
        Args:
            settings: 用户设置对象，用于获取语言偏好
        """
        self.settings = settings
        self._language = get_language_from_settings(settings)
    
    def update_settings(self, settings: Settings) -> None:
        """
        更新用户设置
        
        Args:
            settings: 新的用户设置
        """
        self.settings = settings
        self._language = get_language_from_settings(settings)
    
    def get(self, key: str, **kwargs: str) -> str:
        """
        获取消息文本
        
        Args:
            key: 消息键
            **kwargs: 格式化参数
            
        Returns:
            str: 翻译后的消息文本
        """
        return get_text(key, self._language, **kwargs)
    
    # WebSocket相关消息
    def run_cancelled_by_user(self) -> str:
        """运行被用户取消"""
        return self.get("backend.run_cancelled_by_user")
    
    def connection_closed(self) -> str:
        """连接已关闭"""
        return self.get("backend.connection_closed")
    
    def server_shutdown(self) -> str:
        """服务器关闭"""
        return self.get("backend.server_shutdown")
    
    def run_interrupted_by_server_shutdown(self) -> str:
        """运行因服务器关闭而中断"""
        return self.get("backend.run_interrupted_by_server_shutdown")
    
    def error_occurred_while_processing(self) -> str:
        """处理此运行时发生错误"""
        return self.get("backend.error_occurred_while_processing")
    
    def magentic_ui_timed_out_waiting_for_input(self) -> str:
        """Magentic-UI在等待您的输入时超时"""
        return self.get("backend.magentic_ui_timed_out_waiting_for_input")
    
    def no_active_connection_for_run(self, run_id: int) -> str:
        """运行没有活动连接"""
        return self.get("backend.no_active_connection_for_run", run_id=run_id)
    
    def run_not_found_in_database(self, run_id: int) -> str:
        """在数据库中未找到运行"""
        return self.get("backend.run_not_found_in_database", run_id=run_id)
    
    def run_has_no_user_id(self, run_id: int) -> str:
        """运行没有用户ID"""
        return self.get("backend.run_has_no_user_id", run_id=run_id)
    
    def no_final_result_captured(self, run_id: int) -> str:
        """未捕获到运行的最终结果"""
        return self.get("backend.no_final_result_captured", run_id=run_id)
    
    def stream_cancelled_or_connection_closed(self, run_id: int) -> str:
        """流被取消或连接已关闭"""
        return self.get("backend.stream_cancelled_or_connection_closed", run_id=run_id)
    
    def stream_error_for_run(self, run_id: int) -> str:
        """运行的流错误"""
        return self.get("backend.stream_error_for_run", run_id=run_id)
    
    def connection_error_for_run(self, run_id: int) -> str:
        """运行的连接错误"""
        return self.get("backend.connection_error_for_run", run_id=run_id)
    
    def websocket_disconnected_while_sending(self, run_id: int) -> str:
        """发送消息时WebSocket断开连接"""
        return self.get("backend.websocket_disconnected_while_sending", run_id=run_id)
    
    def error_sending_message_for_run(self, run_id: int) -> str:
        """发送消息时出错"""
        return self.get("backend.error_sending_message_for_run", run_id=run_id)
    
    def attempted_to_send_message_to_closed_connection(self, run_id: int) -> str:
        """尝试向已关闭的连接发送消息"""
        return self.get("backend.attempted_to_send_message_to_closed_connection", run_id=run_id)
    
    def received_input_response_for_inactive_run(self, run_id: int) -> str:
        """收到非活动运行的输入响应"""
        return self.get("backend.received_input_response_for_inactive_run", run_id=run_id)
    
    def stopping_run(self, run_id: int) -> str:
        """正在停止运行"""
        return self.get("backend.stopping_run", run_id=run_id)
    
    def error_stopping_run(self, run_id: int) -> str:
        """停止运行时出错"""
        return self.get("backend.error_stopping_run", run_id=run_id)
    
    def disconnecting_run(self, run_id: int) -> str:
        """正在断开运行的连接"""
        return self.get("backend.disconnecting_run", run_id=run_id)
    
    def cleaning_up_active_connections(self, count: int) -> str:
        """正在清理活动连接"""
        return self.get("backend.cleaning_up_active_connections", count=count)
    
    def websocket_manager_cleanup_timed_out(self) -> str:
        """WebSocketManager清理超时"""
        return self.get("backend.websocket_manager_cleanup_timed_out")
    
    def error_during_websocket_manager_cleanup(self) -> str:
        """WebSocketManager清理期间出错"""
        return self.get("backend.error_during_websocket_manager_cleanup")
    
    def timeout_disconnecting_run(self, run_id: int) -> str:
        """断开运行连接超时"""
        return self.get("backend.timeout_disconnecting_run", run_id=run_id)
    
    def error_disconnecting_run(self, run_id: int) -> str:
        """断开运行连接时出错"""
        return self.get("backend.error_disconnecting_run", run_id=run_id)
    
    def input_response_timeout_for_run(self, run_id: int) -> str:
        """运行的输入响应超时"""
        return self.get("backend.input_response_timeout_for_run", run_id=run_id)
    
    def error_handling_input_for_run(self, run_id: int) -> str:
        """处理运行的输入时出错"""
        return self.get("backend.error_handling_input_for_run", run_id=run_id)
    
    def run_was_closed(self) -> str:
        """运行已关闭"""
        return self.get("backend.run_was_closed")
    
    def no_input_queue_for_run(self, run_id: int) -> str:
        """运行没有输入队列"""
        return self.get("backend.no_input_queue_for_run", run_id=run_id)
    
    def sending_input_request_for_run(self, run_id: int) -> str:
        """正在发送运行的输入请求"""
        return self.get("backend.sending_input_request_for_run", run_id=run_id)
    
    # 文件相关消息
    def file_not_found(self) -> str:
        """文件未找到"""
        return self.get("backend.file_not_found")
    
    def path_is_not_a_file(self) -> str:
        """路径不是文件"""
        return self.get("backend.path_is_not_a_file")
    
    def access_denied_file_path_outside_workspace(self) -> str:
        """访问被拒绝：文件路径在workspace目录外"""
        return self.get("backend.access_denied_file_path_outside_workspace")
    
    def invalid_file_path(self) -> str:
        """无效的文件路径"""
        return self.get("backend.invalid_file_path")
    
    def unsupported_file_type(self) -> str:
        """不支持的文件类型"""
        return self.get("backend.unsupported_file_type")
    
    def failed_to_parse_uploaded_file(self) -> str:
        """解析上传文件失败"""
        return self.get("backend.failed_to_parse_uploaded_file")
    
    # 会话相关消息
    def error_loading_teams(self) -> str:
        """加载团队时出错"""
        return self.get("backend.error_loading_teams")
    
    def session_updated_successfully(self) -> str:
        """会话更新成功"""
        return self.get("backend.session_updated_successfully")
    
    def session_created_successfully(self) -> str:
        """会话创建成功"""
        return self.get("backend.session_created_successfully")
    
    def please_check_form_for_errors(self) -> str:
        """请检查表单是否有错误"""
        return self.get("backend.please_check_form_for_errors")
    
    def edit_session(self) -> str:
        """编辑会话"""
        return self.get("backend.edit_session")
    
    def create_session(self) -> str:
        """创建会话"""
        return self.get("backend.create_session")
    
    # 计划相关消息
    def missing_session_or_user_information(self) -> str:
        """缺少会话或用户信息"""
        return self.get("backend.missing_session_or_user_information")
    
    def creating_plan_from_conversation(self) -> str:
        """正在从对话创建计划..."""
        return self.get("backend.creating_plan_from_conversation")
    
    def plan_created_successfully(self) -> str:
        """计划创建成功！"""
        return self.get("backend.plan_created_successfully")
    
    def failed_to_create_plan(self) -> str:
        """创建计划失败"""
        return self.get("backend.failed_to_create_plan")
    
    def unknown_error(self) -> str:
        """未知错误"""
        return self.get("backend.unknown_error")
    
    def this_plan_has_been_saved_to_your_library(self) -> str:
        """此计划已保存到您的库中"""
        return self.get("backend.this_plan_has_been_saved_to_your_library")
    
    def plan_learned(self) -> str:
        """计划已学习"""
        return self.get("backend.plan_learned")
    
    def creating_a_plan_from_this_conversation(self) -> str:
        """正在从对话创建计划"""
        return self.get("backend.creating_a_plan_from_this_conversation")
    
    def learning_plan(self) -> str:
        """学习计划中..."""
        return self.get("backend.learning_plan")
    
    def learn_a_reusable_plan_from_this_conversation(self) -> str:
        """从对话中学习可重用计划并保存到您的库中"""
        return self.get("backend.learn_a_reusable_plan_from_this_conversation")
    
    def learn_plan(self) -> str:
        """学习计划"""
        return self.get("backend.learn_plan")
    
    # 错误相关消息
    def failed_to_parse_plan(self) -> str:
        """解析计划失败"""
        return self.get("backend.failed_to_parse_plan")
    
    def failed_to_update_plan(self) -> str:
        """更新计划失败"""
        return self.get("backend.failed_to_update_plan")
    
    def failed_to_parse_attached_files(self) -> str:
        """解析附加文件失败"""
        return self.get("backend.failed_to_parse_attached_files")
    
    def cannot_format_unrecognized_message_type(self) -> str:
        """无法格式化无法识别的消息类型"""
        return self.get("backend.cannot_format_unrecognized_message_type")
    
    def message_formatting_error(self) -> str:
        """消息格式化错误"""
        return self.get("backend.message_formatting_error") 