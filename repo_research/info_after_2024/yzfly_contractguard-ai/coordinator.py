import json
import asyncio
from typing import Dict, List, Any
from python_a2a import A2AClient, Message, TextContent, MessageRole
from base_agent import BaseAgent
from config import Config

class ContractCoordinator(BaseAgent):
    """Main coordinator for contract review tasks"""
    
    def __init__(self):
        system_prompt = """你是合同审查系统的主协调器。你的职责是：
1. 接收用户的合同审查请求
2. 将任务分配给专业的智能体团队
3. 协调各个智能体的工作流程
4. 整合所有分析结果
5. 生成最终的综合报告

专业智能体团队包括：
- 文档处理Agent：处理文档解析和文本提取
- 法律Agent：进行法律条款分析和合规检查
- 商业Agent：分析商业条款和风险评估
- 格式Agent：检查文档格式和结构
- 高亮Agent：标注重要条款和风险点
- 整合Agent：生成最终报告

请根据用户请求制定合适的工作流程。"""
        
        super().__init__("ContractCoordinator", system_prompt)
        self.agent_clients = {}
        self.initialize_agent_clients()
    
    def initialize_agent_clients(self):
        """Initialize A2A clients for all specialized agents"""
        for agent_name in ['document', 'legal', 'business', 'format', 'highlight', 'integration']:
            try:
                url = Config.get_agent_url(agent_name)
                self.agent_clients[agent_name] = A2AClient(url)
                self.logger.info(f"Initialized client for {agent_name} at {url}")
            except Exception as e:
                self.logger.error(f"Failed to initialize client for {agent_name}: {e}")
    
    def process_text_message(self, message: Message) -> Message:
        """Process contract review requests"""
        user_text = message.content.text
        self.logger.info(f"Received contract review request: {user_text[:200]}...")
        
        try:
            # Parse the request to determine workflow
            workflow_plan = self.plan_workflow(user_text)
            
            # Execute the workflow
            results = self.execute_workflow(workflow_plan, user_text)
            
            # Generate final response
            final_response = self.generate_final_response(results)
            
            return self.create_response_message(message, final_response)
            
        except Exception as e:
            self.logger.error(f"Error processing request: {str(e)}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            error_response = f"处理合同审查请求时发生错误：{str(e)}"
            
            return self.create_response_message(message, error_response)
    
    def plan_workflow(self, request: str) -> Dict[str, Any]:
        """Plan the workflow based on the request"""
        planning_prompt = f"""
        根据以下合同审查请求，制定一个详细的工作流程计划：
        
        请求：{request}
        
        可用的专业智能体：
        1. document - 文档处理和文本提取
        2. legal - 法律条款分析
        3. business - 商业条款分析
        4. format - 格式检查
        5. highlight - 重点标注
        6. integration - 结果整合
        
        请以JSON格式返回工作流程，包含：
        - steps: 执行步骤列表
        - agents: 每步需要的智能体
        - parallel: 是否可以并行执行
        
        示例格式：
        {{
            "workflow": [
                {{"step": 1, "agent": "document", "task": "解析合同文档", "parallel": false}},
                {{"step": 2, "agents": ["legal", "business"], "task": "并行分析", "parallel": true}},
                {{"step": 3, "agent": "integration", "task": "整合结果", "parallel": false}}
            ]
        }}
        """
        
        workflow_response = self.call_llm(planning_prompt)
        
        try:
            # Try to parse JSON from response
            workflow_data = json.loads(workflow_response)
            return workflow_data
        except json.JSONDecodeError:
            # Fallback to default workflow
            return {
                "workflow": [
                    {"step": 1, "agent": "document", "task": "文档处理", "parallel": False},
                    {"step": 2, "agents": ["legal", "business"], "task": "专业分析", "parallel": True},
                    {"step": 3, "agent": "highlight", "task": "重点标注", "parallel": False},
                    {"step": 4, "agent": "integration", "task": "结果整合", "parallel": False}
                ]
            }
    
    def execute_workflow(self, workflow_plan: Dict[str, Any], original_request: str) -> Dict[str, Any]:
        """Execute the planned workflow"""
        results = {}
        current_context = original_request
        
        for step_info in workflow_plan.get("workflow", []):
            step_num = step_info["step"]
            task_description = step_info["task"]
            
            self.logger.info(f"Executing step {step_num}: {task_description}")
            
            if step_info.get("parallel", False) and "agents" in step_info:
                # Parallel execution
                step_results = self.execute_parallel_step(
                    step_info["agents"], 
                    current_context, 
                    task_description
                )
            else:
                # Sequential execution
                agent_name = step_info["agent"]
                step_results = self.execute_single_step(
                    agent_name, 
                    current_context, 
                    task_description
                )
            
            results[f"step_{step_num}"] = step_results
            
            # Update context with results for next step
            if isinstance(step_results, dict):
                context_update = "\n".join([f"{k}: {v}" for k, v in step_results.items()])
            else:
                context_update = str(step_results)
            
            current_context += f"\n\n步骤{step_num}结果：\n{context_update}"
        
        return results
    
    def execute_single_step(self, agent_name: str, context: str, task: str) -> str:
        """Execute a single agent step"""
        if agent_name not in self.agent_clients:
            return f"Error: Agent {agent_name} not available"
        
        try:
            client = self.agent_clients[agent_name]
            task_message = f"任务：{task}\n\n上下文：{context}"
            
            message = Message(
                content=TextContent(text=task_message),
                role=MessageRole.USER
            )
            
            response = client.send_message(message)
            
            # 安全地处理响应
            if hasattr(response.content, 'text'):
                return response.content.text
            elif hasattr(response.content, 'type') and response.content.type == "error":
                # 安全地获取错误信息
                error_details = []
                for attr in ['message', 'error', 'details', 'description']:
                    if hasattr(response.content, attr):
                        value = getattr(response.content, attr)
                        if value:
                            error_details.append(f"{attr}: {value}")
                
                error_msg = f"Agent {agent_name} returned error: {'; '.join(error_details) if error_details else 'Unknown error'}"
                self.logger.error(error_msg)
                return f"智能体 {agent_name} 执行失败: {error_details[0] if error_details else 'Unknown error'}"
            else:
                error_msg = f"Agent {agent_name} returned unexpected response type: {type(response.content)}"
                self.logger.error(error_msg)
                return f"智能体 {agent_name} 响应异常: {type(response.content)}"
            
        except Exception as e:
            self.logger.error(f"Error executing step with {agent_name}: {e}")
            return f"Error executing {agent_name}: {str(e)}"
    
    def execute_parallel_step(self, agent_names: List[str], context: str, task: str) -> Dict[str, str]:
        """Execute multiple agents in parallel"""
        results = {}
        
        for agent_name in agent_names:
            if agent_name in self.agent_clients:
                result = self.execute_single_step(agent_name, context, task)
                results[agent_name] = result
            else:
                results[agent_name] = f"Agent {agent_name} not available"
        
        return results
    
    def generate_final_response(self, workflow_results: Dict[str, Any]) -> str:
        """Generate final comprehensive response"""
        summary_prompt = f"""
        基于以下工作流程执行结果，生成一份完整的合同审查报告：
        
        执行结果：
        {json.dumps(workflow_results, ensure_ascii=False, indent=2)}
        
        请生成包含以下部分的综合报告：
        1. 执行摘要
        2. 主要发现
        3. 风险评估
        4. 建议措施
        5. 结论
        
        报告应该专业、清晰、可操作。
        """
        
        final_report = self.call_llm(summary_prompt)
        return final_report

if __name__ == "__main__":
    coordinator = ContractCoordinator()
    coordinator.run(Config.AGENT_PORTS["coordinator"])