#!/usr/bin/env python3
"""
独立协调器 - 不依赖其他智能体，自己完成所有分析
"""

import json
import re
from typing import Dict, List, Any
from python_a2a import Message, TextContent, MessageRole
from base_agent import BaseAgent
from config import Config

class StandaloneCoordinator(BaseAgent):
    """独立协调器，集成所有分析功能"""
    
    def __init__(self):
        system_prompt = """你是合同审查系统的智能协调器。你需要对合同进行全面分析，包括：

1. 文档结构分析：识别合同类型、当事人、关键条款等
2. 法律合规分析：检查必要条款、识别法律风险
3. 商业条款分析：评估财务条款、商业价值和风险
4. 格式规范分析：检查文档格式和专业性
5. 重点标注：突出重要条款和风险点
6. 综合评估：给出风险评级和改进建议

请提供专业、全面的合同审查报告。"""
        
        super().__init__("StandaloneCoordinator", system_prompt)
    
    def process_text_message(self, message: Message) -> Message:
        """处理合同审查请求"""
        user_text = message.content.text
        self.logger.info(f"收到合同审查请求: {len(user_text)} 字符")
        
        try:
            # 综合分析
            analysis_result = self.comprehensive_analysis(user_text)
            
            # 格式化最终报告
            final_report = self.format_final_report(analysis_result, user_text)
            
            return self.create_response_message(message, final_report)
            
        except Exception as e:
            self.logger.error(f"处理请求时发生错误: {str(e)}")
            import traceback
            self.logger.error(f"详细错误: {traceback.format_exc()}")
            
            error_response = f"""
合同审查过程中发生技术错误：{str(e)}

请检查：
1. 合同文本格式是否正确
2. 网络连接是否正常
3. 系统资源是否充足

如问题持续，请联系技术支持。
"""
            return self.create_response_message(message, error_response)
    
    def comprehensive_analysis(self, contract_text: str) -> Dict[str, Any]:
        """综合分析合同"""
        
        # 基础信息提取
        basic_info = self.extract_basic_info(contract_text)
        
        # 构建分析提示词
        analysis_prompt = f"""
请对以下合同进行全面专业分析：

合同文本：
{contract_text[:2000]}...

请从以下维度进行分析并以结构化格式返回：

1. 【文档信息】
   - 合同类型
   - 当事人信息
   - 合同金额
   - 履行期限
   - 签署日期

2. 【法律分析】
   - 合规性评估 (1-10分)
   - 主要法律风险
   - 缺失的必要条款
   - 违约责任是否合理

3. 【商业分析】
   - 财务条款评估
   - 商业风险等级 (低/中/高)
   - 投资价值评估
   - 市场条件分析

4. 【格式评估】
   - 文档规范性 (1-10分)
   - 专业程度评估
   - 格式改进建议

5. 【重点关注】
   - 高风险条款 (用⚠️标注)
   - 重要财务条款 (用💰标注)
   - 关键时间节点 (用📅标注)

6. 【综合评估】
   - 整体风险评级 (1-10分，10为最高风险)
   - 主要建议
   - 是否建议签署

请提供专业、详细的分析报告。
"""
        
        # 调用LLM进行分析
        llm_response = self.call_llm(analysis_prompt)
        
        return {
            "basic_info": basic_info,
            "llm_analysis": llm_response,
            "contract_length": len(contract_text),
            "analysis_timestamp": self.get_timestamp()
        }
    
    def extract_basic_info(self, text: str) -> Dict[str, Any]:
        """提取基础信息"""
        info = {
            "contract_type": "未识别",
            "parties": {},
            "amounts": [],
            "dates": [],
            "key_terms": []
        }
        
        # 识别合同类型
        if re.search(r'销售|买卖', text):
            info["contract_type"] = "销售合同"
        elif re.search(r'服务|咨询', text):
            info["contract_type"] = "服务合同"
        elif re.search(r'租赁|出租', text):
            info["contract_type"] = "租赁合同"
        elif re.search(r'合作|协议', text):
            info["contract_type"] = "合作协议"
        
        # 提取当事人
        party_patterns = [
            r'甲方[:：]\s*([^，。；\n]+)',
            r'乙方[:：]\s*([^，。；\n]+)'
        ]
        
        for pattern in party_patterns:
            match = re.search(pattern, text)
            if match:
                if '甲方' in pattern:
                    info["parties"]["甲方"] = match.group(1).strip()
                elif '乙方' in pattern:
                    info["parties"]["乙方"] = match.group(1).strip()
        
        # 提取金额
        amount_patterns = [
            r'([￥$¥]\s*[\d,]+(?:\.\d{2})?)',
            r'([\d,]+(?:\.\d{2})?\s*[元万千万亿])'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            info["amounts"].extend(matches)
        
        # 提取日期
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{4}-\d{1,2}-\d{1,2})'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            info["dates"].extend(matches)
        
        return info
    
    def format_final_report(self, analysis: Dict[str, Any], original_text: str) -> str:
        """格式化最终报告"""
        
        basic_info = analysis["basic_info"]
        
        report = f"""
==================================================
           合同审查综合分析报告
==================================================

📋 基础信息
合同类型：{basic_info["contract_type"]}
文档长度：{analysis["contract_length"]} 字符
分析时间：{analysis["analysis_timestamp"]}

👥 当事人信息
"""
        
        for party, name in basic_info["parties"].items():
            report += f"{party}：{name}\n"
        
        if basic_info["amounts"]:
            report += f"\n💰 涉及金额\n"
            for amount in basic_info["amounts"][:5]:  # 最多显示5个
                report += f"- {amount}\n"
        
        if basic_info["dates"]:
            report += f"\n📅 重要日期\n"
            for date in basic_info["dates"][:5]:  # 最多显示5个
                report += f"- {date}\n"
        
        report += f"""
==================================================
           专业分析结果
==================================================

{analysis["llm_analysis"]}

==================================================
           系统技术信息
==================================================

✅ 分析完成状态：成功
✅ 使用模块：独立智能协调器
✅ 分析覆盖：文档、法律、商业、格式、风险评估
✅ 报告生成：{self.get_timestamp()}

如需更详细的分析或有任何疑问，请提供具体问题进行进一步分析。

==================================================
"""
        
        return report
    
    def get_timestamp(self) -> str:
        """获取时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

if __name__ == "__main__":
    coordinator = StandaloneCoordinator()
    coordinator.run(Config.AGENT_PORTS["coordinator"])