import json
import re
from typing import Any, AsyncGenerator, Dict, List, Mapping, Sequence, Union, cast
from typing_extensions import Self
from datetime import datetime
from pydantic import Field
from autogen_agentchat.base import Response
from autogen_agentchat.messages import BaseChatMessage, TextMessage, MultiModalMessage
from autogen_core import CancellationToken
from autogen_core.models import ChatCompletionClient, SystemMessage, UserMessage

from ._web_surfer import WebSurfer, WebSurferConfig, WebSurferState
from ...tools.playwright.browser import PlaywrightBrowser
from loguru import logger as trace_logger


class DeepSearchWebSurferConfig(WebSurferConfig):
    """深度搜索网页浏览器配置"""
    max_pages_per_search: int = 3  # 每次搜索最大页面数
    detailed_analysis: bool = True  # 是否进行详细分析
    save_search_history: bool = True  # 是否保存搜索历史
    research_mode: bool = True  # 研究模式，更注重信息收集
    # 新增提前结束机制配置
    enable_early_termination: bool = True  # 是否启用提前结束机制
    min_pages_before_check: int = 2  # 检查提前结束前最少访问的页面数
    satisfaction_threshold: float = 0.8  # 满足度阈值（0-1）
    check_interval: int = 2  # 每访问几个页面检查一次是否可以提前结束
    max_total_pages: int = 45  # 最大总页面数限制


class DeepSearchWebSurferState(WebSurferState):
    """深度搜索网页浏览器状态"""
    search_history: List[Dict[str, Any]] = Field(default_factory=list)
    collected_information: List[Dict[str, Any]] = Field(default_factory=list)
    search_depth: int = 0
    visited_urls: List[str] = Field(default_factory=list)  # 保存已访问的URLs
    search_queue: List[str] = Field(default_factory=list)  # 搜索关键词队列
    searched_keywords: List[str] = Field(default_factory=list)  # 已搜索的关键词列表
    total_pages_visited: int = 0  # 总访问页面数
    page_results: List[str] = Field(default_factory=list)  # 页面搜索结果
    type: str = Field(default="DeepSearchWebSurferState")


