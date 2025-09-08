from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import logging
import asyncio
import json
import re
import time
import random
from datetime import datetime

from app.models.database import DiscussionGroup, Role
from app.adapters.meeting_adapter import MeetingAdapter
from app.meeting.utils.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)

class DiscussionProcessor:
    """讨论组处理器，用于管理讨论组数据"""
    
    def __init__(self, db: Session):
        self.db = db
        self.adapter = None  # 保留adapter引用以便兼容过渡
        self.group_id = None
        self.current_meeting_id = None  # 添加一个属性来跟踪当前会议ID
        self.active_meetings = {}  # 自己管理活跃会议
    
    def start_meeting(self, group_id: int, topic: str = None) -> str:
        """启动一个新的讨论会议"""
        if self.adapter:
            # 如果存在adapter，使用它启动会议（兼容现有代码）
            self.group_id = group_id
            
            # 如果没有提供主题，使用默认主题
            if not topic or topic.strip() == "":
                group = self._load_group(group_id)
                topic = group.topic if group.topic else f"讨论组{group_id}的新讨论"
            
            # 启动会议并返回会议ID
            logger.info(f"通过adapter启动讨论: group_id={group_id}, topic={topic}")
            meeting_id = self.adapter.start_meeting(group_id, topic)
            self.current_meeting_id = meeting_id  # 保存当前会议ID
            
            # 将会议数据也存入自己的管理字典，以便过渡
            if meeting_id not in self.active_meetings and meeting_id in self.adapter.active_meetings:
                self.active_meetings[meeting_id] = self.adapter.active_meetings[meeting_id]
            
            return meeting_id
        else:
            # TODO: 实现不依赖adapter的会议启动逻辑

            raise NotImplementedError("尚未实现无adapter的会议启动功能")
    
    def get_groups(self) -> List[Dict[str, Any]]:
        """获取所有讨论组"""
        groups = self.db.query(DiscussionGroup).all()
        return [self._group_to_dict(group) for group in groups]
    
    def get_group(self, group_id: int) -> Optional[Dict[str, Any]]:
        """获取特定讨论组"""
        group = self.db.query(DiscussionGroup).filter(DiscussionGroup.id == group_id).first()
        if not group:
            return None
        return self._group_to_dict(group)
    
    def create_group(self, group_data: Dict[str, Any]) -> Dict[str, Any]:
        """创建新讨论组"""
        # 获取角色ID列表
        role_ids = group_data.get('role_ids', [])
        
        # 创建讨论组
        group = DiscussionGroup(
            name=group_data.get('name'),
            topic=group_data.get('topic', ''),
            description=group_data.get('description', ''),
            mode=group_data.get('mode', 'discussion'),
            max_rounds=group_data.get('max_rounds', 3),
            summary_model_id=group_data.get('summary_model_id'),
            summary_prompt=group_data.get('summary_prompt')
        )
        
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        
        # 添加角色关联
        if role_ids:
            roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            for role in roles:
                group.roles.append(role)
            
            self.db.commit()
            self.db.refresh(group)
        
        return self._group_to_dict(group)
    
    def update_group(self, group_id: int, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """更新讨论组"""
        group = self.db.query(DiscussionGroup).filter(DiscussionGroup.id == group_id).first()
        if not group:
            return None
        
        # 更新讨论组属性
        if 'name' in group_data:
            group.name = group_data['name']
        if 'topic' in group_data:
            group.topic = group_data['topic']
        if 'description' in group_data:
            group.description = group_data['description']
        if 'mode' in group_data:
            group.mode = group_data['mode']
        if 'max_rounds' in group_data:
            group.max_rounds = group_data['max_rounds']
        if 'summary_model_id' in group_data:
            group.summary_model_id = group_data['summary_model_id']
        if 'summary_prompt' in group_data:
            group.summary_prompt = group_data['summary_prompt']
        if 'custom_speaking_order' in group_data:
            group.custom_speaking_order = group_data['custom_speaking_order']
        
        # 更新角色关联
        if 'role_ids' in group_data:
            # 清除现有角色
            group.roles = []
            
            # 添加新角色
            role_ids = group_data['role_ids']
            roles = self.db.query(Role).filter(Role.id.in_(role_ids)).all()
            for role in roles:
                group.roles.append(role)
        
        self.db.commit()
        self.db.refresh(group)
        
        return self._group_to_dict(group)
    
    def delete_group(self, group_id: int) -> bool:
        """删除讨论组"""
        group = self.db.query(DiscussionGroup).filter(DiscussionGroup.id == group_id).first()
        if not group:
            return False
        
        # 清除角色关联
        group.roles = []
        
        self.db.delete(group)
        self.db.commit()
        
        return True
    
    def _group_to_dict(self, group: DiscussionGroup) -> Dict[str, Any]:
        """将讨论组对象转换为字典"""
        return {
            "id": group.id,
            "name": group.name,
            "topic": group.topic or "",
            "description": group.description or "",
            "mode": group.mode,
            "max_rounds": group.max_rounds,
            "summary_model_id": group.summary_model_id,
            "summary_prompt": group.summary_prompt or "",
            "custom_speaking_order": group.custom_speaking_order,
            "created_at": group.created_at.isoformat() if group.created_at else None,
            "updated_at": group.updated_at.isoformat() if group.updated_at else None,
            "roles": [
                {
                    "id": role.id,
                    "name": role.name
                }
                for role in group.roles
            ],
            "role_ids": [role.id for role in group.roles]
        }
    
    def _load_group(self, group_id: int) -> DiscussionGroup:
        """加载讨论组信息"""
        group = self.db.query(DiscussionGroup).filter(DiscussionGroup.id == group_id).first()
        if not group:
            raise ValueError(f"讨论组ID {group_id} 不存在")
        return group
    
    async def process_request(self, prompt: str, stream: bool = False, meeting_id: str = None) -> Any:
        """处理请求"""
        try:
            logger.info(f"开始处理讨论组请求: group_id={self.group_id}, prompt='{prompt[:50]}...'")
            
            # 确保self.group_id和self.adapter存在
            if not hasattr(self, 'group_id') or not hasattr(self, 'adapter'):
                logger.error("未设置group_id或adapter")
                raise ValueError("未设置group_id或adapter")
            
            # 使用传入的会议ID或当前已有的会议ID，如果都没有才启动新会议
            if meeting_id:
                # 使用传入的会议ID
                self.current_meeting_id = meeting_id
                logger.info(f"使用传入的会议ID: meeting_id={meeting_id}")
            elif self.current_meeting_id:
                # 使用当前已存在的会议ID
                meeting_id = self.current_meeting_id
                logger.info(f"使用当前会议ID: meeting_id={meeting_id}")
            else:
                # 如果没有会议ID，才启动新会议
                logger.info(f"开始启动讨论: group_id={self.group_id}")
                meeting_id = self.start_meeting(self.group_id, prompt)
                logger.info(f"讨论已启动: meeting_id={meeting_id}")
            
            if stream:
                # 流式处理模式 - 使用返回能够迭代的生成器
                logger.info("使用流式响应模式")
                return self._get_stream_response(meeting_id)
            else:
                # 非流式模式 - 等待全部完成后一次性返回
                logger.info("使用非流式响应模式")
                return await self._complete_discussion_process(meeting_id)
        except Exception as e:
            logger.error(f"处理讨论组请求失败: {str(e)}", exc_info=True)
            raise
    
    def _get_stream_response(self, meeting_id: str):
        """
        返回适用于StreamingResponse的生成器
        这是一个同步方法，返回一个可以迭代的生成器
        """
        # 非异步函数中返回一个同步生成器
        async def process_meeting():
            # 内部处理会议并生成数据
            generator = self._stream_discussion_process(meeting_id)
            async for chunk in generator:
                yield chunk
        
        # 创建一个类似于生成器的对象，但它能被FastAPI的StreamingResponse正确处理
        class AsyncIteratorWrapper:
            def __init__(self, coro):
                self.coro = coro
                self._iterator = None
            
            def __aiter__(self):
                return self
            
            async def __anext__(self):
                if self._iterator is None:
                    self._iterator = self.coro.__aiter__()
                try:
                    return await self._iterator.__anext__()
                except StopAsyncIteration:
                    raise
        
        # 返回一个可迭代对象
        return AsyncIteratorWrapper(process_meeting())
    
    async def _complete_discussion_process(self, meeting_id: str) -> str:
        """完整讨论过程，一次性返回结果"""
        round_count = 0
        # 进行讨论直到结束
        while True:
            logger.info(f"开始执行第{round_count+1}轮讨论: meeting_id={meeting_id}")
            round_data = self.adapter.conduct_discussion_round(meeting_id)
            logger.info(f"第{round_count+1}轮讨论完成: {round_data}")
            
            # 每轮结束后打印当前轮次的对话内容
            self._print_latest_round_content(meeting_id)
            
            round_count += 1
            if round_data["status"] == "已结束":
                logger.info(f"讨论已结束: meeting_id={meeting_id}")
                break
            
            logger.info(f"等待下一轮讨论...")
            await asyncio.sleep(0.5)
        
        # 结束讨论并获取结果
        logger.info(f"获取讨论结果: meeting_id={meeting_id}")
        result = await self.adapter.end_meeting(meeting_id)
        
        # 打印完整的讨论历史和总结
        self._print_full_discussion(result)
        
        logger.info(f"获取到讨论结果: summary_length={len(result.get('summary', ''))}")
        return result["summary"] or "讨论已完成，但未生成总结。"
    
    async def _stream_discussion_process(self, meeting_id: str):
        """流式讨论过程，实时返回每个角色的回答"""
        import time
        import json
        import asyncio
        import random
        from datetime import datetime
        
        conversation_id = f"chatcmpl-{int(time.time())}"
        last_processed_message_index = -1
        round_count = 0  # 这是用于前端显示的轮次计数
        
        # 获取会议对象
        meeting_data = self.adapter.active_meetings.get(meeting_id)
        if not meeting_data:
            yield f"data: {{\"error\": \"会议ID {meeting_id} 不存在\"}}\n\n"
            return
        
        # 从会议数据中获取实际的会议对象
        meeting = meeting_data.get("meeting")
        if not meeting:
            yield f"data: {{\"error\": \"会议数据格式错误\"}}\n\n"
            return
        
        # 打印会议状态和历史内容
        print(f"\n{'='*80}")
        print(f"会议ID: {meeting_id}")
        print(f"主题: {meeting.topic}")
        print(f"状态: {meeting.status}")
        print(f"当前轮次: {meeting.current_round}")
        print(f"最大轮次: {meeting.max_rounds}")
        print(f"当前历史消息数: {len(meeting.meeting_history)}")
        print(f"{'='*80}\n")
            
        # 检查会议状态，如果已结束则获取总结并返回
        if meeting.status == "已结束":
            # 发送会话开始事件 (确保前端能正确识别)
            start_event = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(start_event, ensure_ascii=False)}\n\n"
            
            # 发送会议结束信息
            end_meeting_info = {
                "id": f"{conversation_id}-meeting-end",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"content": "\n\n## 会议结束\n\n*正在生成会议总结*\n\n"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(end_meeting_info, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.5)
            
            # 使用流式总结生成器实时生成并发送总结
            # 获取会议主题和历史
            meeting_topic = meeting.topic
            meeting_history = meeting.meeting_history
            
            # 获取讨论组信息和总结模型配置
            custom_prompt = None
            model_name = None
            api_key = None
            api_base_url = None
            
            # 从会议对象获取讨论组信息
            group_info = getattr(meeting, 'group_info', None)
            
            if group_info:
                # 获取自定义提示模板（如果有）
                if 'summary_prompt' in group_info and group_info['summary_prompt']:
                    custom_prompt = group_info['summary_prompt']
                    logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                
                # 获取自定义总结模型（如果有）
                if 'summary_model_id' in group_info and group_info['summary_model_id']:
                    model_id = group_info['summary_model_id']
                    logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                    
                    try:
                        # 获取模型信息
                        from app.models.database import get_db, Model
                        
                        # 获取数据库会话
                        db = next(get_db())
                        
                        # 查询模型配置
                        summary_model = db.query(Model).filter(Model.id == model_id).first()
                        
                        if summary_model:
                            logger.info(f"找到总结模型: {summary_model.name}")
                            model_name = summary_model.name
                            
                            # 获取API密钥和基础URL
                            api_key = getattr(summary_model, 'api_key', None)
                            api_url = getattr(summary_model, 'api_url', None)
                            
                            # 处理URL，从完整URL中提取基础部分
                            if api_url:
                                if "/v1/chat/completions" in api_url:
                                    api_base_url = api_url.split("/v1/chat/completions")[0]
                                else:
                                    api_base_url = api_url
                    except Exception as e:
                        logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
            
            # 使用模式的默认提示模板或自定义提示
            prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
            
            # 先发送总结标题
            summary_title_event = {
                "id": f"{conversation_id}-meeting-summary-title",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"content": "\n## 会议总结\n\n"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(summary_title_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)
            
            # 使用流式总结生成器实时生成并发送总结
            logger.info(f"开始直接流式生成和发送会议总结")
            
            # 获取会议主题和历史
            meeting_topic = meeting.topic
            meeting_history = meeting.meeting_history
            
            # 获取讨论组信息和总结模型配置
            custom_prompt = None
            model_name = None
            api_key = None
            api_base_url = None
            
            # 从会议对象获取讨论组信息
            group_info = getattr(meeting, 'group_info', None)
            
            if group_info:
                # 获取自定义提示模板（如果有）
                if 'summary_prompt' in group_info and group_info['summary_prompt']:
                    custom_prompt = group_info['summary_prompt']
                    logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                
                # 获取自定义总结模型（如果有）
                if 'summary_model_id' in group_info and group_info['summary_model_id']:
                    model_id = group_info['summary_model_id']
                    logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                    
                    try:
                        # 获取模型信息
                        from app.models.database import get_db, Model
                        
                        # 获取数据库会话
                        db = next(get_db())
                        
                        # 查询模型配置
                        summary_model = db.query(Model).filter(Model.id == model_id).first()
                        
                        if summary_model:
                            logger.info(f"找到总结模型: {summary_model.name}")
                            model_name = summary_model.name
                            
                            # 获取API密钥和基础URL
                            api_key = getattr(summary_model, 'api_key', None)
                            api_url = getattr(summary_model, 'api_url', None)
                            
                            # 处理URL，从完整URL中提取基础部分
                            if api_url:
                                if "/v1/chat/completions" in api_url:
                                    api_base_url = api_url.split("/v1/chat/completions")[0]
                                else:
                                    api_base_url = api_url
                    except Exception as e:
                        logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
            
            # 使用模式的默认提示模板或自定义提示
            prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
            
            # 开始流式生成总结
            accumulated_summary = ""
            async for chunk in SummaryGenerator.generate_summary_stream(
                meeting_topic=meeting_topic,
                meeting_history=meeting_history,
                prompt_template=prompt_template,
                model_name=model_name,
                api_key=api_key,
                api_base_url=api_base_url
            ):
                accumulated_summary += chunk
                summary_chunk_event = {
                    "id": f"{conversation_id}-summary-chunk-{int(time.time()*1000)}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(summary_chunk_event, ensure_ascii=False)}\n\n"
            
            # 将累积的总结保存到会议历史
            meeting.add_message("system", accumulated_summary)
            
            # 发送完成事件
            summary_end_event = {
                "id": f"{conversation_id}-summary-end",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"content": ""},
                    "finish_reason": "stop"
                }]
            }
            yield f"data: {json.dumps(summary_end_event, ensure_ascii=False)}\n\n"
            
            logger.info(f"总结内容已通过流式方式实时生成和发送完毕，总长度: {len(accumulated_summary)}")
            print("会议结束，已实时生成并流式发送总结")
            
            # 发送结束标志
            yield f"data: [DONE]\n\n"
            return
            
        # 检查是否是继续处理（在人类输入后）
        is_continuation = False
        last_human_agent = None
        last_human_name = None
        last_human_position = -1
        
        
        # 打印历史消息内容
        print("\n当前会议历史消息:\n")
        for i, msg in enumerate(meeting.meeting_history[-10:]):  # 只打印最近10条消息
            agent = msg.get('agent', '未知')
            content_preview = msg.get('content', '')[:100] + ('...' if len(msg.get('content', '')) > 100 else '')
            timestamp = msg.get('timestamp', '')
            print(f"{i+1}. [{agent}] ({timestamp[:19]}): {content_preview}")
        print("\n")
        
        # 如果是继续处理的情况，使用会议对象中的轮次
        if is_continuation:
            # 使用会议对象中的当前轮次，不增加额外的轮次
            # 注意：meeting.current_round是从1开始的，而round_count是从0开始的，用于显示
            round_count = meeting.current_round - 1
            logger.info(f"继续处理第 {round_count + 1} 轮会议，当前轮次={meeting.current_round}，当前发言者索引={meeting.current_speaker_index}")
            
            # 如果有最后发言的人类，确保从下一个发言者开始
            if last_human_agent:
                # 记录用于调试
                logger.info(f"最后发言的人类是 {last_human_agent.name}，将从下一个发言者开始")
                
                # 特别处理：我们需要确保人类后面的AI角色能够发言
                # 先获取原始发言顺序（不考虑current_speaker_index）
                original_speaking_order = meeting.mode.determine_speaking_order(
                    [{"name": a.name, "role": a.role_description} for a in meeting.agents],
                    meeting.current_round - 1  # 使用上一轮的发言顺序，因为我们实际上继续的是上一轮的发言
                )
                
                logger.info(f"上一轮发言顺序: {original_speaking_order}")
                
                # 确保发言索引与发言顺序对齐
                # 如果人类不是最后一个发言者，则我们从人类的下一个开始
                if last_human_position >= 0 and last_human_position < len(original_speaking_order) - 1:
                    # 确保角色还有要发言的
                    next_speakers = original_speaking_order[last_human_position+1:]
                    logger.info(f"人类后面还有角色未发言: {next_speakers}")
                    
                    # 将meeting.current_speaker_index设置为那个未发言的人
                    for i, agent in enumerate(meeting.agents):
                        if agent.name == next_speakers[0]:
                            meeting.current_speaker_index = i
                            logger.info(f"将发言索引设置为 {i}(角色: {agent.name})，以确保未发言的角色可以发言")
                            break
        else:
            # 发送会话开始事件
            start_event = {
                "id": conversation_id,
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"role": "assistant", "content": ""},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(start_event, ensure_ascii=False)}\n\n"
            
            # 发送会议主题与格式说明
            intro_event = {
                "id": f"{conversation_id}-intro",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"content": f"# 讨论主题：{meeting.topic}\n\n"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(intro_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.3)
        
        # 主循环 - 处理讨论轮次
        while True:
            # 首先检查是否已达到最大轮次
            if meeting.current_round > meeting.max_rounds:
                logger.info(f"流式处理检测到当前轮次({meeting.current_round})已超过最大轮次({meeting.max_rounds})，结束会议")
                meeting.status = "已结束"
                meeting.end_time = datetime.now()
                
                # 发送会议结束信息
                end_meeting_info = {
                    "id": f"{conversation_id}-meeting-end",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": "\n\n## 会议结束\n\n*正在生成会议总结...*\n\n"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(end_meeting_info, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)
                
                # 调用finish方法生成会议总结，使用讨论组的自定义模型和提示
                summary = meeting.finish()
                logger.info(f"已生成会议总结，长度: {len(summary)}")
                
                # 发送会议总结 - 使用流式方式发送
                logger.info(f"开始直接流式生成和发送会议总结")
                
                # 获取会议主题和历史
                meeting_topic = meeting.topic
                meeting_history = meeting.meeting_history
                
                # 获取讨论组信息和总结模型配置
                custom_prompt = None
                model_name = None
                api_key = None
                api_base_url = None
                
                # 从会议对象获取讨论组信息
                group_info = getattr(meeting, 'group_info', None)
                
                if group_info:
                    # 获取自定义提示模板（如果有）
                    if 'summary_prompt' in group_info and group_info['summary_prompt']:
                        custom_prompt = group_info['summary_prompt']
                        logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                    
                    # 获取自定义总结模型（如果有）
                    if 'summary_model_id' in group_info and group_info['summary_model_id']:
                        model_id = group_info['summary_model_id']
                        logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                        
                        try:
                            # 获取模型信息
                            from app.models.database import get_db, Model
                            
                            # 获取数据库会话
                            db = next(get_db())
                            
                            # 查询模型配置
                            summary_model = db.query(Model).filter(Model.id == model_id).first()
                            
                            if summary_model:
                                logger.info(f"找到总结模型: {summary_model.name}")
                                model_name = summary_model.name
                                
                                # 获取API密钥和基础URL
                                api_key = getattr(summary_model, 'api_key', None)
                                api_url = getattr(summary_model, 'api_url', None)
                                
                                # 处理URL，从完整URL中提取基础部分
                                if api_url:
                                    if "/v1/chat/completions" in api_url:
                                        api_base_url = api_url.split("/v1/chat/completions")[0]
                                    else:
                                        api_base_url = api_url
                        except Exception as e:
                            logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
                
                # 使用模式的默认提示模板或自定义提示
                prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
                
                # 开始流式生成总结
                accumulated_summary = ""
                async for chunk in SummaryGenerator.generate_summary_stream(
                    meeting_topic=meeting_topic,
                    meeting_history=meeting_history,
                    prompt_template=prompt_template,
                    model_name=model_name,
                    api_key=api_key,
                    api_base_url=api_base_url
                ):
                    accumulated_summary += chunk
                    summary_chunk_event = {
                        "id": f"{conversation_id}-summary-chunk-{int(time.time()*1000)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(summary_chunk_event, ensure_ascii=False)}\n\n"
                
                # 将累积的总结保存到会议历史
                meeting.add_message("system", accumulated_summary)
                
                # 发送完成事件
                summary_end_event = {
                    "id": f"{conversation_id}-summary-end",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": ""},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(summary_end_event, ensure_ascii=False)}\n\n"
                
                logger.info(f"总结内容已通过流式方式实时生成和发送完毕，总长度: {len(accumulated_summary)}")
                print("会议结束，已实时生成并流式发送总结")
                
                # 发送结束标志
                yield f"data: [DONE]\n\n"
                return
            
            # 确保会议状态为"进行中"
            if meeting.status != "进行中":
                meeting.status = "进行中"
                logger.info(f"会议状态重置为'进行中': meeting_id={meeting_id}")
            
            # 发送美化的轮次标题 (除非是继续处理）
            if not is_continuation:
                round_title = {
                    "id": f"{conversation_id}-round-{round_count+1}-title",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"\n\n"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(round_title, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.3)
            else:
                # 继续处理时，重置标志
                is_continuation = False
            
            logger.info(f"流式模式: 开始执行第{round_count+1}轮讨论")
            print(f"\n开始执行第 {round_count+1} 轮讨论，会议轮次={meeting.current_round}，发言索引={meeting.current_speaker_index}\n")
            
            # 确定发言顺序 - 使用会议模式的定义
            speaking_order = meeting.mode.determine_speaking_order(
                [{"name": agent.name, "role": agent.role_description} for agent in meeting.agents],
                meeting.current_round
            )
            
            # 打印发言顺序
            print(f"本轮发言顺序: {', '.join(speaking_order)}\n")
            
            # 跟踪本轮是否所有角色都已发言
            all_agents_spoke = True
            
            # 如果是人类发言后的继续处理，需要特别处理下一个发言者
            if is_continuation and last_human_name:
                logger.info(f"人类发言后继续处理，检查发言顺序")
                
                # 如果我们得到了上一轮的发言顺序和人类的位置
                if last_human_position >= 0:
                    # 如果人类不是上一轮的最后一个发言者
                    prev_speaking_order = meeting.mode.determine_speaking_order(
                        [{"name": a.name, "role": a.role_description} for a in meeting.agents],
                        meeting.current_round - 1  # 上一轮
                    )
                    
                    if last_human_position < len(prev_speaking_order) - 1:
                        # 找到人类后面应该发言的角色
                        remaining_speakers = prev_speaking_order[last_human_position+1:]
                        logger.info(f"人类后面没发言的角色: {remaining_speakers}")
                        
                        # 重新排序发言顺序，优先完成上一轮
                        reordered_speakers = remaining_speakers
                        
                        # 如果当前已经是新的一轮，还需要加上这一轮的发言者
                        if meeting.current_round > 1:
                            current_round_speakers = meeting.mode.determine_speaking_order(
                                [{"name": a.name, "role": a.role_description} for a in meeting.agents],
                                meeting.current_round  # 当前轮
                            )
                            # 添加没有在remaining_speakers中的发言者
                            for speaker in current_round_speakers:
                                if speaker not in reordered_speakers:
                                    reordered_speakers.append(speaker)
                        
                        # 更新发言顺序
                        speaking_order = reordered_speakers
                        logger.info(f"重新排序后的发言顺序: {speaking_order}")
                        
                        # 更新当前发言者索引
                        if speaking_order and speaking_order[0] in [a.name for a in meeting.agents]:
                            for i, agent in enumerate(meeting.agents):
                                if agent.name == speaking_order[0]:
                                    meeting.current_speaker_index = i
                                    logger.info(f"将当前发言者索引设置为 {i} ({agent.name})")
                                    break
            # 打印最终定义的发言顺序
            logger.info(f"最终确定的发言顺序: {speaking_order}")
            print(f"更新后的发言顺序: {', '.join(speaking_order)}\n")
            
            # 关键修复：确保发言顺序与当前发言者索引对应
            # 记录每个角色在meeting.agents列表中的索引
            agent_indices = {}
            for i, agent in enumerate(meeting.agents):
                agent_indices[agent.name] = i
                logger.info(f"角色 {agent.name} 在agents列表中的索引为 {i}")
            
            # 获取当前发言者名称
            current_speaker_name = None
            if meeting.current_speaker_index < len(meeting.agents):
                current_speaker_name = meeting.agents[meeting.current_speaker_index].name
                logger.info(f"当前current_speaker_index={meeting.current_speaker_index}，对应角色: {current_speaker_name}")
            
            # 检查当前轮次已经发言过的角色 - 只考虑当前轮次
            spoken_agents = []
            
            # 初始化已发言角色表（避免重复发言），同时记录轮次信息
            # 格式为 {轮次: [发言人列表]}
            spoken_agents_in_current_round = {}
            
            # 特别记录当前轮次的消息
            current_round_msgs = []
            
            # 为了调试，打印所有消息记录
            logger.info(f"当前会议历史消息数: {len(meeting.meeting_history)}")
            for i, msg in enumerate(meeting.meeting_history):
                round_info = msg.get('round', 'N/A')
                agent_info = msg.get('agent', 'N/A')
                logger.info(f"[DEBUG] 消息{i+1}: 轮次={round_info}, 角色={agent_info}")
            
            # 先从history检查当前轮次的发言记录
            for msg in meeting.history:
                # 先检查消息是否包含需要的键
                if "round" in msg and "role" in msg:
                    # 只考虑当前轮次的消息
                    if msg["round"] == meeting.current_round and msg["role"] != "system":
                        # 确保轮次键存在
                        if msg["round"] not in spoken_agents_in_current_round:
                            spoken_agents_in_current_round[msg["round"]] = []
                        # 添加发言人到对应轮次
                        if msg["role"] not in spoken_agents_in_current_round[msg["round"]]:
                            spoken_agents_in_current_round[msg["round"]].append(msg["role"])
                        current_round_msgs.append(msg)
            
            logger.info(f"从内部history找到当前轮次({meeting.current_round})消息: {len(current_round_msgs)}")
            
            # 再从完整的meeting_history检查，只强调当前轮次
            current_round_meeting_history = []
            for msg in meeting.meeting_history:
                if "agent" in msg and msg["agent"] != "system":
                    # 优先检查消息是否有round字段并匹配当前轮次
                    if "round" in msg and msg["round"] == meeting.current_round:
                        # 记录当前轮次的发言者，确保不重复添加
                        # 确保轮次键存在
                        if msg["round"] not in spoken_agents_in_current_round:
                            spoken_agents_in_current_round[msg["round"]] = []
                        # 添加发言人到对应轮次
                        if msg["agent"] not in spoken_agents_in_current_round[msg["round"]]:
                            spoken_agents_in_current_round[msg["round"]].append(msg["agent"])
                            logger.info(f"从完整meeting_history找到轮次{msg['round']}发言者: {msg['agent']}")
                        current_round_meeting_history.append(msg)
            
            logger.info(f"从meeting_history找到当前轮次({meeting.current_round})消息: {len(current_round_meeting_history)}")
                        
            # 仅在当前讨论轮次中考虑最后发言的人类角色
            human_has_spoken_in_current_round = False
            
            # 绿色在当前轮次中检查人类消息
            human_has_spoken_in_current_round = False
            
            if hasattr(meeting, 'last_human_speaker') and meeting.last_human_speaker:
                # 使用多种方法检测人类消息
                
                # 方法1: 检查当前消息历史 - 先尝试直接在当前轮次的历史消息中查找
                current_round_msgs = [msg for msg in meeting.meeting_history 
                                    if "agent" in msg and 
                                       msg["agent"] == meeting.last_human_speaker and 
                                       "round" in msg and msg["round"] == meeting.current_round]  # 严格要求消息必须有round字段并且等于current_round
                
                if current_round_msgs:
                    human_has_spoken_in_current_round = True
                    # 确保轮次键存在
                    if meeting.current_round not in spoken_agents_in_current_round:
                        spoken_agents_in_current_round[meeting.current_round] = []
                    # 添加人类发言人到对应轮次
                    if meeting.last_human_speaker not in spoken_agents_in_current_round[meeting.current_round]:
                        spoken_agents_in_current_round[meeting.current_round].append(meeting.last_human_speaker)
                        logger.info(f"从消息历史中确认当前轮次({meeting.current_round})中人类角色{meeting.last_human_speaker}已发言")
                
                # 方法2: 检查最新的一条消息
                if not human_has_spoken_in_current_round and meeting.meeting_history:
                    latest_msg = meeting.meeting_history[-1]  # 获取最后一条消息
                    
                    # 如果最后一条消息是人类的，我们可以假设它是当前轮次的
                    if "agent" in latest_msg and latest_msg["agent"] == meeting.last_human_speaker:
                        human_has_spoken_in_current_round = True
                        # 确保轮次键存在
                        if meeting.current_round not in spoken_agents_in_current_round:
                            spoken_agents_in_current_round[meeting.current_round] = []
                        # 添加人类发言人到对应轮次
                        if meeting.last_human_speaker not in spoken_agents_in_current_round[meeting.current_round]:
                            spoken_agents_in_current_round[meeting.current_round].append(meeting.last_human_speaker)
                            logger.info(f"从最新消息确认当前轮次({meeting.current_round})中人类角色{meeting.last_human_speaker}已发言")
                
                
                # 如果所有方法都没找到该人类在当前轮中的发言
                if not human_has_spoken_in_current_round:
                    logger.info(f"人类角色{meeting.last_human_speaker}在当前轮次({meeting.current_round})中尚未发言")
            
            logger.info(f"从history找到已发言角色(按轮次): {spoken_agents_in_current_round}")
            # 获取当前轮次的发言者列表，如果不存在则创建空列表
            current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
            spoken_agents = current_round_speakers.copy()  # 同步当前轮次数据到spoken_agents变量
            
            # 根据当前轮次已发言的角色，确定未发言的角色
            remaining_speakers = []
            # 只保留当前轮次spoken_agents_in_current_round角色之后的角色
            # 找到最后一个已发言角色在speaking_order中的位置
            last_spoken_index = -1
            # 获取当前轮次的发言者列表
            current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
            for name in current_round_speakers:
                if name in speaking_order:
                    current_index = speaking_order.index(name)
                    last_spoken_index = max(last_spoken_index, current_index)
            
            # 只添加最后一个已发言角色之后的未发言角色
            for i in range(len(speaking_order)):
                name = speaking_order[i]
                # 获取当前轮次的发言者列表
                current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
                if i > last_spoken_index and name not in current_round_speakers:
                    remaining_speakers.append(name)
            
            # 如果没有找到任何角色（可能是第一轮开始），则添加所有未发言角色
            if not remaining_speakers and last_spoken_index == -1:
                for name in speaking_order:
                    # 获取当前轮次的发言者列表
                    current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
                    if name not in current_round_speakers:
                        remaining_speakers.append(name)
            
            # 获取当前轮次的发言者列表
            current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
            logger.info(f"第{meeting.current_round}轮已发言角色: {current_round_speakers}")
            logger.info(f"第{meeting.current_round}轮未发言角色: {remaining_speakers}")
            
            # 首先确保所有角色都能在当前轮次发言
            if remaining_speakers:
                # 如果还有未发言的角色，使用未发言角色列表
                reordered_speaking_order = remaining_speakers
                logger.info(f"使用未发言角色列表: {reordered_speaking_order}")
            else:
                # 当前轮次所有角色已发言，考虑进入下一轮
                logger.info(f"第{meeting.current_round}轮所有角色已发言完毕")
                
                # 检查是否达到最大轮次
                if meeting.current_round < meeting.max_rounds:
                    # 尚未达到最大轮次，进入下一轮
                    old_round = meeting.current_round
                    meeting.current_round += 1
                    logger.info(f"完成第{old_round}轮，开始第{meeting.current_round}轮讨论")
                    
                    # 使用原始发言顺序开始新轮讨论
                    reordered_speaking_order = speaking_order.copy()
                    
                    # 显示当前轮次完成消息
                    print(f"\n{'*'*40}")
                    print(f"第 {old_round} 轮讨论全部完成！")
                    print(f"所有 {len(speaking_order)} 个角色都已发言")
                    print(f"{'*'*40}\n")
                    print(f"\n{'='*80}")
                    print(f"第 {old_round} 轮讨论完成")
                    print(f"当前会议状态: {meeting.status}")
                    print(f"当前轮次: {meeting.current_round}")
                    print(f"历史消息数量: {len(meeting.meeting_history)}")
                    print(f"{'='*80}\n")
                else:
                    # 已达到最大轮次，会议结束
                    logger.info(f"已达到最大轮次 {meeting.max_rounds}，会议结束")
                    # 返回空列表表示结束会议
                    reordered_speaking_order = []
                
            logger.info(f"过滤已发言角色后的顺序: {reordered_speaking_order}")
            print(f"实际发言顺序: {', '.join(reordered_speaking_order)}\n")
            
            # 每个智能体依次发言 - 使用过滤后的发言顺序
            for agent_name in reordered_speaking_order:
                # 再次检查该角色是否已经在本轮发言过，以防止重复发言
                # 获取当前轮次的发言者列表
                current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
                if agent_name in current_round_speakers:
                    logger.info(f"角色 {agent_name} 已经在当前轮次({meeting.current_round})发言过，跳过")
                    continue
                    
                # 获取智能体
                agent = next((a for a in meeting.agents if a.name == agent_name), None)
                if not agent:
                    continue
                
                # 更新current_speaker_index为当前发言者对应的索引
                # 只有当该角色在当前轮次中还没有发言时才更新发言者索引
                # 获取当前轮次的发言者列表
                current_round_speakers = spoken_agents_in_current_round.get(meeting.current_round, [])
                for i, a in enumerate(meeting.agents):
                    if a.name == agent_name and a.name not in current_round_speakers:
                        if meeting.current_speaker_index != i:
                            logger.info(f"更新current_speaker_index从 {meeting.current_speaker_index} 到 {i} ({agent_name})")
                            meeting.current_speaker_index = i
                        break
                
                print(f"\n当前发言者: {agent_name} (索引: {meeting.current_speaker_index})")
                
                # 发送发言人信息 - 使用格式化的标题
                speaker_info = {
                    "id": f"{conversation_id}-{agent_name}-start",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": f"\n### {agent_name} 发言：\n\n"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(speaker_info, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.2)
                
                # 获取智能体提示
                prompt = meeting.mode.get_agent_prompt(
                    agent_name=agent.name,
                    agent_role=agent.role_description,
                    meeting_topic=meeting.topic,
                    current_round=meeting.current_round
                )
                
                # 获取当前上下文
                context = meeting._get_current_context()
                
                # 检查是否是人类智能体并且需要等待输入
                is_human_agent = hasattr(agent, 'is_human') and agent.is_human
                if is_human_agent:
                    # 设置等待人类输入状态
                    agent.wait_for_input()
                    
                    logger.info(f"等待人类角色 {agent_name} (索引: {meeting.current_speaker_index}) 输入")
                    print(f"等待人类角色 {agent_name} 输入...")
                    
                    # 发送等待人类输入的通知
                    waiting_msg = f"等待人类角色 {agent.name} 输入..."
                    waiting_event = {
                        "id": f"{conversation_id}-{agent_name}-waiting",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": f"\n\n[WAITING_FOR_HUMAN_INPUT:{agent.name}]\n\n"},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(waiting_event, ensure_ascii=False)}\n\n"
                    
                    # 暂停讨论，记录等录状态
                    meeting.waiting_for_human_input = agent.name
                    
                    # 不添加等待消息到会议历史
                    # meeting.add_message("system", f"等待人类角色 {agent.name} 输入")
                    
                    # 发送客户端指令，指示需要人类输入
                    client_instruction = {
                        "id": f"{conversation_id}-client-instruction",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": f"\n\n[WAITING_FOR_HUMAN_INPUT:{agent.name}]\n\n"},
                            "finish_reason": "waiting_human"
                        }]
                    }
                    yield f"data: {json.dumps(client_instruction, ensure_ascii=False)}\n\n"
                    
                    # 暂停继续执行，退出当前函数等待人类输入
                    # 标记未完成本轮讨论
                    all_agents_spoke = False
                    logger.info(f"流式讨论暂停，等待人类角色 {agent.name} 输入")
                    logger.info(f"当前轮次 {meeting.current_round} 未完成，需要等待人类输入后继续")
                    return
                
                # 实时流式生成并返回回应 - 优化缓冲处理提高流畅性
                buffer = ""
                thinking_dots_shown = False
                last_chunk_time = time.time()
                
                # 发送思考中提示
                thinking_event = {
                    "id": f"{conversation_id}-{agent_name}-thinking",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": ""},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(thinking_event, ensure_ascii=False)}\n\n"
                
                print(f"生成 {agent_name} 的回应中...")
                
                # 使用累积缓冲区优化流式输出
                async for chunk in agent.generate_response_stream(prompt, context):
                    # 检查是否是等待人类输入的特殊标记
                    if isinstance(chunk, str) and "[WAITING_FOR_HUMAN_INPUT:" in chunk:
                        # 提取人类角色名称
                        import re
                        match = re.search(r"\[WAITING_FOR_HUMAN_INPUT:(.*?)\]", chunk)
                        if match:
                            human_name = match.group(1)
                            
                            print(f"\n检测到需要人类 {human_name} 输入")
                            
                            # 发送等待人类输入的通知
                            waiting_msg = f"等待人类角色 {human_name} 输入..."
                            waiting_event = {
                                "id": f"{conversation_id}-{agent_name}-waiting",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "discussion-group",
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": f"\n\n[WAITING_FOR_HUMAN_INPUT:{human_name}]\n\n"},
                                    "finish_reason": "waiting_human"
                                }]
                            }
                            yield f"data: {json.dumps(waiting_event, ensure_ascii=False)}\n\n"
                            
                            # 暂停讨论，记录等待状态
                            meeting.waiting_for_human_input = human_name
                            
                            # 添加等待消息到会议历史
                            # meeting.add_message("system", f"轮到 {human_name} (人类角色) 发言，请输入您的发言内容")
                            
                            # 发送客户端指令，指示需要人类输入
                            client_instruction = {
                                "id": f"{conversation_id}-client-instruction",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "discussion-group",
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": f"\n\n[WAITING_FOR_HUMAN_INPUT:{human_name}]\n\n"},
                                    "finish_reason": "waiting_human"
                                }]
                            }
                            yield f"data: {json.dumps(client_instruction, ensure_ascii=False)}\n\n"
                            
                            # 暂停继续执行，退出当前函数等待人类输入
                            # 标记未完成本轮讨论
                            all_agents_spoke = False
                            logger.info(f"流式讨论暂停，等待人类角色 {human_name} 输入")
                            logger.info(f"当前轮次 {meeting.current_round} 未完成，需要等待人类输入后继续粗糙")
                            return
                    
                    buffer += chunk
                    current_time = time.time()
                    
                    # 使用更小的缓冲区和更短的时间间隔，创造打字效果
                    # 每1-3个字符输出一次，或每0.1-0.2秒输出一次
                    if len(buffer) >= random.randint(1, 3) or (current_time - last_chunk_time) > random.uniform(0.1, 0.2):
                        content_chunk = {
                            "id": f"{conversation_id}-{agent_name}-chunk-{int(current_time*1000)}",
                            "object": "chat.completion.chunk",
                            "created": int(current_time),
                            "model": "discussion-group",
                            "choices": [{
                                "index": 0,
                                "delta": {"content": buffer},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
                        buffer = ""
                        last_chunk_time = current_time
                        
                        # 添加极小的随机暂停以增强打字效果的自然感
                        # 这个暂停是异步的，不会阻塞其他处理
                        if random.random() < 0.3:  # 30%概率添加微小停顿
                            await asyncio.sleep(random.uniform(0.03, 0.08))
                
                # 发送剩余的缓冲区内容
                if buffer:
                    content_chunk = {
                        "id": f"{conversation_id}-{agent_name}-final",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": buffer},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(content_chunk, ensure_ascii=False)}\n\n"
                
                # 获取生成的完整回应
                response = agent.last_response
                
                # 打印智能体回应
                print(f"\n{agent_name} 的回应: {response[:100]}...\n")
                
                # 添加到会议历史
                meeting.add_message(agent.name, response)
                logger.info(f"当前回应: {response}")
                
                # 添加轻微的随机延迟使发言更自然
                await asyncio.sleep(0.3 + random.uniform(0, 0.3))
            
            # 只有所有角色都发言完毕，才增加轮次计数
            if all_agents_spoke:
                # 增加显示轮次计数
                round_count += 1
                
                # 增加会议轮次 - 确保只在此处增加轮次，避免重复计算
                meeting.current_round += 1
                logger.info(f"所有角色已完成发言，轮次递增: {meeting.current_round}")
                
                # 打印清晰的轮次完成标记
                print(f"\n{'*'*40}")
                print(f"第 {round_count} 轮讨论全部完成！")
                print(f"所有 {len(speaking_order)} 个角色都已发言")
                print(f"{'*'*40}\n")
                
                # 打印会议信息和历史更新
                print(f"\n{'='*80}")
                print(f"第 {round_count} 轮讨论完成")
                print(f"当前会议状态: {meeting.status}")
                print(f"当前轮次: {meeting.current_round}")
                print(f"历史消息数量: {len(meeting.meeting_history)}")
                print(f"{'='*80}\n")
                
                # 检查会议模式是否指示会议应该结束
                if meeting.mode.should_end_meeting(round_count, meeting.meeting_history):
                    logger.info(f"会议模式指示会议应该结束，当前轮次: {meeting.current_round}")
                    meeting.status = "已结束"
                    
                    # 发送会议结束信息 - 美化格式
                    end_meeting_info = {
                        "id": f"{conversation_id}-meeting-end",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": "\n\n## 会议结束\n\n*正在生成会议总结...*\n\n"},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(end_meeting_info, ensure_ascii=False)}\n\n"
                    print("会议结束，正在生成总结...")
                    break
            else:
                # 未完成所有发言，不增加轮次
                logger.info(f"未完成所有角色发言，轮次保持不变: {meeting.current_round}")
            
            # 添加分隔符使轮次之间更清晰
            round_separator = {
                "id": f"{conversation_id}-round-{round_count}-separator",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": "discussion-group",
                "choices": [{
                    "index": 0,
                    "delta": {"content": "\n\n---\n\n"},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(round_separator, ensure_ascii=False)}\n\n"
            
            # 检查是否已达到最大轮次，如果是则结束会议并生成总结
            if meeting.current_round > meeting.max_rounds and meeting.status != "已结束":
                logger.info(f"已达到最大轮次({meeting.max_rounds})，主动结束会议并生成总结")
                meeting.status = "已结束"
                meeting.end_time = datetime.now()
                
                # 设置跳过自动生成总结的标志
                meeting._skip_auto_summary = True
                
                # 发送会议结束信息
                end_meeting_info = {
                    "id": f"{conversation_id}-meeting-end",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": "\n\n## 会议结束\n\n*正在生成会议总结...*\n\n"},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(end_meeting_info, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.5)
                
                # 直接流式生成总结，不再调用meeting.finish()
                logger.info(f"开始直接流式生成和发送会议总结")
                
                # 获取会议主题和历史
                meeting_topic = meeting.topic
                meeting_history = meeting.meeting_history
                
                # 获取讨论组信息和总结模型配置
                custom_prompt = None
                model_name = None
                api_key = None
                api_base_url = None
                
                # 从会议对象获取讨论组信息
                group_info = getattr(meeting, 'group_info', None)
                
                if group_info:
                    # 获取自定义提示模板（如果有）
                    if 'summary_prompt' in group_info and group_info['summary_prompt']:
                        custom_prompt = group_info['summary_prompt']
                        logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                    
                    # 获取自定义总结模型（如果有）
                    if 'summary_model_id' in group_info and group_info['summary_model_id']:
                        model_id = group_info['summary_model_id']
                        logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                        
                        try:
                            # 获取模型信息
                            from app.models.database import get_db, Model
                            
                            # 获取数据库会话
                            db = next(get_db())
                            
                            # 查询模型配置
                            summary_model = db.query(Model).filter(Model.id == model_id).first()
                            
                            if summary_model:
                                logger.info(f"找到总结模型: {summary_model.name}")
                                model_name = summary_model.name
                                
                                # 获取API密钥和基础URL
                                api_key = getattr(summary_model, 'api_key', None)
                                api_url = getattr(summary_model, 'api_url', None)
                                
                                # 处理URL，从完整URL中提取基础部分
                                if api_url:
                                    if "/v1/chat/completions" in api_url:
                                        api_base_url = api_url.split("/v1/chat/completions")[0]
                                    else:
                                        api_base_url = api_url
                        except Exception as e:
                            logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
                
                # 使用模式的默认提示模板或自定义提示
                prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
                
                # 开始流式生成总结
                accumulated_summary = ""
                async for chunk in SummaryGenerator.generate_summary_stream(
                    meeting_topic=meeting_topic,
                    meeting_history=meeting_history,
                    prompt_template=prompt_template,
                    model_name=model_name,
                    api_key=api_key,
                    api_base_url=api_base_url
                ):
                    accumulated_summary += chunk
                    summary_chunk_event = {
                        "id": f"{conversation_id}-summary-chunk-{int(time.time()*1000)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(summary_chunk_event, ensure_ascii=False)}\n\n"
                
                # 将累积的总结保存到会议历史
                meeting.add_message("system", accumulated_summary)
                
                # 发送完成事件
                summary_end_event = {
                    "id": f"{conversation_id}-summary-end",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": ""},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(summary_end_event, ensure_ascii=False)}\n\n"
                
                logger.info(f"总结内容已通过流式方式实时生成和发送完毕，总长度: {len(accumulated_summary)}")
                print("会议结束，已实时生成并流式发送总结")
                
                # 发送结束标志
                yield f"data: [DONE]\n\n"
                return
            
            # 暂停一下再进行下一轮 - 适当的延迟使整体流程更自然
            await asyncio.sleep(0.7 + random.uniform(0, 0.5))
        
        # 发送完成标记
        yield "data: [DONE]\n\n"
        
        # 标记会议为结束状态，确保会话结束
        if meeting and not meeting.status == "已结束":
            meeting.status = "已结束"
            meeting.end_time = datetime.now()
            logger.info(f"会议流处理完成，已标记为结束: meeting_id={meeting_id}")
            
            # 生成并添加总结
            try:
                logger.info(f"检测到会议已结束但未找到有效总结，开始流式生成总结...")
                
                # 使用流式总结生成器实时生成并发送总结
                # 获取会议主题和历史
                meeting_topic = meeting.topic
                meeting_history = meeting.meeting_history
                
                # 获取讨论组信息和总结模型配置
                custom_prompt = None
                model_name = None
                api_key = None
                api_base_url = None
                
                # 从会议对象获取讨论组信息
                group_info = getattr(meeting, 'group_info', None)
                
                if group_info:
                    # 获取自定义提示模板（如果有）
                    if 'summary_prompt' in group_info and group_info['summary_prompt']:
                        custom_prompt = group_info['summary_prompt']
                        logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                    
                    # 获取自定义总结模型（如果有）
                    if 'summary_model_id' in group_info and group_info['summary_model_id']:
                        model_id = group_info['summary_model_id']
                        logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                        
                        try:
                            # 获取模型信息
                            from app.models.database import get_db, Model
                            
                            # 获取数据库会话
                            db = next(get_db())
                            
                            # 查询模型配置
                            summary_model = db.query(Model).filter(Model.id == model_id).first()
                            
                            if summary_model:
                                logger.info(f"找到总结模型: {summary_model.name}")
                                model_name = summary_model.name
                                
                                # 获取API密钥和基础URL
                                api_key = getattr(summary_model, 'api_key', None)
                                api_url = getattr(summary_model, 'api_url', None)
                                
                                # 处理URL，从完整URL中提取基础部分
                                if api_url:
                                    if "/v1/chat/completions" in api_url:
                                        api_base_url = api_url.split("/v1/chat/completions")[0]
                                    else:
                                        api_base_url = api_url
                        except Exception as e:
                            logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
                
                # 使用模式的默认提示模板或自定义提示
                prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
                
                # 开始流式生成总结
                accumulated_summary = ""
                async for chunk in SummaryGenerator.generate_summary_stream(
                    meeting_topic=meeting_topic,
                    meeting_history=meeting_history,
                    prompt_template=prompt_template,
                    model_name=model_name,
                    api_key=api_key,
                    api_base_url=api_base_url
                ):
                    accumulated_summary += chunk
                    summary_chunk_event = {
                        "id": f"{conversation_id}-summary-chunk-{int(time.time()*1000)}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": chunk},
                            "finish_reason": None
                        }]
                    }
                    yield f"data: {json.dumps(summary_chunk_event, ensure_ascii=False)}\n\n"
                
                # 将累积的总结保存到会议历史
                meeting.add_message("system", accumulated_summary)
                
                # 发送完成事件
                summary_end_event = {
                    "id": f"{conversation_id}-summary-end",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "discussion-group",
                    "choices": [{
                        "index": 0,
                        "delta": {"content": ""},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(summary_end_event, ensure_ascii=False)}\n\n"
                
                logger.info(f"总结内容已通过流式方式实时生成和发送完毕，总长度: {len(accumulated_summary)}")
                print("会议结束，已实时生成并流式发送总结")
                
                # 发送结束标志
                yield f"data: [DONE]\n\n"
                
            except Exception as e:
                logger.error(f"生成会议总结时出错: {str(e)}", exc_info=True)
        
        elif meeting and meeting.status == "已结束":
            # 检查是否已有总结，如果没有则生成
            summary = meeting.get_summary()
            if not summary or len(summary) < 100 or "未找到总结" in summary:
                try:
                    logger.info(f"检测到会议已结束但未找到有效总结，开始流式生成总结...")
                    
                    # 使用流式总结生成器实时生成并发送总结
                    # 获取会议主题和历史
                    meeting_topic = meeting.topic
                    meeting_history = meeting.meeting_history
                    
                    # 获取讨论组信息和总结模型配置
                    custom_prompt = None
                    model_name = None
                    api_key = None
                    api_base_url = None
                    
                    # 从会议对象获取讨论组信息
                    group_info = getattr(meeting, 'group_info', None)
                    
                    if group_info:
                        # 获取自定义提示模板（如果有）
                        if 'summary_prompt' in group_info and group_info['summary_prompt']:
                            custom_prompt = group_info['summary_prompt']
                            logger.info(f"使用讨论组自定义总结提示模板: length={len(custom_prompt)}")
                        
                        # 获取自定义总结模型（如果有）
                        if 'summary_model_id' in group_info and group_info['summary_model_id']:
                            model_id = group_info['summary_model_id']
                            logger.info(f"使用讨论组自定义总结模型: model_id={model_id}")
                            
                            try:
                                # 获取模型信息
                                from app.models.database import get_db, Model
                                
                                # 获取数据库会话
                                db = next(get_db())
                                
                                # 查询模型配置
                                summary_model = db.query(Model).filter(Model.id == model_id).first()
                                
                                if summary_model:
                                    logger.info(f"找到总结模型: {summary_model.name}")
                                    model_name = summary_model.name
                                    
                                    # 获取API密钥和基础URL
                                    api_key = getattr(summary_model, 'api_key', None)
                                    api_url = getattr(summary_model, 'api_url', None)
                                    
                                    # 处理URL，从完整URL中提取基础部分
                                    if api_url:
                                        if "/v1/chat/completions" in api_url:
                                            api_base_url = api_url.split("/v1/chat/completions")[0]
                                        else:
                                            api_base_url = api_url
                            except Exception as e:
                                logger.error(f"获取总结模型信息失败: {str(e)}", exc_info=True)
                    
                    # 使用模式的默认提示模板或自定义提示
                    prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
                    
                    # 开始流式生成总结
                    accumulated_summary = ""
                    async for chunk in SummaryGenerator.generate_summary_stream(
                        meeting_topic=meeting_topic,
                        meeting_history=meeting_history,
                        prompt_template=prompt_template,
                        model_name=model_name,
                        api_key=api_key,
                        api_base_url=api_base_url
                    ):
                        accumulated_summary += chunk
                        summary_chunk_event = {
                            "id": f"{conversation_id}-summary-chunk-{int(time.time()*1000)}",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "discussion-group",
                            "choices": [{
                                "index": 0,
                                "delta": {"content": chunk},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(summary_chunk_event, ensure_ascii=False)}\n\n"
                    
                    # 将累积的总结保存到会议历史
                    meeting.add_message("system", accumulated_summary)
                    
                    # 发送完成事件
                    summary_end_event = {
                        "id": f"{conversation_id}-summary-end",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "discussion-group",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": ""},
                            "finish_reason": "stop"
                        }]
                    }
                    yield f"data: {json.dumps(summary_end_event, ensure_ascii=False)}\n\n"
                    
                    logger.info(f"总结内容已通过流式方式实时生成和发送完毕，总长度: {len(accumulated_summary)}")
                    print("会议结束，已实时生成并流式发送总结")
                    
                    # 发送结束标志
                    yield f"data: [DONE]\n\n"
                    
                except Exception as e:
                    logger.error(f"补充生成会议总结时出错: {str(e)}", exc_info=True)
            
        # 打印完整会议历史
        self._print_full_discussion({'history': meeting.meeting_history, 'summary': meeting.get_summary()})
    
    def _print_latest_round_content(self, meeting_id: str):
        """打印最新一轮的对话内容"""
        try:
            meeting_data = self.adapter.active_meetings.get(meeting_id)
            if not meeting_data:
                return
            
            # 获取会议对象
            meeting = meeting_data.get("meeting")
            if not meeting:
                return
            
            # 获取当前轮次
            current_round = meeting.current_round
            
            print(f"\n{'='*80}")
            print(f"第 {current_round-1} 轮讨论内容:")
            print(f"{'='*80}")
            
            # 只显示最近的2条消息（通常是本轮的发言）
            history = meeting.meeting_history
            recent_messages = [msg for msg in history if msg["agent"] != "system"][-2:]
            
            for msg in recent_messages:
                print(f"\n[{msg['agent']}]:")
                print(f"{msg['content']}")
            
            print(f"\n{'='*80}\n")
        except Exception as e:
            logger.error(f"打印最新一轮内容时出错: {str(e)}")

    def _print_full_discussion(self, result: Dict[str, Any]):
        """打印完整的讨论历史和总结"""
        try:
            history = result.get("history", [])
            summary = result.get("summary", "无总结")
            
            print(f"\n{'='*80}")
            print(f"完整讨论内容:")
            print(f"{'='*80}")
            
            for msg in history:
                if msg["agent"] != "system":
                    print(f"\n[{msg['agent']}]:")
                    print(f"{msg['content']}")
            
            print(f"\n{'='*80}")
            print(f"讨论总结:")
            print(f"{'='*80}")
            print(f"\n{summary}")
            print(f"\n{'='*80}\n")
        except Exception as e:
            logger.error(f"打印完整讨论内容时出错: {str(e)}")

    # 添加处理人类输入的方法，直接在DiscussionProcessor中处理
    def process_human_input(self, meeting_id: str, agent_name: str, message: str) -> Dict[str, Any]:
        """处理人类角色的输入"""
        logger.info(f"处理人类输入，会议ID: {meeting_id}, 角色: {agent_name}")
        
        # 首先尝试从自己的active_meetings获取会议数据
        meeting_data = self.active_meetings.get(meeting_id)
        
        # 如果没有找到，且adapter存在，从adapter中获取
        if not meeting_data and self.adapter:
            meeting_data = self.adapter.active_meetings.get(meeting_id)
            # 同步到自己的字典
            if meeting_data:
                self.active_meetings[meeting_id] = meeting_data
        
        # 如果仍未找到，抛出错误
        if not meeting_data:
            logger.error(f"会议ID {meeting_id} 不存在")
            raise ValueError(f"会议ID {meeting_id} 不存在")
        
        # 获取会议对象
        meeting = meeting_data.get("meeting")
        if not meeting:
            logger.error(f"会议数据格式错误: meeting_id={meeting_id}")
            raise ValueError(f"会议数据格式错误")
        
        # 查找对应的人类智能体
        human_agent = None
        for agent in meeting.agents:
            if hasattr(agent, 'is_human') and agent.is_human and agent.name == agent_name:
                human_agent = agent
                break
        
        if not human_agent:
            logger.error(f"找不到人类智能体 {agent_name}，会议ID={meeting_id}")
            raise ValueError(f"找不到人类智能体 {agent_name}")
        
        # 添加人类消息
        success = meeting.add_human_message(agent_name, message)
        if not success:
            logger.error(f"无法为 {agent_name} 添加消息，会议ID={meeting_id}")
            raise ValueError(f"无法为 {agent_name} 添加消息")
            
        # 记录最后发言的人类角色
        meeting.last_human_speaker = agent_name
        logger.info(f"记录最后发言的人类角色: {agent_name}")
        
        # 重置等待状态
        if hasattr(human_agent, 'is_waiting_input'):
            human_agent.is_waiting_input = False
            if hasattr(human_agent, 'input_start_time'):
                human_agent.input_start_time = None
            logger.info(f"已重置人类智能体 {agent_name} 的等待状态")
        
        # 如果会议有等待人类输入的标记，清除它
        if hasattr(meeting, 'waiting_for_human_input') and meeting.waiting_for_human_input == agent_name:
            meeting.waiting_for_human_input = None
            logger.info(f"已清除会议的等待人类输入标记")
        
        # 确保会议状态是"进行中"
        if meeting.status == "等待人类输入" or meeting.status == "未开始":
            meeting.status = "进行中"
            logger.info(f"已将会议状态从'{meeting.status}'更改为'进行中'")
        
        # 记录当前轮次和发言者索引，便于日志分析
        original_round = meeting.current_round
        original_speaker_index = meeting.current_speaker_index
        logger.info(f"人类输入处理前：轮次={original_round}，发言索引={original_speaker_index}")
        
        # 获取发言顺序，用于确定是否所有角色都已发言
        speaking_order = meeting.mode.determine_speaking_order(
            [{"name": agent.name, "role": agent.role_description} for agent in meeting.agents],
            meeting.current_round
        )
        logger.info(f"本轮发言顺序: {speaking_order}")
        
        # 处理人类输入后更新发言顺序和轮次
        # 检查当前发言者是否为该人类角色
        current_speaker_is_human = False
        if meeting.current_speaker_index < len(meeting.agents):
            current_speaker = meeting.agents[meeting.current_speaker_index]
            if current_speaker.name == agent_name:
                current_speaker_is_human = True
        
        # 找到人类在发言顺序中的位置
        human_position_in_order = -1
        for i, name in enumerate(speaking_order):
            if name == agent_name:
                human_position_in_order = i
                break
        
        # 记录人类在发言顺序中的位置
        logger.info(f"人类角色 {agent_name} 在发言顺序中的位置: {human_position_in_order}")
        
        # 如果当前发言者是该人类角色，手动调用移动到下一个发言者的方法
        if current_speaker_is_human:
            logger.info(f"人类角色 {agent_name} 是当前发言者，处理响应并移到下一位发言者")
            # 记录消息并移到下一个发言者
            meeting._move_to_next_speaker()
            logger.info(f"人类输入后移动到下一位发言者，当前索引: {meeting.current_speaker_index}")
            
            # 检查是否是本轮最后一个发言者
            # 如果人类是最后一个发言者(或倒数第二个，且下一个已经发言过)，则需要增加轮次
            is_last_speaker = human_position_in_order == len(speaking_order) - 1
            
            # 如果人类是第一个发言者，确保不要提前结束本轮发言
            if human_position_in_order == 0:
                logger.info(f"人类角色是本轮第一个发言者，确保本轮继续进行")
                # 不需要特别处理，只需确保不增加轮次
            
            # 如果人类是最后一个发言者，则本轮结束
            # 注意：轮次增加已经在meeting.py的add_human_message中处理过了，这里不要重复增加
            elif is_last_speaker:
                logger.info(f"人类角色是本轮最后一个发言者，准备进入下一轮")
                # 不在此处增加轮次，避免重复增加
        else:
            # 如果不是当前发言者，尝试找到其位置并更新发言索引
            logger.info(f"人类角色 {agent_name} 不是当前发言者，尝试找到其位置并更新")
            # 查找该人类智能体在发言顺序中的位置
            for i, agent in enumerate(meeting.agents):
                if agent.name == agent_name:
                    logger.info(f"找到人类角色 {agent_name} 在位置 {i}，当前发言者位置是 {meeting.current_speaker_index}")
                    # 将当前发言位置设置为该人类后面的位置，确保下一个发言者是人类后面的
                    meeting.current_speaker_index = (i + 1) % len(meeting.agents)
                    logger.info(f"人类输入后设置下一位发言者索引为: {meeting.current_speaker_index}")
                    
                    # 如果重新设置后索引为0，说明已经回到第一个发言者
                    # 注意：轮次增加已经在meeting.py的add_human_message中处理过了，这里不要重复增加
                    if meeting.current_speaker_index == 0:
                        logger.info(f"发言索引回到首位，当前轮次为 {meeting.current_round}")
                    break
        
        # 记录处理后的轮次和发言者索引
        logger.info(f"人类输入处理后：轮次={meeting.current_round}，发言索引={meeting.current_speaker_index}")
        
        # 确保人类消息被正确添加到会议历史
        logger.info(f"确认人类消息已添加到会议历史，当前历史长度: {len(meeting.meeting_history)}")
        
        # 输出会议状态
        logger.info(f"人类输入已添加: 会议ID={meeting_id}, 角色={agent_name}, 消息长度={len(message)}, 当前轮次={meeting.current_round}")
        
        # 检查是否达到最大轮次，如果达到则直接结束会议
        if meeting.current_round > meeting.max_rounds:
            logger.info(f"人类输入后检查发现轮次已超过最大值 (当前轮次={meeting.current_round}, 最大轮次={meeting.max_rounds})，结束会议")
            meeting.status = "已结束"
            meeting.end_time = datetime.now()
            return {
                "success": True,
                "message": f"{agent_name} 的消息已提交，会议已结束 (达到最大轮次)",
                "meeting_id": meeting_id,
                "status": "已结束",
                "current_round": meeting.current_round
            }
        
        return {
            "success": True,
            "message": f"{agent_name} 的消息已提交，会议将继续进行",
            "meeting_id": meeting_id,
            "status": meeting.status,
            "current_round": meeting.current_round
        }

    async def _end_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """结束会议并获取总结"""
        try:
            # 获取会议对象
            meeting_data = self.active_meetings.get(meeting_id)
            if not meeting_data:
                logger.error(f"结束会议失败: 会议ID {meeting_id} 不存在")
                return {"error": f"会议ID {meeting_id} 不存在"}
            
            # 从会议数据中获取会议对象
            meeting = meeting_data.get("meeting")
            if not meeting:
                logger.error(f"会议数据格式错误: meeting_id={meeting_id}")
                return {"error": f"会议数据格式错误: meeting_id={meeting_id}"}
            
            # 获取讨论组信息
            group_info = meeting.group_info
            
            # 检查会议是否已有总结
            existing_summary = meeting.get_summary() if hasattr(meeting, 'get_summary') else None
            if meeting.status == "已结束" and existing_summary and len(existing_summary) > 100 and "未找到总结" not in existing_summary:
                logger.info(f"会议已结束且已有总结，直接返回: meeting_id={meeting_id}")
                result = meeting.to_dict()
                if "summary" not in result:
                    result["summary"] = existing_summary
                return result
            
            # 设置会议状态为已结束(如果尚未结束)
            if meeting.status != "已结束":
                meeting.status = "已结束"
                meeting.end_time = datetime.now()
                logger.info(f"会议状态设置为已结束: meeting_id={meeting_id}")
            
            # 获取自定义总结模型（如果有）
            summary_model = None
            api_key = None
            api_base_url = None
            
            if group_info and 'summary_model_id' in group_info and group_info['summary_model_id']:
                model_id = group_info['summary_model_id']
                logger.info(f"使用自定义总结模型: model_id={model_id}")
                
                # 从数据库获取模型配置
                try:
                    from app.models.database import Model
                    summary_model = self.db.query(Model).filter(Model.id == model_id).first()
                
                    if summary_model:
                        logger.info(f"找到总结模型: {summary_model.name}")
                        # 获取API密钥和基础URL
                        api_key = getattr(summary_model, 'api_key', None)
                        api_url = getattr(summary_model, 'api_url', None)
                        
                        # 处理URL，从完整URL中提取基础部分
                        if api_url:
                            if "/v1/chat/completions" in api_url:
                                api_base_url = api_url.split("/v1/chat/completions")[0]
                            else:
                                api_base_url = api_url
                except Exception as e:
                    logger.error(f"获取总结模型信息失败: {str(e)}，将使用默认模型", exc_info=True)
            
            # 获取自定义提示模板（如果有）
            custom_prompt = None
            if group_info and 'summary_prompt' in group_info and group_info['summary_prompt']:
                custom_prompt = group_info['summary_prompt']
                logger.info(f"使用自定义总结提示模板: length={len(custom_prompt)}")
            
            # 检查会议历史中是否已包含总结
            has_summary_in_history = False
            for msg in meeting.meeting_history:
                if msg.get("agent") == "system" and len(msg.get("content", "")) > 100:
                    # 如果历史中已经有看起来像总结的系统消息，标记为已有总结
                    has_summary_in_history = True
                    existing_summary = msg.get("content", "")
                    logger.info(f"在会议历史中找到总结: 长度={len(existing_summary)}")
                    break
            
            # 如果还未生成总结，则生成
            if not has_summary_in_history:
                # 生成总结
                meeting_topic = meeting.topic
                meeting_history = meeting.meeting_history
                
                # 使用自定义模型和提示（如果有），否则使用默认
                model_name = summary_model.name if summary_model else None  # 使用默认值
                
                # 使用会议模式的默认提示模板或自定义提示
                prompt_template = custom_prompt if custom_prompt else meeting.mode.get_summary_prompt_template()
                
                logger.info(f"生成总结: model_name={model_name or '默认'}, 提示模板长度={len(prompt_template)}")
                
                # 使用流式方式生成总结
                logger.info(f"开始流式生成总结: meeting_id={meeting_id}")
                accumulated_summary = ""
                
                # 使用流式总结生成器
                async for chunk in SummaryGenerator.generate_summary_stream(
                    meeting_topic=meeting_topic,
                    meeting_history=meeting_history,
                    prompt_template=prompt_template,
                    model_name=model_name,
                    api_key=api_key,
                    api_base_url=api_base_url
                ):
                    accumulated_summary += chunk
                
                # 将累积的总结添加到会议历史
                meeting.add_message("system", accumulated_summary)
                logger.info(f"已流式生成并添加总结到会议历史: 长度={len(accumulated_summary)}")
                
                # 使用累积的总结作为结果
                summary = accumulated_summary
            else:
                # 使用已有的总结
                summary = existing_summary
                logger.info(f"使用已有总结: 长度={len(summary)}")
            
            # 确保会议状态为已结束
            meeting.status = "已结束"
            if not meeting.end_time:
                meeting.end_time = datetime.now()
            
            # 构建返回结果
            result = meeting.to_dict()
            
            # 确保返回的数据包含summary字段
            if "summary" not in result:
                result["summary"] = summary
            
            # 记录会议结束
            logger.info(f"会议已结束: meeting_id={meeting_id}, 总结长度={len(result.get('summary', ''))}")
            
            return result
        except Exception as e:
            logger.error(f"结束会议时出错: {str(e)}", exc_info=True)
            # 尝试创建一个基本的错误返回
            return {
                "error": f"结束会议时出错: {str(e)}",
                "id": meeting_id,
                "topic": meeting.topic if meeting else "未知主题",
                "history": meeting.meeting_history if meeting else [],
                "summary": "由于技术问题，无法生成会议总结。"
            } 