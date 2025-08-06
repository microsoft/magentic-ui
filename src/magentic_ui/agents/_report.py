import asyncio
from pathlib import Path
import tempfile
from typing import AsyncGenerator, List, Sequence, Optional, Dict, Any, Union
from typing import Mapping
from loguru import logger
from datetime import datetime
from pydantic import Field, BaseModel
from autogen_core import CancellationToken, ComponentModel, Component
from autogen_core.models import (
    ChatCompletionClient,
    SystemMessage,
)
from typing_extensions import Self
import re

from autogen_agentchat.agents import BaseChatAgent
from autogen_core.model_context import (
    ChatCompletionContext,
    TokenLimitedChatCompletionContext,
)
from autogen_agentchat.base import Response
from autogen_agentchat.state import BaseState
from autogen_agentchat.messages import (
    BaseAgentEvent,
    BaseChatMessage,
    TextMessage,
    MessageFactory,
)

from ..utils import thread_to_context
from ..approval_guard import BaseApprovalGuard
from ..guarded_action import ApprovalDeniedError, TrivialGuardedAction
from magentic_ui.agents._prompt import (
    REPORT_TEMPLATE_OUTLINE_PROMPT,
    REPORT_FREE_OUTLINE_PROMPT,
    REPORT_SECTION_WRITING_PROMPT,
    REPORT_REVIEW_PROMPT,
    REPORT_SYSTEM_PROMPT_TEMPLATE
)
from loguru import logger as trace_logger


class ReportSection(BaseModel):
    """报告章节模型"""
    title: str
    content: str
    order: int
    is_completed: bool = False


class ReportOutline(BaseModel):
    """报告大纲模型"""
    title: str
    sections: List[Dict[str, Any]]
    introduction: str
    conclusion: str
    template_type: str = "default"  # 添加模板类型


class TaskAnalysisResult(BaseModel):
    """任务分析结果"""
    need_outline: bool = False
    need_chapter_writing: bool = False
    report_type: str = "default"  # 报告类型
    task_description: str = ""


# 预设大纲模板
OUTLINE_TEMPLATES = {
    "default": {
        "name": "通用调研报告",
        "sections": [
            {"title": "背景介绍", "description": "介绍调研背景、目的和意义"},
            {"title": "调研方法", "description": "说明调研方法、数据来源和分析方法"},
            {"title": "调研结果", "description": "详细阐述调研发现和关键结果"},
            {"title": "分析讨论", "description": "对调研结果进行深入分析和讨论"},
            {"title": "结论建议", "description": "总结结论并提出相关建议"}
        ]
    },
    "data_analysis": {
        "name": "数据分析报告",
        "sections": [
            {"title": "数据概览", "description": "介绍数据概览、数据来源和分析方法"},
            {"title": "数据分析", "description": "详细阐述数据分析和关键结果"},
            {"title": "数据结论", "description": "对数据分析结果进行总结和结论"},
            {"title": "数据建议", "description": "对数据分析结果提出相关建议"}
        ]
    },
    "technology": {
        "name": "科技类调研报告",
        "sections": [
            {"title": "技术背景", "description": "介绍相关技术背景和发展现状"},
            {"title": "技术分析", "description": "详细分析技术特点、优势和局限性"},
            {"title": "市场应用", "description": "分析技术在市场中的应用情况"},
            {"title": "发展趋势", "description": "预测技术未来发展趋势"},
            {"title": "风险评估", "description": "评估技术应用的风险和挑战"},
            {"title": "建议措施", "description": "提出技术应用和发展建议"}
        ]
    },
    "finance": {
        "name": "金融类调研报告",
        "sections": [
            {"title": "市场概况", "description": "分析金融市场整体概况和环境"},
            {"title": "产品分析", "description": "详细分析金融产品特点和表现"},
            {"title": "风险评估", "description": "评估投资风险和市场风险"},
            {"title": "收益分析", "description": "分析预期收益和历史表现"},
            {"title": "政策影响", "description": "分析相关政策对市场的影响"},
            {"title": "投资建议", "description": "提供投资建议和策略"}
        ]
    },
    "code_design": {
        "name": "代码设计文档",
        "sections": [
            {"title": "需求分析", "description": "详细分析功能需求和非功能需求"},
            {"title": "系统架构", "description": "设计系统整体架构和模块划分"},
            {"title": "接口设计", "description": "定义各模块间的接口和数据格式"},
            {"title": "数据库设计", "description": "设计数据库表结构和关系"},
            {"title": "实现细节", "description": "描述关键功能的实现细节"},
            {"title": "测试方案", "description": "制定测试计划和测试用例"}
        ]
    }
}


