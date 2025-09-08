import os
import sys
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, Request, HTTPException, Body
from fastapi.responses import StreamingResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uvicorn
import json
import uuid
import time
import re
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logger import logger
from app.utils.auth import verify_api_key

from app.models.database import get_db, init_db, Model as DBModel, Configuration as DBConfiguration, ConfigurationStep, Role, DiscussionGroup
from app.models.schemas import Model, ModelCreate, Configuration, ConfigurationCreate
from app.models import ModelCollaboration, MultiStepModelCollaboration
from app.routes import model_router, configuration_router, api_key_router, auth_router
from app.routers import meeting, roles, discussion_groups, discussions
from app.processors.role_processor import RoleProcessor
from app.processors.discussion_processor import DiscussionProcessor
from app.adapters.meeting_adapter import MeetingAdapter

# 自定义中间件类，用于过滤特定路径的访问日志
class AccessLogFilter(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, paths_to_ignore: List[str]):
        super().__init__(app)
        self.paths_to_ignore = paths_to_ignore
        
    async def dispatch(self, request: Request, call_next):
        # 获取请求路径
        path = request.url.path
        
        # 检查是否是需要忽略的路径
        should_ignore = False
        for ignore_path in self.paths_to_ignore:
            if '*' in ignore_path:
                # 处理包含通配符的路径
                pattern = ignore_path.replace('*', '.*')
                if re.match(pattern, path):
                    should_ignore = True
                    break
            else:
                # 处理精确匹配的路径
                if ignore_path == path:
                    should_ignore = True
                    break
        
        if should_ignore:
            # 临时禁用访问日志记录器
            access_logger = logging.getLogger("uvicorn.access")
            original_level = access_logger.level
            access_logger.setLevel(logging.WARNING)  # 提高日志级别以忽略INFO级别的日志
            
            try:
                # 处理请求
                response = await call_next(request)
                return response
            finally:
                # 恢复日志级别
                access_logger.setLevel(original_level)
        
        # 处理其他正常记录日志的请求
        response = await call_next(request)
        return response

# 加载环境变量
load_dotenv()

app = FastAPI(title="DeepGemini API")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# CORS设置
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
allow_origins_list = ALLOW_ORIGINS.split(",") if ALLOW_ORIGINS else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加日志过滤中间件，忽略特定路径的访问日志
app.add_middleware(
    AccessLogFilter,
    paths_to_ignore=[
        "/api/meeting/discussions/.*/messages",  # 忽略讨论消息轮询请求
        "/api/meeting/discussions/.*/round",     # 忽略轮次请求
        "/api/meeting/discussions/.*/human_roles" # 忽略人类角色查询
    ]
)

# Initialize database
init_db()