class DeepSearchWebSurfer(WebSurfer):
    """深度搜索网页浏览器
    
    专门用于进行深入研究搜索的智能代理。与普通WebSurfer相比，具有以下特点：
    1. 能够进行多层次的深度搜索
    2. 自动收集和整理详细的页面信息
    3. 支持多个搜索关键词的综合分析
    4. 提供更详细的搜索结果摘要
    5. 具有搜索历史记录和信息整合能力
    """
    
    component_type = "agent"
    component_config_schema = DeepSearchWebSurferConfig
    component_provider_override = "magentic_ui.agents.web_surfer.DeepSearchWebSurfer"
    
    DEFAULT_DESCRIPTION = """
    深度搜索网页浏览器是一个专门用于进行深入研究搜索的智能代理。
    它能够：
    - 进行多层次的深度搜索，挖掘更全面的信息
    - 自动访问多个相关页面并提取详细内容
    - 对搜索结果进行智能分析和整合
    - 支持复杂查询的分解和逐步解答
    
    该代理特别适合需要深入了解某个主题、进行市场调研、技术分析等场景。对某一主题进行深入的调查研究时，建议使用深度搜索。
    该代理不适合简单的信息查询和网页操作，例如：查询车票、机票信息。
    """
    
    DEEP_SEARCH_SYSTEM_MESSAGE = """
    您是一个专门用于深入研究搜索的智能助手。您的任务是针对用户的请求进行全面、深入的信息收集和分析。

    重要提示：除非用户特别要求其他语言，否则请用简体中文回复。

    您的核心能力：
    1. 深度搜索：不满足于表面信息，会深入挖掘相关主题
    2. 多角度分析：从不同角度和层面分析问题
    3. 信息整合：将多个来源的信息进行综合分析
    4. 结构化输出：提供清晰、有条理的研究结果

    搜索策略：
    - 使用多个相关关键词进行搜索
    - 访问权威网站和专业资源
    - 收集不同观点和数据
    - 验证信息的可靠性和时效性
    - 整理成结构化的研究报告

    当前日期：{date_today}
    """
    
    def __init__(
        self,
        name: str,
        model_client: ChatCompletionClient,
        browser: PlaywrightBrowser,
        max_pages_per_search: int = 5,
        detailed_analysis: bool = True,
        save_search_history: bool = True,
        research_mode: bool = True,
        # 新增提前结束机制参数
        enable_early_termination: bool = True,
        min_pages_before_check: int = 3,
        satisfaction_threshold: float = 0.8,
        check_interval: int = 2,
        # 新增最大页面数限制
        max_total_pages: int = 45,
        **kwargs: Any
    ) -> None:
        """初始化深度搜索网页浏览器"""
        super().__init__(name, model_client, browser, **kwargs)
        
        # 深度搜索特有配置
        self.max_pages_per_search = max_pages_per_search
        self.detailed_analysis = detailed_analysis
        self.save_search_history = save_search_history
        self.research_mode = research_mode
        
        # 提前结束机制配置
        self.enable_early_termination = enable_early_termination
        self.min_pages_before_check = min_pages_before_check
        self.satisfaction_threshold = satisfaction_threshold
        self.check_interval = check_interval
        # 新增最大页面数限制
        self.max_total_pages = max_total_pages
        
        # 搜索状态
        self.search_history: List[Dict[str, Any]] = []
        self.collected_information: List[Dict[str, Any]] = []
        self.current_search_depth = 0
        # 记录已访问的链接，避免重复访问
        self.visited_urls: set[str] = set()
        # 搜索关键词队列
        self.search_queue: List[str] = []
        # 已搜索的关键词列表
        self.searched_keywords: List[str] = []
        # 总访问页面数
        self.total_pages_visited: int = 0
        # 保存页面搜索结果用于最终输出
        self.page_results: List[str] = []
            
    async def on_messages_stream(
        self, messages: Sequence[BaseChatMessage], cancellation_token: CancellationToken
    ) -> AsyncGenerator[BaseChatMessage | Response, None]:
        """处理消息流，执行深度搜索"""
        
        # 重置搜索状态，开始新的搜索
        # self.visited_urls.clear()
        # self.collected_information.clear()
        # self.search_history.clear()
        self.search_queue.clear() # 清空队列
        self.searched_keywords.clear() # 清空已搜索关键词列表
        self.total_pages_visited = 0 # 重置总访问页面数
        self.page_results.clear() # 清空页面结果
        
        # 解析用户请求
        user_query = self._extract_user_query(messages)
        
        if not user_query:
            yield Response(
                chat_message=TextMessage(
                    content="请提供您需要深入研究的主题或问题。",
                    source=self.name,
                )
            )
            return
        
        # 开始深度搜索流程
        yield Response(
            chat_message=TextMessage(
                content=f"🔍 开始对「{user_query}」进行深度研究搜索...",
                source=self.name,
            )
        )
        
        try:
            # 执行深度搜索
            async for result in self._perform_deep_search(user_query, cancellation_token):
                yield result
            
            # # 生成最终报告
            # final_report = await self._generate_research_report(user_query)
            # yield Response(
            #     chat_message=TextMessage(
            #         content=final_report,
            #         source=self.name,
            #         metadata={"type": "research_report", "internal": "no"},
            #     )
            # )
            
        except Exception as e:
            trace_logger.error(f"深度搜索过程中发生错误: {e}")
            yield Response(
                chat_message=TextMessage(
                    content=f"深度搜索过程中遇到错误：{str(e)}",
                    source=self.name,
                )
            )
    
    def _extract_user_query(self, messages: Sequence[BaseChatMessage]) -> str:
        """提取用户查询"""
        if not messages:
            return ""
        
        last_message = messages[-1]
        if isinstance(last_message, TextMessage):
            return last_message.content
        elif isinstance(last_message, MultiModalMessage):
            # 提取文本内容
            text_content = ""
            for content in last_message.content:
                if isinstance(content, str):
                    text_content += content + " "
            return text_content.strip()
        
        return ""
    
    async def _perform_deep_search(
        self, query: str, cancellation_token: CancellationToken
    ) -> AsyncGenerator[Response, None]:
        """执行深度搜索 - 基于队列的动态搜索策略"""
        
        # 生成初始搜索关键词并加入队列
        initial_keywords = await self._generate_search_keywords(query)
        self.search_queue.extend(initial_keywords)
        
        yield Response(
            chat_message=TextMessage(
                content=f"📋 初始搜索队列：{', '.join(initial_keywords)}",
                source=self.name,
            )
        )
        
        # 处理搜索队列直到队列为空或达到最大页面数
        while self.search_queue and self.total_pages_visited < self.max_total_pages:
            if cancellation_token.is_cancelled():
                break
            
            # 从队列中取出下一个关键词
            current_keyword = self.search_queue.pop(0)
            
            # 添加到已搜索列表
            if current_keyword not in self.searched_keywords:
                self.searched_keywords.append(current_keyword)
            
            yield Response(
                chat_message=TextMessage(
                    content=f"🔎 正在搜索关键词：{current_keyword} (已访问: {self.total_pages_visited} 个页面)",
                    source=self.name,
                )
            )
            
            # 执行单个关键词搜索
            async for result in self._search_single_keyword(current_keyword, cancellation_token):
                yield result
                
                # 达到最大页面数时停止
                if self.total_pages_visited >= self.max_total_pages:
                    final_summary = "\n\n---\n\n".join(self.page_results)
                    yield Response(
                        chat_message=TextMessage(
                            content=f"深度搜索完成：已达到最大页面数限制 ({self.max_total_pages})。\n{final_summary}",
                            source=self.name,
                        )
                    )
                    return
            
            # 在单个关键词搜索完成后进行检查
            if self.total_pages_visited >= self.min_pages_before_check:
                if (self.total_pages_visited - self.min_pages_before_check) % self.check_interval == 0:
                    should_terminate, reason, missing_aspects = await self._check_early_termination_with_missing(query)
                    
                    if should_terminate:
                        # 直接拼接所有页面结果
                        final_summary = "\n\n---\n\n".join(self.page_results)
                        yield Response(
                            chat_message=TextMessage(
                                content=f"深度搜索完成：{reason}\n\n{final_summary}",
                                source=self.name,
                                metadata={"type": "final_report", "internal": "no"},
                            )
                        )
                        return
                    else:
                        # 根据missing_aspects生成新的搜索关键词
                        new_keywords = await self._generate_keywords_from_missing_aspects(
                            query, reason, missing_aspects
                        )
                        
                        if new_keywords:
                            # 过滤掉已经搜索过的关键词
                            filtered_keywords = [kw for kw in new_keywords if kw not in self.searched_keywords]
                            if filtered_keywords:
                                # 替换当前搜索队列
                                self.search_queue = filtered_keywords
                                yield Response(
                                    chat_message=TextMessage(
                                        content=f"📝 根据评估结果替换搜索队列：{', '.join(filtered_keywords)}",
                                        source=self.name,
                                    )
                                )
                            else:
                                yield Response(
                                    chat_message=TextMessage(
                                        content="📝 评估生成的关键词都已搜索过，继续当前队列",
                                        source=self.name,
                                    )
                                )
            
            # 如果搜索队列为空但未达到结束条件，提供状态更新
            if not self.search_queue and self.total_pages_visited < self.max_total_pages:
                yield Response(
                    chat_message=TextMessage(
                        content=f"📋 搜索队列已空，共访问 {self.total_pages_visited} 个页面",
                        source=self.name,
                    )
                )
        
        # 搜索结束
        if self.total_pages_visited >= self.max_total_pages:
            final_summary = "\n\n---\n\n".join(self.page_results)
            yield Response(
                chat_message=TextMessage(
                    content=f"深度搜索完成：已达到最大页面数限制 {final_summary}",
                    source=self.name,
                    metadata={"type": "final_report", "internal": "no"},
                )
            )
        else:
            final_summary = "\n\n---\n\n".join(self.page_results)
            yield Response(
                chat_message=TextMessage(
                    content=f"深度搜索完成：队列已空，{final_summary}",
                    source=self.name,
                    metadata={"type": "final_report", "internal": "no"},
                )
            )
    
    async def _generate_search_keywords(self, query: str) -> List[str]:
        """生成搜索关键词"""
        try:
            prompt = f"""
            基于以下查询，生成3个最核心的搜索关键词，用于深度研究：
            
            查询：{query}
            
            请生成最相关、最有价值的3个关键词，包括：
            1. 最直接相关的核心关键词
            2. 相关的重要概念或术语
            3. 能够补充第一个关键词的扩展词汇
            
            注意：
            - 只需要3个关键词，不要更多
            - 关键词应该具有互补性，覆盖不同角度
            - 避免过于相似的关键词
            
            请以JSON格式返回关键词列表：
            {{"keywords": ["关键词1", "关键词2", "关键词3"]}}
            """
            
            messages = [
                SystemMessage(content="你是一个专业的搜索策略专家。"),
                UserMessage(content=prompt, source=self.name)
            ]
            for message in messages:
                trace_logger.info(f"生成搜索关键词消息: {message.content}")
            response = await self._model_client.create(messages)
            trace_logger.info(f"生成搜索关键词响应: {response.content}")
            # 解析响应
            if isinstance(response.content, str):
                try:
                    # 解析响应，去除```json ```
                    content = response.content.replace("```json", "").replace("```", "").strip()
                    result = json.loads(content)
                    keywords = result.get("keywords", [query])
                    # 确保不超过3个关键词
                    return keywords[:3]
                except json.JSONDecodeError:
                    return [query]
            
            return [query]
            
        except Exception as e:
            trace_logger.error(f"生成搜索关键词失败: {e}")
            return [query]
    
    async def _check_early_termination_with_missing(self, original_query: str) -> tuple[bool, str, List[str]]:
        """检查是否可以提前结束搜索，并返回缺失方面
        
        Args:
            original_query: 原始查询
            
        Returns:
            tuple[bool, str, List[str]]: (是否应该结束, 结束原因, 缺失的方面列表)
        """
        try:
            if not self.collected_information:
                return False, "无收集信息", []
            
            # 准备已收集信息的摘要
            info_summaries: List[str] = []
            for info in self.collected_information:
                summary = info.get('summary', '')
                key_points = info.get('key_points', [])
                title = info.get('title', '未知')
                
                # 安全地处理key_points列表类型
                if not key_points:
                    key_points_list: List[str] = []
                elif isinstance(key_points, list):
                    # 显式转换每个元素为字符串
                    key_points_list = []
                    for item in key_points:  # type: ignore
                        if item is not None:
                            key_points_list.append(str(item))  # type: ignore
                else:
                    key_points_list = [str(key_points)]
                
                key_points_str = ', '.join(key_points_list)
                
                info_summaries.append(f"标题: {title}\n摘要: {summary}\n关键点: {key_points_str}")
            
            collected_info_text = "\n\n".join(info_summaries)
            
            # 使用LLM评估信息是否足够
            evaluation_prompt = f"""
            作为一个专业的研究分析师，请评估已收集的信息是否足以回答用户的原始查询。
            
            原始查询：{original_query}
            
            已收集信息（共{len(self.collected_information)}个页面）：
            {collected_info_text}
            
            请从以下几个维度评估信息的充分性：
            1. 信息覆盖度：是否涵盖了查询的主要方面
            2. 信息深度：是否提供了足够详细的信息
            3. 信息质量：信息是否可靠和权威
            4. 信息完整性：是否有明显的信息缺口
            5. 多样性：是否包含了不同角度的观点
            
            请以JSON格式返回评估结果：
            {{
                "sufficient": true/false,
                "confidence": 0.0-1.0,
                "coverage_score": 0.0-1.0,
                "depth_score": 0.0-1.0,
                "quality_score": 0.0-1.0,
                "completeness_score": 0.0-1.0,
                "diversity_score": 0.0-1.0,
                "overall_score": 0.0-1.0,
                "reason": "详细的评估理由",
                "missing_aspects": ["缺失的方面1", "缺失的方面2"]
            }}
            
            注意：
            - 如果overall_score >= {self.satisfaction_threshold}，则sufficient应为true
            - 请严格评估，不要过于宽松
            - 考虑用户查询的复杂性和深度要求
            - missing_aspects应该具体明确，便于生成新的搜索关键词
            """
            
            messages = [
                SystemMessage(content="你是一个专业的研究分析师，擅长评估信息的充分性和质量。"),
                UserMessage(content=evaluation_prompt, source=self.name)
            ]
            
            trace_logger.info(f"检查提前结束条件消息: {evaluation_prompt}")
            response = await self._model_client.create(messages)
            trace_logger.info(f"检查提前结束条件响应: {response.content}")
            
            if isinstance(response.content, str):
                try:
                    # 解析响应，去除```json ```
                    content = response.content.replace("```json", "").replace("```", "").strip()
                    evaluation = json.loads(content)
                    
                    sufficient = evaluation.get("sufficient", False)
                    overall_score = evaluation.get("overall_score", 0.0)
                    reason = evaluation.get("reason", "评估完成")
                    missing_aspects = evaluation.get("missing_aspects", [])
                    
                    # 记录评估结果
                    trace_logger.info(f"信息充分性评估 - 分数: {overall_score}, 是否充分: {sufficient}")
                    
                    if sufficient and overall_score >= self.satisfaction_threshold:
                        return True, f"信息已足够充分（评分: {overall_score:.2f}）。{reason}", missing_aspects
                    else:
                        return False, f"信息尚不充分（评分: {overall_score:.2f}）{reason}", missing_aspects
                        
                except json.JSONDecodeError:
                    trace_logger.error("解析评估结果JSON失败")
                    return False, "评估结果解析失败", []
            
            return False, "评估响应无效", []
            
        except Exception as e:
            trace_logger.error(f"检查提前结束条件失败: {e}")
            return False, f"评估过程出错: {str(e)}", []
    
    async def _generate_keywords_from_missing_aspects(
        self, original_query: str, evaluation_reason: str, missing_aspects: List[str]
    ) -> List[str]:
        """根据缺失的方面生成新的搜索关键词
        
        Args:
            original_query: 原始查询
            evaluation_reason: 评估理由
            missing_aspects: 缺失的方面列表
            
        Returns:
            List[str]: 新的搜索关键词列表
        """
        try:
            if not missing_aspects:
                return []
            
            missing_aspects_text = ', '.join(missing_aspects)
            
            prompt = f"""
            基于搜索评估结果，生成新的搜索关键词来补充缺失的信息：
            
            原始查询：{original_query}
            评估理由：{evaluation_reason}
            缺失的方面：{missing_aspects_text}
            历史搜索关键词：{', '.join(self.searched_keywords)}
            
            请针对这些缺失的方面，生成2-3个新的搜索关键词。要求：
            1. 直接针对缺失的方面
            2. 具体而有针对性
            3. 能够找到互补的信息
            4. 避免与之前的搜索关键词重复
            
            请以JSON格式返回关键词列表：
            {{"keywords": ["针对性关键词1", "针对性关键词2", "针对性关键词3"]}}
            """
            
            messages = [
                SystemMessage(content="你是一个专业的搜索策略专家，擅长根据信息缺口生成针对性的搜索关键词。"),
                UserMessage(content=prompt, source=self.name)
            ]
            
            trace_logger.info(f"生成新关键词输入: {prompt}")
            response = await self._model_client.create(messages)
            trace_logger.info(f"生成新关键词响应: {response.content}")
            
            if isinstance(response.content, str):
                try:
                    # 解析响应，去除```json ```
                    content = response.content.replace("```json", "").replace("```", "").strip()
                    result = json.loads(content)
                    new_keywords = result.get("keywords", [])
                    # 限制关键词数量，最多3个
                    return new_keywords[:3]
                except json.JSONDecodeError:
                    trace_logger.error("解析新关键词JSON失败")
                    return []
            
            return []
            
        except Exception as e:
            trace_logger.error(f"根据缺失方面生成关键词失败: {e}")
            return []
    
    async def _search_single_keyword(
        self, keyword: str, cancellation_token: CancellationToken
    ) -> AsyncGenerator[Response, None]:
        """搜索单个关键词"""
        
        try:
            # 直接调用web搜索方法更新页面状态
            search_result = await self._perform_web_search(keyword)
            
            yield Response(
                chat_message=TextMessage(
                    content=f"🔎 已搜索关键词「{keyword}」: {search_result}",
                    source=self.name,
                )
            )
            
            async for result in self._extract_and_visit_links_with_output(cancellation_token):
                yield result
                        
        except Exception as e:
            trace_logger.error(f"搜索关键词 '{keyword}' 时发生错误: {e}")
            yield Response(
                chat_message=TextMessage(
                    content=f"搜索关键词 '{keyword}' 时遇到错误：{str(e)}",
                    source=self.name,
                )
            )
    
    async def _perform_web_search(self, query: str) -> str:
        """执行web搜索并更新页面状态"""
        # 确保浏览器已初始化
        if not self.did_lazy_init:
            await self.lazy_init()
        
        # 直接调用web搜索工具
        search_args = {"query": query}
        result = await self._execute_tool_web_search(search_args)
        
        return result
    
    async def _extract_and_visit_links_with_output(self, cancellation_token: CancellationToken) -> AsyncGenerator[Response, None]:
        """提取并访问相关链接，同时输出格式化结果"""
        if not self._page:
            return
        
        try:
            trace_logger.info(f"页面信息：{self._page.url}")
            
            # 检查是否是Bing搜索结果页面
            current_url = self._page.url
            if "bing.com/search" in current_url:
                # 专门针对Bing搜索结果页面提取链接
                links = await self._page.evaluate(r"""
                    () => {
                        // 查找搜索结果链接 - Bing的搜索结果通常在特定的选择器中
                        const resultSelectors = [
                            'h2 a[href]',  // 标题链接
                            '.b_algo h2 a[href]',  // 标准搜索结果
                            '.b_title a[href]',  // 标题链接
                            '[data-onclick] a[href]',  // 带点击事件的链接
                            '.b_entityTP a[href]',  // 实体卡片链接
                            '.b_rich a[href]'  // 富媒体结果链接
                        ];
                        
                        const links = [];
                        
                        for (const selector of resultSelectors) {
                            const elements = Array.from(document.querySelectorAll(selector));
                            for (const element of elements) {
                                const href = element.href;
                                const text = element.textContent.trim();
                                const title = element.title || text;
                                
                                // 过滤掉无效链接
                                if (href && 
                                    href.startsWith('http') && 
                                    !href.includes('bing.com') &&  // 排除Bing自身链接
                                    !href.includes('microsoft.com') && // 排除微软链接
                                    text.length > 0 && 
                                    text.length < 200 &&
                                    !text.toLowerCase().includes('skip') &&
                                    !text.toLowerCase().includes('privacy') &&
                                    !text.toLowerCase().includes('terms')) {
                                    
                                    links.push({
                                        href: href,
                                        text: text,
                                        title: title
                                    });
                                }
                            }
                        }
                        
                        // 去重并限制数量
                        const uniqueLinks = [];
                        const seenUrls = new Set();
                        
                        for (const link of links) {
                            // 清理URL，去除片段标识符和查询参数
                            const cleanUrl = link.href.split('#')[0].split('?')[0].replace(/\/$/, '');
                            
                            if (!seenUrls.has(cleanUrl) && uniqueLinks.length < 10) {
                                seenUrls.add(cleanUrl);
                                uniqueLinks.push({
                                    href: link.href,
                                    text: link.text,
                                    title: link.title,
                                    cleanUrl: cleanUrl  // 添加清理后的URL用于后续判断
                                });
                            }
                        }
                        
                        return uniqueLinks;
                    }
                """)
            else:
                # 对于非搜索页面，使用通用的链接提取
                links = await self._page.evaluate("""
                    () => {
                        const links = Array.from(document.querySelectorAll('a[href]'));
                        return links.slice(0, 10).map(link => ({
                            href: link.href,
                            text: link.textContent.trim(),
                            title: link.title || link.textContent.trim()
                        })).filter(link => 
                            link.href.startsWith('http') && 
                            link.text.length > 0 && 
                            link.text.length < 100
                        );
                    }
                """)
            
            trace_logger.info(f"提取到 {len(links)} 个搜索结果链接: {[link['href'] for link in links]}")
            
            if not links:
                yield Response(
                    chat_message=TextMessage(
                        content="⚠️ 未找到可访问的搜索结果链接",
                        source=self.name,
                    )
                )
                return
            
            # 在遍历前过滤掉已经访问过的URL
            unvisited_links: List[Dict[str, str]] = []
            for link in links:
                # 清理URL，去除片段标识符和查询参数中的无关部分
                clean_url = link['href'].split('#')[0].split('?')[0]
                if clean_url.endswith('/'):
                    clean_url = clean_url[:-1]
                
                # 检查是否已经访问过这个URL
                if clean_url not in self.visited_urls:
                    unvisited_links.append({
                        'href': link['href'],
                        'text': link.get('text', ''),
                        'title': link.get('title', ''),
                        'clean_url': clean_url
                    })
                    # 标记为已访问
                    self.visited_urls.add(clean_url)
                else:
                    trace_logger.info(f"跳过已访问的URL: {clean_url}")
            
            if not unvisited_links:
                yield Response(
                    chat_message=TextMessage(
                        content="⚠️ 所有搜索结果链接都已访问过，跳过",
                        source=self.name,
                    )
                )
                return
            
            trace_logger.info(f"过滤后剩余 {len(unvisited_links)} 个未访问链接")
            
            # 访问前几个未访问的链接
            for i, link in enumerate(unvisited_links[:self.max_pages_per_search]):  # 限制访问前3个链接
                if cancellation_token.is_cancelled():
                    break
                try:
                    yield Response(
                        chat_message=TextMessage(
                            content=f"📄 正在访问搜索结果 {i+1}: {link['title'][:50]}...",
                            source=self.name,
                        )
                    )
                    async for result in self._visit_and_analyze_page_with_output(link['href'], link['title'], cancellation_token):
                        yield result
                except Exception as e:
                    trace_logger.error(f"访问链接失败: {e}")
                    yield Response(
                        chat_message=TextMessage(
                            content=f"❌ 访问链接失败: {link['href'][:50]}...",
                            source=self.name,
                        )
                    )
                    continue
                    
        except Exception as e:
            trace_logger.error(f"提取链接失败: {e}")
            yield Response(
                chat_message=TextMessage(
                    content=f"❌ 提取搜索结果链接时出错: {str(e)}",
                    source=self.name,
                )
            )
    
    async def _visit_and_analyze_page_with_output(self, url: str, title: str, cancellation_token: CancellationToken) -> AsyncGenerator[Response, None]:
        """访问并分析页面，同时输出格式化结果"""
        if not self._page:
            return
        
        try:
            # 检查URL是否被允许
            _, approved = await self._check_url_and_generate_msg(url)
            if not approved:
                return
            
            # 访问页面
            await self._playwright_controller.visit_page(self._page, url)
            
            # 等待页面加载
            await self._page.wait_for_load_state("domcontentloaded")
            
            # 增加页面访问计数
            self.total_pages_visited += 1
            
            # 提取页面信息
            page_info = await self._extract_detailed_page_info()
            # url处理，去除掉#:~:text=高亮符号后的text
            page_info['url'] = url.split('#:~:text=')[0]
            page_info['title'] = title
            
            trace_logger.info(f"提取页面信息: {page_info}")
            
            # 添加到收集的信息中
            self.collected_information.append(page_info)
            
            
            # TODO 此处输出的结果要保存，输出格式化的搜索结果
            formatted_output = await self._format_search_result(page_info)
            self.page_results.append(formatted_output)
            yield Response(
                chat_message=TextMessage(
                    content=formatted_output,
                    source=self.name,
                    metadata={"type": "search_result", "url": url, "internal": "no"},
                )
            )
            
            # 记录搜索历史
            if self.save_search_history:
                self.search_history.append({
                    'action': 'visit_page',
                    'url': url,
                    'title': title,
                    'timestamp': datetime.now().isoformat(),
                    'info_collected': len(page_info.get('key_points', []))
                })
            
        except Exception as e:
            trace_logger.error(f"访问和分析页面失败: {e}")
            yield Response(
                chat_message=TextMessage(
                    content=f"访问页面 {url} 时遇到错误：{str(e)}",
                    source=self.name,
                )
            )
    
    async def _format_search_result(self, page_info: Dict[str, Any]) -> str:
        """格式化搜索结果"""
        try:
            url = page_info.get('url', '未知')
            markdown_summary = page_info.get('markdown_summary', '无内容总结')
            title = page_info.get('title', '未知')
            
            # 构建输出格式
            formatted_output = f"""URL: {url}\n标题: {title}\n内容总结:\n{markdown_summary}"""
            
            return formatted_output
            
        except Exception as e:
            trace_logger.error(f"格式化搜索结果失败: {e}")
            return f"格式化结果时出错：{str(e)}"
    
    async def _extract_detailed_page_info(self) -> Dict[str, Any]:
        """提取详细的页面信息"""
        if not self._page:
            return {}
        
        try:
            # 获取页面内容
            page_content = await self._playwright_controller.get_page_markdown(self._page)
            page_title = await self._page.title()
            
            # 去除超链接，保留链接文本
            # 匹配 [文本](链接) 格式的超链接
            page_content = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', page_content)
            # 匹配 <链接> 格式的裸链接
            page_content = re.sub(r'<[^>]*>', '', page_content)
            # 匹配 http/https 开头的裸链接
            page_content = re.sub(r'https?://[^\s\]]+', '', page_content)
            
            # 限制内容长度
            if len(page_content) > 3000:
                page_content = page_content[:3000] + "..."
            
            # 使用LLM分析页面内容并生成Markdown格式的总结
            analysis_prompt = f"""
            请分析以下网页内容，并生成一个结构化的Markdown格式内容总结：
            
            页面标题：{page_title}
            页面内容：
            {page_content}
            
            请提供以下信息的JSON格式：
            {{
                "summary": "页面内容简要摘要（100字以内）",
                "markdown_summary": "详细的Markdown格式内容总结，包含主要章节、关键点和重要信息",
                "key_points": ["关键点1", "关键点2", "关键点3"],
                "important_data": ["重要数据1", "重要数据2"],
                "relevant_topics": ["相关主题1", "相关主题2"],
                "credibility": "信息可信度评估"
            }}
            
            markdown_summary字段要求：
            1. 使用标准Markdown格式
            2. 包含适当的标题层级（##、###等）
            3. 使用列表、粗体、斜体等格式化元素
            4. 结构清晰，易于阅读
            """
            
            messages = [
                SystemMessage(content="你是一个专业的内容分析师，擅长生成结构化的Markdown格式总结。"),
                UserMessage(content=analysis_prompt, source=self.name)
            ]
            trace_logger.info(f"分析页面内容输入: {messages}")
            response = await self._model_client.create(messages)
            trace_logger.info(f"分析页面内容结果: {response}")
            if isinstance(response.content, str):
                try:
                    # 解析响应，去除```json ```
                    content = response.content.replace("```json", "").replace("```", "").strip()
                    analysis_result = json.loads(content)
                    return analysis_result
                except json.JSONDecodeError:
                    # 如果JSON解析失败，返回基本信息
                    return {
                        "summary": page_content[:200] + "...",
                        "markdown_summary": f"## {page_title}\n\n{page_content}...",
                        "key_points": [],
                        "important_data": [],
                        "relevant_topics": [],
                        "credibility": "未评估"
                    }
            
            return {}
            
        except Exception as e:
            trace_logger.error(f"提取页面信息失败: {e}")
            return {}
    
     
            
    
    def _to_config(self) -> DeepSearchWebSurferConfig:
        """转换为配置对象"""
        base_config = super()._to_config()
        return DeepSearchWebSurferConfig(
            **base_config.model_dump(),
            max_pages_per_search=self.max_pages_per_search,
            detailed_analysis=self.detailed_analysis,
            save_search_history=self.save_search_history,
            research_mode=self.research_mode,
            enable_early_termination=self.enable_early_termination,
            min_pages_before_check=self.min_pages_before_check,
            satisfaction_threshold=self.satisfaction_threshold,
            check_interval=self.check_interval,
            max_total_pages=self.max_total_pages,
        )
    
    @classmethod
    def _from_config(cls, config: Union[WebSurferConfig, DeepSearchWebSurferConfig]) -> Self:
        """从配置创建实例"""
        if isinstance(config, DeepSearchWebSurferConfig):
            return cls(
                name=config.name,
                model_client=ChatCompletionClient.load_component(config.model_client),
                browser=PlaywrightBrowser.load_component(config.browser),
                model_context_token_limit=config.model_context_token_limit,
                downloads_folder=config.downloads_folder,
                description=config.description or cls.DEFAULT_DESCRIPTION,
                debug_dir=config.debug_dir,
                start_page=config.start_page or cls.DEFAULT_START_PAGE,
                animate_actions=config.animate_actions,
                to_save_screenshots=config.to_save_screenshots,
                max_actions_per_step=config.max_actions_per_step,
                to_resize_viewport=config.to_resize_viewport,
                url_statuses=config.url_statuses,
                url_block_list=config.url_block_list,
                single_tab_mode=config.single_tab_mode,
                json_model_output=config.json_model_output,
                multiple_tools_per_call=config.multiple_tools_per_call,
                viewport_height=config.viewport_height,
                viewport_width=config.viewport_width,
                use_action_guard=config.use_action_guard,
                max_pages_per_search=config.max_pages_per_search,
                detailed_analysis=config.detailed_analysis,
                save_search_history=config.save_search_history,
                research_mode=config.research_mode,
                enable_early_termination=config.enable_early_termination,
                min_pages_before_check=config.min_pages_before_check,
                satisfaction_threshold=config.satisfaction_threshold,
                check_interval=config.check_interval,
                max_total_pages=config.max_total_pages,
            )
        else:
            # 如果是基础配置，使用默认的深度搜索参数
            return cls(
                name=config.name,
                model_client=ChatCompletionClient.load_component(config.model_client),
                browser=PlaywrightBrowser.load_component(config.browser),
                model_context_token_limit=config.model_context_token_limit,
                downloads_folder=config.downloads_folder,
                description=config.description or cls.DEFAULT_DESCRIPTION,
                debug_dir=config.debug_dir,
                start_page=config.start_page or cls.DEFAULT_START_PAGE,
                animate_actions=config.animate_actions,
                to_save_screenshots=config.to_save_screenshots,
                max_actions_per_step=config.max_actions_per_step,
                to_resize_viewport=config.to_resize_viewport,
                url_statuses=config.url_statuses,
                url_block_list=config.url_block_list,
                single_tab_mode=config.single_tab_mode,
                json_model_output=config.json_model_output,
                multiple_tools_per_call=config.multiple_tools_per_call,
                viewport_height=config.viewport_height,
                viewport_width=config.viewport_width,
                use_action_guard=config.use_action_guard,
            )
    
    @classmethod
    def from_config(cls, config: Union[WebSurferConfig, DeepSearchWebSurferConfig]) -> Self:
        """从配置创建实例"""
        return cls._from_config(config)
    
    async def save_state(self) -> Dict[str, Any]:
        """保存状态"""
        base_state = await super().save_state()
        
        deep_search_state = DeepSearchWebSurferState(
            **base_state,
            search_history=self.search_history,
            collected_information=self.collected_information,
            search_depth=self.current_search_depth,
            visited_urls=list(self.visited_urls),  # 转换为列表保存
            search_queue=self.search_queue, # 保存队列
            searched_keywords=self.searched_keywords, # 保存已搜索关键词列表
            total_pages_visited=self.total_pages_visited, # 保存总访问页面数
            page_results=self.page_results, # 保存页面搜索结果
        )
        
        return deep_search_state.model_dump()
    
    async def load_state(self, state: Mapping[str, Any]) -> None:
        """加载状态"""
        await super().load_state(state)
        
        deep_search_state = DeepSearchWebSurferState.model_validate(state)
        self.search_history = deep_search_state.search_history
        self.collected_information = deep_search_state.collected_information
        self.current_search_depth = deep_search_state.search_depth
        self.visited_urls = set(deep_search_state.visited_urls)  # 转换为集合 
        self.search_queue = deep_search_state.search_queue # 加载队列 
        self.searched_keywords = deep_search_state.searched_keywords # 加载已搜索关键词列表 
        self.total_pages_visited = deep_search_state.total_pages_visited # 加载总访问页面数 
        self.page_results = deep_search_state.page_results # 加载页面搜索结果 