async def _analyze_task_requirements(
    chat_history: List[BaseChatMessage],
    model_client: ChatCompletionClient,
    model_context: ChatCompletionContext,
    cancellation_token: CancellationToken
) -> TaskAnalysisResult:
    """使用大模型分析任务需求，判断需要执行哪些步骤"""
    
    # 构建分析提示
    latest_message = ""
    if chat_history:
        latest_msg = chat_history[-1]
        latest_message = str(getattr(latest_msg, 'content', latest_msg))
    
    # 收集对话历史内容
    history_content = ""
    for msg in chat_history[-10:]:  # 只取最近10条消息
        content = str(getattr(msg, 'content', ''))
        if content:
            history_content += f"- {content[:200]}...\n"
    
    analysis_prompt = f"""
    请分析以下任务请求和对话历史，判断用户希望执行哪些操作：

    当前任务请求：
    {latest_message}

    对话历史（最近内容）：
    {history_content}

    请分析并判断：
    1. 是否需要生成报告大纲？
    2. 是否需要逐章编写内容？
    4. 报告类型是什么？（{'/'.join(OUTLINE_TEMPLATES.keys())}）

    判断规则：
    - 如果任务要求进行写作，且对话历史中没有大纲，则需要生成大纲
    - 如果用户要求进行完整的写作，且对话历史中没有具体章节的写作内容，则需要逐章编写
    - 如果对话历史中已有大纲但用户要求写内容，则只需要逐章编写

    请用以下JSON格式回复：
    {{
        "need_outline": true/false,
        "need_chapter_writing": true/false,
        "report_type": "{'/'.join(OUTLINE_TEMPLATES.keys())}",
        "task_description": "任务描述"
    }}
    """
    
    # 使用模型进行分析
    await model_context.clear()
    await model_context.add_message(SystemMessage(content="你是一个任务分析助手，专门分析用户的报告生成需求。"))
    from autogen_core.models import UserMessage
    await model_context.add_message(UserMessage(content=analysis_prompt, source="user"))
    
    token_limited_context = await model_context.get_messages()
    
    result = await model_client.create(
        messages=token_limited_context, 
        cancellation_token=cancellation_token
    )
    
    # 解析结果
    result_content = ""
    if result.content:
        if isinstance(result.content, str):
            result_content = result.content
        else:
            result_content = str(result.content)
    
    # 尝试解析JSON
    try:
        import json
        # 提取JSON部分
        json_match = re.search(r'\{.*\}', result_content, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            analysis_data = json.loads(json_str)
            
            return TaskAnalysisResult(
                need_outline=analysis_data.get("need_outline", False),
                need_chapter_writing=analysis_data.get("need_chapter_writing", False),
                report_type=analysis_data.get("report_type", "default"),
                task_description=analysis_data.get("task_description", latest_message)
            )
    except Exception as e:
        logger.warning(f"解析任务分析结果失败: {e}")
    
    # 如果解析失败，使用简单规则判断
    task_lower = latest_message.lower()
    report_type = "default"
    
    if any(word in task_lower for word in ["科技", "技术", "technology", "tech"]):
        report_type = "technology"
    elif any(word in task_lower for word in ["数据", "分析", "data", "analysis", "数据分析"]):
        report_type = "data_analysis"
    elif any(word in task_lower for word in ["金融", "投资", "finance", "financial"]):
        report_type = "finance"
    elif any(word in task_lower for word in ["代码", "设计", "code", "design", "软件", "系统"]):
        report_type = "code_design"
    
    need_outline = "大纲" in latest_message or "outline" in task_lower
    need_chapter_writing = any(word in latest_message for word in ["撰写", "编写", "写作", "章节"])
    
    return TaskAnalysisResult(
        need_outline=need_outline,
        need_chapter_writing=need_chapter_writing,
        report_type=report_type,
        task_description=latest_message
    )


def _extract_sources_from_context(context_messages: List[BaseChatMessage]) -> List[dict[str, str]]:
    """从上下文中提取信息来源"""
    sources: List[dict[str, str]] = []

    for msg in context_messages:
        content = str(getattr(msg, 'content', ''))
        trace_logger.info(f"提取来源: {content}")
        if content:
            source_pattern = r'URL:\s*([^\s\n]+)[\s\n]+标题:\s*(.+?)\s*内容总结:\s*(.+?)(?=\n\n---|$)'
            res = re.findall(source_pattern, content, re.DOTALL)
            if res:
                trace_logger.info(f"引用来源: {res}")
                for source in res:
                    sources.append({
                        "url": source[0],
                        "title": source[1],
                        "summary": source[2]
                    })
            
            # deep_search_pattern = r'^深度搜索完成'
            # source_pattern = r'URL:(.+)标题:(.+)内容总结:(.+)'
            # deep_search_flag = re.search(deep_search_pattern, content, re.DOTALL)
            # if deep_search_flag:
            #     deep_search_res = content.split("\n\n---\n\n")
            #     for res in deep_search_res:
            #         res = re.findall(source_pattern, res, re.DOTALL)
            #         if res:
            #             trace_logger.info(f"引用来源: {res}")
            #             for source in res:
            #                 sources.append({
            #                     "url": source[0],
            #                     "title": source[1],
            #                     "summary": source[2]
            #                 })
            # else:
            #     # 查找URL:...标题:...内容总结:...格式的消息，并提取出消息内的标题和url
            #     res = re.findall(source_pattern, content, re.DOTALL)
            #     if res:
            #         trace_logger.info(f"引用来源: {res}")
            #         for source in res:
            #             sources.append({
            #                 "url": source[0],
            #                 "title": source[1],
            #                 "summary": source[2]
            #             })
                    
    return sources


def _extract_outline_from_history(chat_history: List[BaseChatMessage]) -> Optional[ReportOutline]:
    """从对话历史中提取大纲信息"""
    for msg in reversed(chat_history):
        content = str(getattr(msg, 'content', ''))
        if content and ("报告大纲" in content or "outline" in content.lower() or content.startswith("# ")):
            return _extract_outline_from_text(content, "default")
    return None


def _generate_outline_from_template(template_type: str, task_description: str) -> str:
    """根据模板生成大纲"""
    if template_type not in OUTLINE_TEMPLATES:
        template_type = "default"
    
    template = OUTLINE_TEMPLATES[template_type]
    
    outline_content = f"# {template['name']}\n\n"
    
    for section in template['sections']:
        section_dict = section if isinstance(section, dict) else {}
        outline_content += f"## {section_dict.get('title', '')}\n{section_dict.get('description', '')}\n\n"
    
    return outline_content


def _extract_outline_from_text(text: str, template_type: str = "default") -> ReportOutline:
    """从文本中提取报告大纲"""
    lines = text.split('\n')
    title = ""
    sections: List[Dict[str, Any]] = []
    introduction = ""
    conclusion = ""
    
    current_section: Optional[Dict[str, Any]] = None
    in_intro = False
    in_conclusion = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 检测标题
        if line.startswith('# '):
            title = line[2:].strip()
        elif line.startswith('## '):
            # 新的章节
            section_title = line[3:].strip()
            if section_title.lower() in ['引言', 'introduction']:
                in_intro = True
                in_conclusion = False
                if current_section:
                    sections.append(current_section)
                current_section = None
            elif section_title.lower() in ['结论', 'conclusion']:
                in_conclusion = True
                in_intro = False
                if current_section:
                    sections.append(current_section)
                current_section = None
            else:
                if current_section:
                    sections.append(current_section)
                current_section = {
                    'title': section_title,
                    'description': '',
                    'order': len(sections) + 1
                }
                in_intro = False
                in_conclusion = False
        else:
            # 内容行
            if in_intro:
                introduction += line + '\n'
            elif in_conclusion:
                conclusion += line + '\n'
            elif current_section:
                current_section['description'] = str(current_section.get('description', '')) + line + '\n'
    
    if current_section:
        sections.append(current_section)
    
    return ReportOutline(
        title=title or "调查研究报告",
        sections=sections,
        introduction=introduction.strip(),
        conclusion=conclusion.strip(),
        template_type=template_type
    )


async def _invoke_report_action_guard(
    thread: Sequence[BaseChatMessage | BaseAgentEvent],
    delta: Sequence[BaseChatMessage | BaseAgentEvent],
    report_message: TextMessage,
    agent_name: str,
    model_client: ChatCompletionClient,
    approval_guard: BaseApprovalGuard | None,
    action_type: str = "report_generation"
) -> None:
    """调用报告生成的审批守卫"""
    guarded_action = TrivialGuardedAction(action_type, baseline_override="maybe")
    
    assert delta[-1] == report_message
    
    thread_list = list(thread) + list(delta)
    
    context = thread_to_context(
        thread_list,
        agent_name,
        is_multimodal=model_client.model_info["vision"],
    )
    
    action_description_for_user = TextMessage(
        content=f"是否要执行{action_type}操作？",
        source=agent_name,
    )
    
    await guarded_action.invoke_with_approval(
        {}, report_message, context, approval_guard, action_description_for_user
    )


async def _generate_report_with_review(
    system_prompt: str,
    thread: Sequence[BaseChatMessage],
    agent_name: str,
    model_client: ChatCompletionClient,
    work_dir: Path,
    max_review_rounds: int,
    cancellation_token: CancellationToken,
    model_context: ChatCompletionContext,
    approval_guard: BaseApprovalGuard | None,
    task_analysis: TaskAnalysisResult,
) -> AsyncGenerator[Union[TextMessage, bool], None]:
    """生成报告并进行审查润色的主要流程"""
    
    delta: List[Union[BaseChatMessage, BaseAgentEvent]] = []
    report_generated = False
    
    # 提取信息来源
    sources = _extract_sources_from_context(list(thread))
    
    try:
        outline: Optional[ReportOutline] = None
        full_report_content = ""
        
        # 第一步：生成大纲（如果需要）
        if task_analysis.need_outline:
            if task_analysis.report_type != "default":
                # 使用模板生成大纲，TODO 生成大纲的标题即可不要生成内容
                template_outline = _generate_outline_from_template(
                    task_analysis.report_type, 
                    task_analysis.task_description
                )
                
                outline_prompt = REPORT_TEMPLATE_OUTLINE_PROMPT.format(
                    task_description=task_analysis.task_description,
                    report_type_name=OUTLINE_TEMPLATES[task_analysis.report_type]['name'],
                    template_outline=template_outline
                )
            else:
                # 不使用模板，自由生成大纲
                outline_prompt = REPORT_FREE_OUTLINE_PROMPT.format(
                    task_description=task_analysis.task_description
                )
            
            current_thread = (
                list(thread)
                + list(delta)
                + [TextMessage(source="user", content=outline_prompt)]
            )
            
            context = [SystemMessage(content=system_prompt)] + thread_to_context(
                current_thread,
                agent_name,
                is_multimodal=model_client.model_info["vision"],
            )
            
            # 生成大纲
            await model_context.clear()
            for msg in context:
                await model_context.add_message(msg)
            token_limited_context = await model_context.get_messages()
            
            outline_result = await model_client.create(
                messages=token_limited_context, cancellation_token=cancellation_token
            )
            
            # 确保内容是字符串类型
            outline_content = ""
            if outline_result.content:
                if isinstance(outline_result.content, str):
                    outline_content = outline_result.content
                else:
                    outline_content = str(outline_result.content)
            
            outline_msg = TextMessage(
                source=agent_name + "-outline",
                metadata={"internal": "no", "type": "report_outline"},
                content=f"📋 **报告大纲生成完成**\n\n{outline_content}",
            )
            delta.append(outline_msg)
            yield outline_msg
            
            # 解析大纲
            outline = _extract_outline_from_text(outline_content, task_analysis.report_type)
            
            # 检查是否需要审批
            if approval_guard is not None:
                await _invoke_report_action_guard(
                    thread=thread,
                    delta=delta,
                    report_message=outline_msg,
                    agent_name=agent_name,
                    model_client=model_client,
                    approval_guard=approval_guard,
                    action_type="outline_generation"
                )
        
        # 第二步：逐章节写作（如果需要）
        if task_analysis.need_chapter_writing:
            if outline is None:
                # 从对话历史中提取大纲
                outline = _extract_outline_from_history(list(thread))
                
                if outline is None:
                    # 如果仍然没有大纲，生成一个默认大纲
                    default_outline = _generate_outline_from_template("default", task_analysis.task_description)
                    outline = _extract_outline_from_text(default_outline, "default")
            
            report_sections: List[ReportSection] = []
            full_report_content = f"# {outline.title}\n\n"
            
            # 只写各个章节，不写引言和结论
            for i, section in enumerate(outline.sections):
                section_title = str(section.get('title', f'章节{i+1}'))
                section_description = str(section.get('description', ''))
                
                # TODO 将sources添加到section_prompt中
                section_prompt = REPORT_SECTION_WRITING_PROMPT.format(
                    section_number=i+1,
                    section_title=section_title,
                    section_description=section_description,
                    sources="\n\n".join([f"[{i+1}]{source['title']} - {source['url']}\n{source['summary']}" for i, source in enumerate(sources)]) if sources else "无特定来源",
                    task_description=task_analysis.task_description
                )
                
                trace_logger.info(f"section_prompt: {section_prompt}")
                
                current_thread = (
                    list(thread)
                    + list(delta)
                    + [TextMessage(source="user", content=section_prompt)]
                )
                
                context = [SystemMessage(content=system_prompt)] + thread_to_context(
                    current_thread,
                    agent_name,
                    is_multimodal=model_client.model_info["vision"],
                )
                
                await model_context.clear()
                for msg in context:
                    await model_context.add_message(msg)
                token_limited_context = await model_context.get_messages()
                
                section_result = await model_client.create(
                    messages=token_limited_context, cancellation_token=cancellation_token
                )
                
                # 确保内容是字符串类型
                section_content = ""
                if section_result.content:
                    if isinstance(section_result.content, str):
                        section_content = section_result.content
                    else:
                        section_content = str(section_result.content)
                
                section_msg = TextMessage(
                    source=agent_name + "-writer",
                    metadata={"internal": "no", "type": "section_content"},
                    content=f"✍️ **第{i+1}章节《{section_title}》撰写完成**\n\n{section_content}",
                )
                delta.append(section_msg)
                yield section_msg
                
                full_report_content += f"## {section_title}\n\n{section_content}\n\n"
                
                # 提取该章节引用的来源
                section_sources: List[dict[str, str]] = []
                for source in sources:
                    if source['url'] in section_content:
                        section_sources.append(source)
                
                report_sections.append(ReportSection(
                    title=section_title,
                    content=section_content,
                    order=i+1,
                    is_completed=True
                ))
            
            # TODO 参考来源修改
            if sources:
                full_report_content += "## 参考来源\n\n"
                for i, source in enumerate(sources):
                    full_report_content += f"[{i+1}]{source['title']} - {source['url']}\n"
                full_report_content += "\n"
        
        # # 第三步：审查和润色（如果有内容需要审查）
        # if task_analysis.need_chapter_writing and full_report_content:
        #     for review_round in range(max_review_rounds):
        #         review_prompt = REPORT_REVIEW_PROMPT.format(
        #             full_report_content=full_report_content
        #         )
                
        #         current_thread = (
        #             list(thread)
        #             + list(delta)
        #             + [TextMessage(source="user", content=review_prompt)]
        #         )
                
        #         context = [SystemMessage(content=system_prompt)] + thread_to_context(
        #             current_thread,
        #             agent_name,
        #             is_multimodal=model_client.model_info["vision"],
        #         )
                
        #         await model_context.clear()
        #         for msg in context:
        #             await model_context.add_message(msg)
        #         token_limited_context = await model_context.get_messages()
                
        #         review_result = await model_client.create(
        #             messages=token_limited_context, cancellation_token=cancellation_token
        #         )
                
        #         # 确保内容是字符串类型
        #         review_content = ""
        #         if review_result.content:
        #             if isinstance(review_result.content, str):
        #                 review_content = review_result.content
        #             else:
        #                 review_content = str(review_result.content)
                
        #         review_msg = TextMessage(
        #             source=agent_name + "-reviewer",
        #             metadata={"internal": "no", "type": "report_review"},
        #             content=f"🔍 **第{review_round + 1}轮审查润色完成**\n\n{review_content}...",
        #         )
        #         delta.append(review_msg)
        #         yield review_msg
                
        #         # 更新报告内容
        #         full_report_content = review_content
        
        # 第四步：保存MD文件（如果需要）
        if full_report_content:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_type_name = OUTLINE_TEMPLATES.get(task_analysis.report_type, {}).get('name', '调查研究报告')
            filename = f"{report_type_name}_{timestamp}.md"
            file_path = work_dir / filename
            
            # 确保工作目录存在
            work_dir.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(full_report_content)
            
            save_msg = TextMessage(
                source=agent_name + "-saver",
                metadata={"internal": "no", "type": "file_save"},
                content=f"💾 **报告已保存**\n\n文件路径：{file_path}\n文件名：{filename}",
            )
            delta.append(save_msg)
            yield save_msg
        
        report_generated = True
        
    except Exception as e:
        error_msg = TextMessage(
            source=agent_name + "-error",
            metadata={"internal": "no", "type": "error"},
            content=f"❌ **报告生成过程中发生错误**\n\n错误信息：{str(e)}",
        )
        delta.append(error_msg)
        yield error_msg
    
    yield report_generated


class ReportAgentConfig(BaseModel):
    name: str
    model_client: ComponentModel
    description: str = """
    一个专门用于生成调查研究报告的智能代理。
    它能够根据上下文信息生成结构化的调查研究报告，包括大纲制定、逐章写作、审查润色等完整流程。
    最终输出专业的Markdown格式报告文件。
    """
    max_review_rounds: int = 1
    auto_save: bool = True


class ReportAgentState(BaseState):
    chat_history: List[BaseChatMessage] = Field(default_factory=list)
    current_report: Optional[Dict[str, Any]] = None
    type: str = Field(default="ReportAgentState")


class ReportAgent(BaseChatAgent, Component[ReportAgentConfig]):
    """专门用于生成调查研究报告的智能代理
    
    该代理能够：
    1. 根据上下文信息生成报告大纲
    2. 逐章节撰写详细内容
    3. 审查和润色报告
    4. 输出专业的Markdown格式报告文件
    """
    
    component_type = "agent"
    component_config_schema = ReportAgentConfig
    component_provider_override = "magentic_ui.agents.ReportAgent"
    
    DEFAULT_DESCRIPTION = """
    一个专门用于生成调查研究报告的智能代理。
    它能够根据上下文信息生成结构化的调查研究报告，包括大纲制定、逐章写作、审查润色等完整流程。
    注意：它只能够基于已搜集并整理好的信息生成报告，不支持信息的搜集和整理。
    """
    
    system_prompt_template = REPORT_SYSTEM_PROMPT_TEMPLATE.format(
        date_today=datetime.now().strftime("%Y-%m-%d")
    )
    
    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        model_context_token_limit: int = 128000,
        description: str = DEFAULT_DESCRIPTION,
        max_review_rounds: int = 2,
        auto_save: bool = True,
        work_dir: Path | str | None = None,
        approval_guard: BaseApprovalGuard | None = None,
    ) -> None:
        """初始化ReportAgent
        
        Args:
            name: 代理名称
            model_client: 语言模型客户端
            model_context_token_limit: 模型上下文令牌限制
            description: 代理描述
            max_review_rounds: 最大审查轮数
            auto_save: 是否自动保存报告
            work_dir: 工作目录
            approval_guard: 审批守卫
        """
        super().__init__(name, description)
        self._model_client = model_client
        self._model_context = TokenLimitedChatCompletionContext(
            model_client, token_limit=model_context_token_limit
        )
        self._chat_history: List[BaseChatMessage] = []
        self._max_review_rounds = max_review_rounds
        self._auto_save = auto_save
        self.is_paused = False
        self._paused = asyncio.Event()
        self._approval_guard = approval_guard
        self._current_report: Optional[Dict[str, Any]] = None
        
        if work_dir is None:
            self._work_dir = Path(tempfile.mkdtemp())
            self._cleanup_work_dir = True
        else:
            self._work_dir = Path(work_dir)
            self._cleanup_work_dir = False
    
    async def lazy_init(self) -> None:
        """延迟初始化"""
        pass
    
    async def close(self) -> None:
        """清理资源"""
        logger.info("Closing ReportAgent...")
        if self._cleanup_work_dir and self._work_dir.exists():
            import shutil
            await asyncio.to_thread(shutil.rmtree, self._work_dir)
        await self._model_client.close()
    
    async def pause(self) -> None:
        """暂停代理"""
        self.is_paused = True
        self._paused.set()
    
    async def resume(self) -> None:
        """恢复代理"""
        self.is_paused = False
        self._paused.clear()
    
    @property
    def produced_message_types(self) -> Sequence[type[BaseChatMessage]]:
        """获取代理产生的消息类型"""
        return (TextMessage,)
    
    async def on_messages(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> Response:
        """处理传入消息并返回单个响应"""
        response: Response | None = None
        async for message in self.on_messages_stream(messages, cancellation_token):
            if isinstance(message, Response):
                response = message
        assert response is not None
        return response
    
    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseAgentEvent | BaseChatMessage | Response, None]:
        """处理传入消息并产生响应流"""
        if self.is_paused:
            yield Response(
                chat_message=TextMessage(
                    content="ReportAgent 当前已暂停。",
                    source=self.name,
                    metadata={"internal": "yes"},
                )
            )
            return
        
        self._chat_history.extend(messages)
        inner_messages: List[BaseChatMessage] = []
        
        # 使用大模型分析任务需求
        task_analysis = await _analyze_task_requirements(
            self._chat_history, 
            self._model_client, 
            self._model_context, 
            cancellation_token
        )
        
        # 输出任务分析结果
        analysis_msg = TextMessage(
            source=self.name + "-analyzer",
            metadata={"internal": "no", "type": "task_analysis"},
            content=f"📊 **任务分析完成**\n\n"
                   f"- 报告类型：{OUTLINE_TEMPLATES.get(task_analysis.report_type, {}).get('name', '通用报告')}\n"
                   f"- 需要生成大纲：{'是' if task_analysis.need_outline else '否'}\n"
                   f"- 需要撰写章节：{'是' if task_analysis.need_chapter_writing else '否'}\n"
                   f"- 任务描述：{task_analysis.task_description[:100]}..."
        )
        inner_messages.append(analysis_msg)
        
        # 设置取消令牌
        report_generation_token = CancellationToken()
        cancellation_token.add_callback(lambda: report_generation_token.cancel())
        
        # 监控暂停事件
        async def monitor_pause() -> None:
            await self._paused.wait()
            report_generation_token.cancel()
        
        monitor_pause_task = asyncio.create_task(monitor_pause())
        
        system_prompt = self.system_prompt_template
        
        try:
            report_generated = False
            
            # 运行报告生成流程
            async for msg in _generate_report_with_review(
                system_prompt=system_prompt,
                thread=self._chat_history,
                agent_name=self.name,
                model_client=self._model_client,
                work_dir=self._work_dir,
                max_review_rounds=self._max_review_rounds,
                cancellation_token=report_generation_token,
                model_context=self._model_context,
                approval_guard=self._approval_guard,
                task_analysis=task_analysis,
            ):
                if isinstance(msg, bool):
                    report_generated = msg
                    break
                inner_messages.append(msg)
                self._chat_history.append(msg)
                yield msg
            
            # 生成最终响应
            if report_generated:
                combined_output = ""
                for txt_msg in inner_messages:
                    assert isinstance(txt_msg, TextMessage)
                    combined_output += f"{txt_msg.content}\n\n"
                
                final_response_msg = TextMessage(
                    source=self.name,
                    metadata={"internal": "yes"},
                    content=f"📄 **报告生成任务完成**\n\n{combined_output}" or "报告生成完成，但没有输出内容。",
                )
                
                yield Response(
                    chat_message=final_response_msg, inner_messages=inner_messages
                )
            else:
                yield Response(
                    chat_message=TextMessage(
                        content="报告生成未完成。",
                        source=self.name,
                        metadata={"internal": "yes"},
                    ),
                    inner_messages=inner_messages,
                )
                
        except ApprovalDeniedError:
            yield Response(
                chat_message=TextMessage(
                    content="用户未批准报告生成操作。",
                    source=self.name,
                    metadata={"internal": "no"},
                ),
                inner_messages=inner_messages,
            )
        except asyncio.CancelledError:
            yield Response(
                chat_message=TextMessage(
                    content="报告生成任务被用户取消。",
                    source=self.name,
                    metadata={"internal": "yes"},
                ),
                inner_messages=inner_messages,
            )
        except Exception as e:
            logger.error(f"ReportAgent 发生错误: {e}")
            self._chat_history.append(
                TextMessage(
                    content=f"报告生成过程中发生错误: {e}",
                    source=self.name,
                )
            )
            yield Response(
                chat_message=TextMessage(
                    content=f"ReportAgent 发生错误: {e}",
                    source=self.name,
                    metadata={"internal": "no"},
                ),
                inner_messages=inner_messages,
            )
        finally:
            try:
                monitor_pause_task.cancel()
                await monitor_pause_task
            except asyncio.CancelledError:
                pass
    
    async def on_reset(self, cancellation_token: CancellationToken) -> None:
        """重置聊天历史"""
        self._chat_history.clear()
        self._current_report = None
    
    def _to_config(self) -> ReportAgentConfig:
        """转换为配置对象"""
        return ReportAgentConfig(
            name=self.name,
            model_client=self._model_client.dump_component(),
            description=self.description,
            max_review_rounds=self._max_review_rounds,
            auto_save=self._auto_save,
        )
    
    @classmethod
    def _from_config(cls, config: ReportAgentConfig) -> Self:
        """从配置对象创建实例"""
        return cls(
            name=config.name,
            model_client=ChatCompletionClient.load_component(config.model_client),
            description=config.description,
            max_review_rounds=config.max_review_rounds,
            auto_save=config.auto_save,
        )
    
    async def save_state(self) -> Mapping[str, Any]:
        """保存状态"""
        return {
            "chat_history": [msg.dump() for msg in self._chat_history],
            "current_report": self._current_report,
        }
    
    async def load_state(self, state: Mapping[str, Any]) -> None:
        """加载状态"""
        message_factory = MessageFactory()
        for msg_data in state["chat_history"]:
            msg = message_factory.create(msg_data)
            assert isinstance(msg, BaseChatMessage)
            self._chat_history.append(msg)
        self._current_report = state.get("current_report") 