# 添加获取默认API密钥的端点
@app.get("/v1/system/default_api_key")
async def get_default_api_key():
    """
    获取默认API密钥，取自.env文件中配置的第一个密钥
    """
    try:
        # 从环境变量中获取API密钥配置
        api_keys_json = os.getenv('ALLOW_API_KEY', '[]')
        api_keys_data = json.loads(api_keys_json)
        
        # 确保数据是正确的格式并且有至少一个密钥
        if isinstance(api_keys_data, list) and len(api_keys_data) > 0 and isinstance(api_keys_data[0], dict) and "key" in api_keys_data[0]:
            # 返回第一个API密钥
            return {"api_key": api_keys_data[0]["key"]}
        else:
            # 如果没有找到有效的API密钥，返回错误
            return JSONResponse(
                status_code=404,
                content={"error": "No valid API key found in configuration"}
            )
    except Exception as e:
        logger.error(f"获取默认API密钥时发生错误: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# Model routes
@app.get("/v1/models")
async def get_models(db: Session = Depends(get_db)):
    """返回OpenAI格式的模型列表，包括配置、角色和讨论组"""
    # 获取配置
    configurations = db.query(DBConfiguration).all()
    
    # 获取角色
    roles = db.query(Role).all()
    
    # 获取讨论组
    groups = db.query(DiscussionGroup).all()
    
    # 合并结果
    result = []
    
    # 添加配置
    for config in configurations:
        result.append({
            "id": config.name,
            "object": "model",
            "created": 0,  # 目前不跟踪创建时间
            "owned_by": "deepgemini"
        })
    
    # 添加角色
    for role in roles:
        result.append({
            "id": f"role-{role.id}",  # 使用一致的格式 role-ID
            "object": "model",
            "created": int(role.created_at.timestamp()) if role.created_at else 0,
            "owned_by": "deepgemini",
            "name": role.name,
            "type": "role"
        })
    
    # 添加讨论组
    for group in groups:
        result.append({
            "id": f"group-{group.id}",  # 使用一致的格式 group-ID
            "object": "model",
            "created": int(group.created_at.timestamp()) if group.created_at else 0,
            "owned_by": "deepgemini",
            "name": group.name,
            "type": "group"
        })
    
    return {
        "object": "list",
        "data": result
    }

@app.get("/v1/model_configs", response_model=List[Model])
async def get_model_configs(db: Session = Depends(get_db)):
    """Return the original model configurations"""
    return db.query(DBModel).all()

@app.post("/v1/models", response_model=Model)
async def create_model(model: ModelCreate, db: Session = Depends(get_db)):
    try:
        # 从 model.dict() 中只获取数据库模型中存在的字段
        model_data = {
            'name': model.name,
            'type': model.type,
            'provider': model.provider,
            'api_key': model.api_key,
            'api_url': model.api_url,
            'model_name': model.model_name,
            'temperature': model.temperature,
            'top_p': model.top_p,
            'max_tokens': model.max_tokens,
            'presence_penalty': model.presence_penalty,
            'frequency_penalty': model.frequency_penalty,
            'enable_tools': model.enable_tools,
            'tools': model.tools,
            'tool_choice': model.tool_choice,
            'enable_thinking': model.enable_thinking,
            'thinking_budget_tokens': model.thinking_budget_tokens,
            'custom_parameters': model.custom_parameters if model.custom_parameters else {}
        }
        
        db_model = DBModel(**model_data)
        db.add(db_model)
        db.commit()
        db.refresh(db_model)
        return db_model
    except Exception as e:
        db.rollback()
        logger.error(f"创建模型时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/v1/models/{model_id}", response_model=Model)
async def update_model(model_id: int, model: ModelCreate, db: Session = Depends(get_db)):
    db_model = db.query(DBModel).filter(DBModel.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    for key, value in model.dict().items():
        setattr(db_model, key, value)
    
    db.commit()
    db.refresh(db_model)
    return db_model

@app.delete("/v1/models/{model_id}")
async def delete_model(model_id: int, db: Session = Depends(get_db)):
    db_model = db.query(DBModel).filter(DBModel.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(db_model)
    db.commit()
    return {"status": "success"}

# Configuration routes
@app.get("/v1/configurations", response_model=List[Configuration])
async def get_configurations(db: Session = Depends(get_db)):
    return db.query(DBConfiguration).all()

@app.post("/v1/configurations", response_model=Configuration)
async def create_configuration(config: ConfigurationCreate, db: Session = Depends(get_db)):
    try:
        # 验证所有模型是否存在且用途类型正确
        for step in config.steps:
            model = db.query(DBModel).filter(DBModel.id == step.model_id).first()
            if not model:
                raise HTTPException(status_code=404, detail=f"Model {step.model_id} not found")
            if model.type not in ["both", step.step_type]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model {model.name} cannot be used for {step.step_type}"
                )

        # 创建配置
        db_config = DBConfiguration(
            name=config.name,
            is_active=config.is_active,
            transfer_content=config.transfer_content
        )
        db.add(db_config)
        db.commit()
        db.refresh(db_config)

        # 创建配置步骤
        for step in config.steps:
            db_step = ConfigurationStep(
                configuration_id=db_config.id,
                model_id=step.model_id,
                step_type=step.step_type,
                step_order=step.step_order,
                system_prompt=step.system_prompt
            )
            db.add(db_step)
        
        db.commit()
        db.refresh(db_config)
        return db_config
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建配置时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/v1/configurations/{config_id}", response_model=Configuration)
async def update_configuration(config_id: int, config: ConfigurationCreate, db: Session = Depends(get_db)):
    try:
        # 获取现有配置
        db_config = db.query(DBConfiguration).filter(DBConfiguration.id == config_id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # 更新基本字段
        db_config.name = config.name
        db_config.is_active = config.is_active
        db_config.transfer_content = config.transfer_content
        
        # 删除现有步骤
        db.query(ConfigurationStep).filter(
            ConfigurationStep.configuration_id == config_id
        ).delete()
        
        # 创建新步骤
        for step in config.steps:
            db_step = ConfigurationStep(
                configuration_id=config_id,
                model_id=step.model_id,
                step_type=step.step_type,
                step_order=step.step_order,
                system_prompt=step.system_prompt
            )
            db.add(db_step)
        
        try:
            db.commit()
            db.refresh(db_config)
            logger.info(f"配置已更新: {db_config.name}")
            return db_config
        except Exception as e:
            db.rollback()
            logger.error(f"更新配置时发生错误: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    except Exception as e:
        logger.error(f"更新配置时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/v1/configurations/{config_id}")
async def delete_configuration(config_id: int, db: Session = Depends(get_db)):
    db_config = db.query(DBConfiguration).filter(DBConfiguration.id == config_id).first()
    if not db_config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    
    db.delete(db_config)
    db.commit()
    return {"status": "success"}

@app.get("/v1/configurations/{config_id}", response_model=Configuration)
async def get_configuration(config_id: int, db: Session = Depends(get_db)):
    """获取单个配置的详细信息"""
    try:
        # 获取配置
        db_config = db.query(DBConfiguration).filter(DBConfiguration.id == config_id).first()
        if not db_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        
        # 获取配置步骤
        db_config.steps = db.query(ConfigurationStep).filter(
            ConfigurationStep.configuration_id == config_id
        ).order_by(ConfigurationStep.step_order).all()
        
        return db_config
    except Exception as e:
        logger.error(f"获取配置时发生错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Chat completion endpoint with configuration support
@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request,
    model: str = Body(...),
    messages: List[Dict[str, Any]] = Body(...),
    temperature: Optional[float] = Body(0.7),
    max_tokens: Optional[int] = Body(None),
    stream: Optional[bool] = Body(False),
    tools: Optional[List[Dict[str, Any]]] = Body(None),
    tool_choice: Optional[Dict[str, Any]] = Body(None),
    enable_thinking: Optional[bool] = Body(False),
    thinking_budget_tokens: Optional[int] = Body(2000),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """聊天补全API，兼容OpenAI格式"""
    try:
        # 记录请求
        logger.info(f"接收到聊天补全请求: model={model}, messages_count={len(messages)}, stream={stream}")
        
        # 检查是否是角色请求（支持两种格式: role-ID 或 role_ID）
        role_match = re.match(r"role[-_](\d+)", model)
        if role_match:
            role_id = int(role_match.group(1))
            logger.info(f"识别为角色请求: role_id={role_id}")
            
            # 检查消息格式
            logger.debug(f"消息格式: {type(messages)}")
            if isinstance(messages, str):
                logger.warning(f"收到字符串格式消息，转换为标准格式")
                messages = [{"role": "user", "content": messages}]
            
            # 创建角色处理器
            processor = RoleProcessor(db, role_id)
            
            # 处理请求
            if stream:
                # 流式响应
                logger.info("使用流式响应")
                result = await processor.process_request(messages, stream=True)
                return StreamingResponse(
                    convert_coroutine_to_stream(result),
                    media_type="text/event-stream"
                )
            else:
                # 普通响应
                logger.info("使用普通响应")
                content = await processor.process_request(messages, stream=False)
                
                # 按OpenAI格式返回
                return {
                    "id": f"chatcmpl-{uuid.uuid4()}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": content,
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0
                    }
                }
        
        # 处理讨论组请求（支持两种格式: group-ID 或 group_ID）
        group_match = re.match(r"group[-_](\d+)", model)
        if group_match:
            try:
                group_id = int(group_match.group(1))
                logger.info(f"识别为讨论组请求: group_id={group_id}")
                
                processor = DiscussionProcessor(db)
                processor.adapter = MeetingAdapter(db)
                processor.group_id = group_id
                
                # 获取最后一条消息作为提示
                prompt = messages[-1]["content"] if messages else ""
                
                if stream:
                    # 创建处理协程的流式响应
                    # 先启动会议获取会议ID
                    meeting_id = processor.start_meeting(group_id, prompt)
                    logger.info(f"启动会议成功，meeting_id={meeting_id}")
                    
                    # 创建流式响应，带上会议ID头
                    response = StreamingResponse(
                        convert_coroutine_to_stream(processor.process_request(prompt, stream=True, meeting_id=meeting_id)),
                        media_type="text/event-stream"
                    )
                    response.headers["X-Meeting-Id"] = meeting_id
                    return response
                else:
                    # 非流式模式下先启动会议，以保证一致性
                    meeting_id = processor.start_meeting(group_id, prompt)
                    logger.info(f"启动会议成功，meeting_id={meeting_id}")
                    
                    # 使用现有会议ID处理请求
                    response = await processor.process_request(prompt, stream=False, meeting_id=meeting_id)
                    return response
            except Exception as e:
                logger.error(f"处理讨论组请求失败: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        # 处理常规模型请求
        else:
            # 记录常规模型请求参数
            logger.info(f"处理常规模型请求: model={model}, enable_thinking={enable_thinking}, thinking_budget_tokens={thinking_budget_tokens}")
            
            # 尝试判断是否是模型ID
            try:
                model_id = int(model)
                # 如果是数字，先通过ID查找模型
                db_model = db.query(DBModel).filter(DBModel.id == model_id).first()
                if db_model:
                    # 使用模型名称查找配置
                    config = db.query(DBConfiguration).filter(
                        DBConfiguration.name == db_model.name,
                        DBConfiguration.is_active == True
                    ).first()
                    
                    if not config:
                        # 如果没有找到配置，尝试创建一个临时配置使用该模型
                        logger.info(f"未找到模型ID {model_id} 的配置，使用单一模型直接调用")
                        # 创建临时步骤
                        steps = [{
                            'model': db_model,
                            'step_type': "both",  # 同时处理思考和执行
                            'system_prompt': "",
                            'tools': tools,
                            'tool_choice': tool_choice,
                            'enable_thinking': enable_thinking,
                            'thinking_budget_tokens': thinking_budget_tokens
                        }]
                        
                        processor = MultiStepModelCollaboration(steps=steps)
                        
                        # 处理请求
                        if stream:
                            return StreamingResponse(
                                processor.process_with_stream(messages),
                                media_type="text/event-stream"
                            )
                        else:
                            response = await processor.process_without_stream(messages)
                            return response
                else:
                    # 如果未找到对应ID的模型，尝试按名称查找配置
                    config = db.query(DBConfiguration).filter(
                        DBConfiguration.name == model,
                        DBConfiguration.is_active == True
                    ).first()
            except ValueError:
                # 如果不是数字，尝试按名称查找配置
                config = db.query(DBConfiguration).filter(
                    DBConfiguration.name == model,
                    DBConfiguration.is_active == True
                ).first()
            
            # 如果仍未找到配置，返回错误
            if not config:
                raise HTTPException(status_code=404, detail=f"No active configuration found for model {model}")
            
            # 获取配置步骤
            steps = db.query(ConfigurationStep).filter(
                ConfigurationStep.configuration_id == config.id
            ).order_by(ConfigurationStep.step_order).all()
            
            if not steps:
                raise HTTPException(status_code=404, detail="Configuration has no steps")
            
            # 更新步骤配置
            steps = [{
                'model': db.query(DBModel).get(step.model_id),
                'step_type': step.step_type,
                'system_prompt': step.system_prompt,
                'tools': tools if step.step_type == "execution" else None,
                'tool_choice': tool_choice if step.step_type == "execution" else None,
                'enable_thinking': enable_thinking,
                'thinking_budget_tokens': thinking_budget_tokens
            } for step in steps]
            
            processor = MultiStepModelCollaboration(steps=steps)
            
            # 获取流式参数
            stream = stream
            
            # 处理请求
            if stream:
                return StreamingResponse(
                    processor.process_with_stream(messages),
                    media_type="text/event-stream"
                )
            else:
                response = await processor.process_without_stream(messages)
                return response
            
    except Exception as e:
        logger.error(f"处理请求时发生错误: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Welcome to DeepGemini API"}


# 添加路由
app.include_router(model_router, prefix="/v1")
app.include_router(configuration_router, prefix="/v1")
app.include_router(api_key_router, prefix="/v1")
app.include_router(auth_router, prefix="/v1")
app.include_router(meeting.router)
app.include_router(roles.router)
app.include_router(discussion_groups.router)
app.include_router(discussions.router)
app.include_router(discussions.router)  # 确保discussions路由已注册

@app.get("/dashboard")
async def dashboard():
    return RedirectResponse(url="/static/index.html", status_code=301)

@app.get("/chat")
async def chat():
    return RedirectResponse(url="/static/chatllm.html", status_code=301)

# 在app/main.py文件中添加一个转换函数
async def convert_coroutine_to_stream(result_or_coroutine):
    """
    将协程或异步迭代器转换为流式响应
    支持多种类型的输入:
    1. 协程 - 会先await获取结果再处理
    2. 异步迭代器 - 直接处理
    3. 普通值 - 直接返回
    """
    # 检查是否为协程
    if hasattr(result_or_coroutine, "__await__") and callable(result_or_coroutine.__await__):
        try:
            # 如果是协程，先获取结果
            logger.info("接收到协程，正在等待其完成...")
            result = await result_or_coroutine
        except Exception as e:
            logger.error(f"等待协程时出错: {str(e)}")
            yield f"错误: {str(e)}"
            return
    else:
        # 如果不是协程，直接使用结果
        logger.info(f"接收到非协程对象，类型: {type(result_or_coroutine).__name__}")
        result = result_or_coroutine
    
    # 处理结果
    if hasattr(result, "__aiter__"):
        # 如果结果是异步迭代器，返回其内容
        logger.info("结果是异步迭代器，开始流式传输...")
        async for chunk in result:
            yield chunk
    else:
        # 如果不是异步迭代器，直接返回结果
        logger.info(f"结果是普通值，类型: {type(result).__name__}")
        yield result

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )