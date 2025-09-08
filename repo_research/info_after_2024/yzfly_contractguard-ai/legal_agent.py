import json
import re
from typing import Dict, List, Any, Optional
from base_agent import BaseAgent
from config import Config

class LegalAgent(BaseAgent):
    """Agent specialized in legal analysis and compliance checking"""
    
    def __init__(self):
        system_prompt = """你是专门进行法律分析的智能体。你的职责包括：

1. 法律条款合规性分析
2. 识别潜在的法律风险
3. 检查必要的法律条款是否完整
4. 分析违约责任和救济措施
5. 检查适用法律和争议解决条款
6. 识别可能存在的法律漏洞

重点关注领域：
- 合同效力要件
- 权利义务平衡性
- 违约责任合理性
- 免责条款的有效性
- 争议解决机制
- 适用法律的明确性
- 强制性法律条款的遵守

你的分析应该：
- 准确识别法律风险
- 提供具体的改进建议
- 评估风险等级
- 引用相关法律法规（如果适用）
- 为其他智能体提供法律背景信息"""
        
        super().__init__("LegalAgent", system_prompt)
        self.legal_risk_categories = self.initialize_risk_categories()
    
    def initialize_risk_categories(self) -> Dict[str, List[str]]:
        """Initialize legal risk categories and keywords"""
        return {
            "合同效力风险": [
                "无效", "可撤销", "效力", "签字", "盖章", "授权", "代表权"
            ],
            "违约责任风险": [
                "违约金", "损害赔偿", "违约责任", "免责", "责任限制", "不可抗力"
            ],
            "争议解决风险": [
                "仲裁", "诉讼", "管辖", "适用法律", "争议解决", "调解"
            ],
            "履行风险": [
                "履行期限", "履行方式", "履行地点", "验收", "交付", "付款"
            ],
            "权利义务风险": [
                "权利", "义务", "责任", "保证", "承诺", "声明"
            ],
            "终止解除风险": [
                "终止", "解除", "提前终止", "单方解除", "协议解除"
            ]
        }
    
    def process_text_message(self, message):
        """Process legal analysis requests"""
        user_text = message.content.text
        self.logger.info("Processing legal analysis request")
        
        try:
            # Extract task and content
            task_info = self.extract_task_info(user_text)
            document_content = task_info.get("content", user_text)
            
            # Perform legal analysis
            legal_analysis = self.perform_legal_analysis(document_content)
            
            # Format response
            response_text = self.format_legal_analysis(legal_analysis)
            
            return self.create_response_message(message, response_text)
            
        except Exception as e:
            self.logger.error(f"Error in legal analysis: {str(e)}")
            error_response = f"法律分析过程中发生错误：{str(e)}"
            return self.create_response_message(message, error_response)
    
    def extract_task_info(self, text: str) -> Dict[str, Any]:
        """Extract task information from the input text"""
        lines = text.split('\n')
        task_info = {"content": text}
        
        for line in lines:
            if line.startswith("任务："):
                task_info["task"] = line.replace("任务：", "").strip()
            elif line.startswith("上下文："):
                context_start = text.find("上下文：")
                if context_start != -1:
                    task_info["content"] = text[context_start + 4:].strip()
                break
        
        return task_info
    
    def perform_legal_analysis(self, document_text: str) -> Dict[str, Any]:
        """Perform comprehensive legal analysis"""
        analysis = {
            "risk_assessment": self.assess_legal_risks(document_text),
            "compliance_check": self.check_compliance(document_text),
            "clause_analysis": self.analyze_key_clauses(document_text),
            "validity_check": self.check_contract_validity(document_text),
            "dispute_resolution": self.analyze_dispute_resolution(document_text),
            "liability_analysis": self.analyze_liability_terms(document_text),
            "recommendations": self.generate_legal_recommendations(document_text)
        }
        
        # Get detailed analysis from LLM
        llm_analysis = self.get_llm_legal_analysis(document_text)
        analysis["detailed_analysis"] = llm_analysis
        
        return analysis
    
    def assess_legal_risks(self, text: str) -> Dict[str, Any]:
        """Assess legal risks in the contract"""
        risks = {
            "high_risk": [],
            "medium_risk": [],
            "low_risk": [],
            "risk_score": 0
        }
        
        total_risk_score = 0
        
        for risk_category, keywords in self.legal_risk_categories.items():
            category_risk = self.evaluate_category_risk(text, risk_category, keywords)
            
            if category_risk["score"] >= 8:
                risks["high_risk"].append(category_risk)
                total_risk_score += category_risk["score"]
            elif category_risk["score"] >= 5:
                risks["medium_risk"].append(category_risk)
                total_risk_score += category_risk["score"]
            elif category_risk["score"] > 0:
                risks["low_risk"].append(category_risk)
                total_risk_score += category_risk["score"]
        
        risks["risk_score"] = min(total_risk_score // len(self.legal_risk_categories), 10)
        
        return risks
    
    def evaluate_category_risk(self, text: str, category: str, keywords: List[str]) -> Dict[str, Any]:
        """Evaluate risk for a specific category"""
        risk_info = {
            "category": category,
            "score": 0,
            "issues": [],
            "keywords_found": []
        }
        
        text_lower = text.lower()
        
        # Check for presence of keywords
        for keyword in keywords:
            if keyword in text:
                risk_info["keywords_found"].append(keyword)
        
        # Specific risk evaluation logic for each category
        if category == "合同效力风险":
            risk_info["score"] = self.evaluate_validity_risk(text)
            risk_info["issues"] = self.find_validity_issues(text)
        
        elif category == "违约责任风险":
            risk_info["score"] = self.evaluate_liability_risk(text)
            risk_info["issues"] = self.find_liability_issues(text)
        
        elif category == "争议解决风险":
            risk_info["score"] = self.evaluate_dispute_risk(text)
            risk_info["issues"] = self.find_dispute_issues(text)
        
        else:
            # General risk scoring based on keyword presence
            risk_info["score"] = min(len(risk_info["keywords_found"]) * 2, 10)
        
        return risk_info
    
    def evaluate_validity_risk(self, text: str) -> int:
        """Evaluate contract validity risks"""
        risk_score = 0
        
        # Check for essential elements
        if not re.search(r'甲方|乙方|第一方|第二方', text):
            risk_score += 3  # Missing parties
        
        if not re.search(r'签字|签名|盖章', text):
            risk_score += 2  # Missing signature requirements
        
        if not re.search(r'\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{1,2}-\d{1,2}', text):
            risk_score += 1  # Missing dates
        
        # Check for void terms
        void_terms = ['违法', '违规', '无效', '欺诈']
        for term in void_terms:
            if term in text:
                risk_score += 2
        
        return min(risk_score, 10)
    
    def find_validity_issues(self, text: str) -> List[str]:
        """Find specific validity issues"""
        issues = []
        
        # Check party identification
        parties = re.findall(r'(甲方|乙方)[:：]\s*([^，。；\n]+)', text)
        if len(parties) < 2:
            issues.append("合同当事人信息不完整")
        
        # Check signature requirements
        if not re.search(r'签字|签名|盖章', text):
            issues.append("缺少签署要求条款")
        
        # Check effective date
        if not re.search(r'生效|生效日期|生效时间', text):
            issues.append("缺少生效条件或日期")
        
        return issues
    
    def evaluate_liability_risk(self, text: str) -> int:
        """Evaluate liability and breach risks"""
        risk_score = 0
        
        # Check for excessive penalties
        if re.search(r'违约金.*?100%|违约金.*?全部', text):
            risk_score += 4  # Excessive penalty clauses
        
        # Check for unfair liability distribution
        if text.count('甲方不承担') > text.count('乙方不承担'):
            risk_score += 2  # Unbalanced liability
        
        # Check for force majeure clauses
        if not re.search(r'不可抗力|force majeure', text, re.IGNORECASE):
            risk_score += 1  # Missing force majeure
        
        return min(risk_score, 10)
    
    def find_liability_issues(self, text: str) -> List[str]:
        """Find specific liability issues"""
        issues = []
        
        # Check penalty clauses
        if not re.search(r'违约金|违约责任', text):
            issues.append("缺少违约责任条款")
        
        # Check liability limitations
        if re.search(r'不承担任何责任|免除全部责任', text):
            issues.append("存在过度免责条款")
        
        # Check force majeure
        if not re.search(r'不可抗力', text):
            issues.append("缺少不可抗力条款")
        
        return issues
    
    def evaluate_dispute_risk(self, text: str) -> int:
        """Evaluate dispute resolution risks"""
        risk_score = 0
        
        # Check for dispute resolution clause
        if not re.search(r'争议|纠纷|仲裁|诉讼|管辖', text):
            risk_score += 3  # No dispute resolution clause
        
        # Check for unclear jurisdiction
        if re.search(r'争议', text) and not re.search(r'管辖|法院|仲裁', text):
            risk_score += 2  # Unclear jurisdiction
        
        return min(risk_score, 10)
    
    def find_dispute_issues(self, text: str) -> List[str]:
        """Find specific dispute resolution issues"""
        issues = []
        
        if not re.search(r'争议.*?解决|纠纷.*?处理', text):
            issues.append("缺少争议解决条款")
        
        if not re.search(r'管辖|法院|仲裁委员会', text):
            issues.append("管辖权或仲裁机构不明确")
        
        if not re.search(r'适用.*?法律|适用.*?法规', text):
            issues.append("适用法律不明确")
        
        return issues
    
    def check_compliance(self, text: str) -> Dict[str, Any]:
        """Check compliance with legal requirements"""
        compliance = {
            "required_clauses": self.check_required_clauses(text),
            "prohibited_terms": self.check_prohibited_terms(text),
            "format_compliance": self.check_format_compliance(text),
            "compliance_score": 0
        }
        
        # Calculate compliance score
        total_checks = len(compliance["required_clauses"]) + len(compliance["prohibited_terms"])
        passed_checks = sum(1 for clause in compliance["required_clauses"] if clause["present"]) + \
                       sum(1 for term in compliance["prohibited_terms"] if not term["found"])
        
        compliance["compliance_score"] = int((passed_checks / total_checks * 10)) if total_checks > 0 else 10
        
        return compliance
    
    def check_required_clauses(self, text: str) -> List[Dict[str, Any]]:
        """Check for required legal clauses"""
        required_clauses = [
            {"name": "当事人信息", "pattern": r"甲方|乙方", "present": False},
            {"name": "合同标的", "pattern": r"标的|合同内容|服务内容", "present": False},
            {"name": "履行期限", "pattern": r"期限|完成时间|交付时间", "present": False},
            {"name": "价款或报酬", "pattern": r"价款|费用|报酬|金额", "present": False},
            {"name": "违约责任", "pattern": r"违约|违约责任|违约金", "present": False},
            {"name": "争议解决", "pattern": r"争议|纠纷|仲裁|诉讼", "present": False}
        ]
        
        for clause in required_clauses:
            if re.search(clause["pattern"], text):
                clause["present"] = True
        
        return required_clauses
    
    def check_prohibited_terms(self, text: str) -> List[Dict[str, Any]]:
        """Check for prohibited or risky terms"""
        prohibited_terms = [
            {"name": "霸王条款", "pattern": r"不得.*?任何.*?异议|必须.*?无条件", "found": False},
            {"name": "过度免责", "pattern": r"不承担任何责任|免除全部责任", "found": False},
            {"name": "不公平条款", "pattern": r"单方.*?决定|最终解释权", "found": False},
            {"name": "违法内容", "pattern": r"规避.*?法律|违反.*?规定", "found": False}
        ]
        
        for term in prohibited_terms:
            if re.search(term["pattern"], text):
                term["found"] = True
        
        return prohibited_terms
    
    def check_format_compliance(self, text: str) -> Dict[str, bool]:
        """Check format compliance requirements"""
        return {
            "has_title": bool(re.search(r'^.{1,50}(合同|协议|契约)', text, re.MULTILINE)),
            "has_parties": bool(re.search(r'甲方|乙方', text)),
            "has_date": bool(re.search(r'\d{4}年\d{1,2}月\d{1,2}日', text)),
            "has_signature_area": bool(re.search(r'签字|签名|盖章', text))
        }
    
    def analyze_key_clauses(self, text: str) -> Dict[str, Any]:
        """Analyze key legal clauses"""
        key_clauses = {
            "payment_terms": self.extract_payment_clauses(text),
            "termination_clauses": self.extract_termination_clauses(text),
            "liability_clauses": self.extract_liability_clauses(text),
            "confidentiality_clauses": self.extract_confidentiality_clauses(text)
        }
        
        return key_clauses
    
    def extract_payment_clauses(self, text: str) -> List[str]:
        """Extract payment-related clauses"""
        payment_clauses = []
        lines = text.split('\n')
        
        payment_keywords = ['支付', '付款', '结算', '费用', '价款', '报酬']
        
        for line in lines:
            if any(keyword in line for keyword in payment_keywords):
                payment_clauses.append(line.strip())
        
        return payment_clauses
    
    def extract_termination_clauses(self, text: str) -> List[str]:
        """Extract termination-related clauses"""
        termination_clauses = []
        lines = text.split('\n')
        
        termination_keywords = ['终止', '解除', '到期', '期满', '提前终止']
        
        for line in lines:
            if any(keyword in line for keyword in termination_keywords):
                termination_clauses.append(line.strip())
        
        return termination_clauses
    
    def extract_liability_clauses(self, text: str) -> List[str]:
        """Extract liability-related clauses"""
        liability_clauses = []
        lines = text.split('\n')
        
        liability_keywords = ['责任', '违约', '赔偿', '损失', '免责']
        
        for line in lines:
            if any(keyword in line for keyword in liability_keywords):
                liability_clauses.append(line.strip())
        
        return liability_clauses
    
    def extract_confidentiality_clauses(self, text: str) -> List[str]:
        """Extract confidentiality-related clauses"""
        confidentiality_clauses = []
        lines = text.split('\n')
        
        confidentiality_keywords = ['保密', '机密', '泄露', '披露', '商业秘密']
        
        for line in lines:
            if any(keyword in line for keyword in confidentiality_keywords):
                confidentiality_clauses.append(line.strip())
        
        return confidentiality_clauses
    
    def check_contract_validity(self, text: str) -> Dict[str, Any]:
        """Check overall contract validity"""
        validity = {
            "essential_elements": self.check_essential_elements(text),
            "legal_capacity": self.check_legal_capacity(text),
            "lawful_content": self.check_lawful_content(text),
            "valid_form": self.check_valid_form(text),
            "validity_score": 0
        }
        
        # Calculate validity score
        scores = [v.get("score", 0) for v in validity.values() if isinstance(v, dict) and "score" in v]
        validity["validity_score"] = sum(scores) // len(scores) if scores else 0
        
        return validity
    
    def check_essential_elements(self, text: str) -> Dict[str, Any]:
        """Check essential elements of contract"""
        elements = {
            "parties": bool(re.search(r'甲方|乙方', text)),
            "subject_matter": bool(re.search(r'标的|内容|服务', text)),
            "consideration": bool(re.search(r'价款|费用|报酬', text)),
            "score": 0
        }
        
        elements["score"] = sum(elements[k] for k in elements if k != "score") * 3
        return elements
    
    def check_legal_capacity(self, text: str) -> Dict[str, Any]:
        """Check legal capacity indicators"""
        capacity = {
            "corporate_entities": bool(re.search(r'公司|企业|法人', text)),
            "authorization": bool(re.search(r'授权|代表|法定代表人', text)),
            "score": 5  # Default score, would need more sophisticated analysis
        }
        
        return capacity
    
    def check_lawful_content(self, text: str) -> Dict[str, Any]:
        """Check for lawful content"""
        lawfulness = {
            "no_illegal_terms": not bool(re.search(r'违法|非法|欺诈', text)),
            "no_prohibited_activities": not bool(re.search(r'洗钱|走私|贩毒', text)),
            "score": 8  # Default high score
        }
        
        if not lawfulness["no_illegal_terms"]:
            lawfulness["score"] -= 3
        if not lawfulness["no_prohibited_activities"]:
            lawfulness["score"] -= 5
        
        return lawfulness
    
    def check_valid_form(self, text: str) -> Dict[str, Any]:
        """Check contract form validity"""
        form_validity = {
            "written_form": True,  # Assuming it's written since we have text
            "signatures_required": bool(re.search(r'签字|签名|盖章', text)),
            "proper_format": bool(re.search(r'合同|协议', text)),
            "score": 7
        }
        
        return form_validity
    
    def analyze_dispute_resolution(self, text: str) -> Dict[str, Any]:
        """Analyze dispute resolution mechanisms"""
        dispute_analysis = {
            "has_dispute_clause": bool(re.search(r'争议|纠纷', text)),
            "resolution_method": self.identify_resolution_method(text),
            "jurisdiction": self.identify_jurisdiction(text),
            "applicable_law": self.identify_applicable_law(text),
            "completeness_score": 0
        }
        
        # Score based on completeness
        score = 0
        if dispute_analysis["has_dispute_clause"]:
            score += 3
        if dispute_analysis["resolution_method"]:
            score += 2
        if dispute_analysis["jurisdiction"]:
            score += 3
        if dispute_analysis["applicable_law"]:
            score += 2
        
        dispute_analysis["completeness_score"] = score
        
        return dispute_analysis
    
    def identify_resolution_method(self, text: str) -> str:
        """Identify dispute resolution method"""
        if re.search(r'仲裁', text):
            return "仲裁"
        elif re.search(r'诉讼|法院', text):
            return "诉讼"
        elif re.search(r'调解', text):
            return "调解"
        else:
            return "未明确"
    
    def identify_jurisdiction(self, text: str) -> str:
        """Identify jurisdiction or court"""
        jurisdiction_match = re.search(r'(.*?)(法院|仲裁委员会)', text)
        if jurisdiction_match:
            return jurisdiction_match.group(0)
        else:
            return "未明确"
    
    def identify_applicable_law(self, text: str) -> str:
        """Identify applicable law"""
        law_match = re.search(r'适用.*?(法律|法规)', text)
        if law_match:
            return law_match.group(0)
        else:
            return "未明确"
    
    def analyze_liability_terms(self, text: str) -> Dict[str, Any]:
        """Analyze liability and penalty terms"""
        liability_analysis = {
            "breach_penalties": self.extract_breach_penalties(text),
            "limitation_of_liability": self.extract_liability_limitations(text),
            "force_majeure": self.check_force_majeure_clause(text),
            "liability_balance": self.assess_liability_balance(text)
        }
        
        return liability_analysis
    
    def extract_breach_penalties(self, text: str) -> List[Dict[str, str]]:
        """Extract breach penalty clauses"""
        penalties = []
        lines = text.split('\n')
        
        for line in lines:
            if re.search(r'违约金|赔偿.*?损失', line):
                penalty_info = {
                    "clause": line.strip(),
                    "type": "违约金" if "违约金" in line else "损害赔偿"
                }
                penalties.append(penalty_info)
        
        return penalties
    
    def extract_liability_limitations(self, text: str) -> List[str]:
        """Extract liability limitation clauses"""
        limitations = []
        lines = text.split('\n')
        
        limitation_keywords = ['免责', '不承担责任', '责任限制', '最大责任']
        
        for line in lines:
            if any(keyword in line for keyword in limitation_keywords):
                limitations.append(line.strip())
        
        return limitations
    
    def check_force_majeure_clause(self, text: str) -> Dict[str, Any]:
        """Check force majeure clause"""
        force_majeure = {
            "present": bool(re.search(r'不可抗力|force majeure', text, re.IGNORECASE)),
            "clause": "",
            "completeness": "incomplete"
        }
        
        if force_majeure["present"]:
            fm_match = re.search(r'[^。]*不可抗力[^。]*。', text)
            if fm_match:
                force_majeure["clause"] = fm_match.group(0)
                # Check completeness
                if re.search(r'通知|减轻|证明', force_majeure["clause"]):
                    force_majeure["completeness"] = "complete"
        
        return force_majeure
    
    def assess_liability_balance(self, text: str) -> Dict[str, Any]:
        """Assess balance of liability between parties"""
        balance = {
            "party_a_obligations": len(re.findall(r'甲方.*?(应当|必须|承担)', text)),
            "party_b_obligations": len(re.findall(r'乙方.*?(应当|必须|承担)', text)),
            "balance_ratio": 0,
            "assessment": "balanced"
        }
        
        total_obligations = balance["party_a_obligations"] + balance["party_b_obligations"]
        if total_obligations > 0:
            balance["balance_ratio"] = balance["party_a_obligations"] / total_obligations
            
            if balance["balance_ratio"] < 0.3 or balance["balance_ratio"] > 0.7:
                balance["assessment"] = "unbalanced"
        
        return balance
    
    def get_llm_legal_analysis(self, text: str) -> str:
        """Get detailed legal analysis from LLM"""
        analysis_prompt = f"""
        请对以下合同文本进行专业的法律分析：
        
        合同文本：{text[:1500]}...
        
        请从以下角度进行分析：
        1. 合同的法律效力评估
        2. 主要法律风险识别
        3. 条款的合法性和合理性
        4. 违约责任和救济措施的适当性
        5. 争议解决机制的有效性
        6. 需要补充或修改的条款
        
        请提供具体、专业的法律意见和建议。
        """
        
        return self.call_llm(analysis_prompt)
    
    def generate_legal_recommendations(self, text: str) -> List[Dict[str, str]]:
        """Generate legal recommendations"""
        recommendations = []
        
        # Check for missing clauses
        if not re.search(r'不可抗力', text):
            recommendations.append({
                "type": "补充条款",
                "priority": "中",
                "recommendation": "建议添加不可抗力条款，明确不可抗力事件的定义、通知义务和责任减免"
            })
        
        if not re.search(r'保密', text):
            recommendations.append({
                "type": "补充条款",
                "priority": "中",
                "recommendation": "建议添加保密条款，保护双方商业信息和技术秘密"
            })
        
        # Check for risky clauses
        if re.search(r'不承担任何责任|免除全部责任', text):
            recommendations.append({
                "type": "修改条款",
                "priority": "高",
                "recommendation": "过度免责条款可能无效，建议修改为合理的责任限制条款"
            })
        
        if not re.search(r'争议.*?解决', text):
            recommendations.append({
                "type": "补充条款",
                "priority": "高",
                "recommendation": "缺少争议解决条款，建议明确争议解决方式、管辖权和适用法律"
            })
        
        return recommendations
    
    def format_legal_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format legal analysis results for output"""
        output = "=== 法律分析报告 ===\n\n"
        
        # Risk Assessment
        risk_assessment = analysis.get("risk_assessment", {})
        output += f"法律风险评分：{risk_assessment.get('risk_score', 0)}/10\n\n"
        
        # High Risk Issues
        high_risks = risk_assessment.get("high_risk", [])
        if high_risks:
            output += "--- 高风险问题 ---\n"
            for risk in high_risks:
                output += f"• {risk['category']}：风险分数 {risk['score']}/10\n"
                for issue in risk.get("issues", []):
                    output += f"  - {issue}\n"
            output += "\n"
        
        # Compliance Check
        compliance = analysis.get("compliance_check", {})
        output += f"合规性评分：{compliance.get('compliance_score', 0)}/10\n"
        
        required_clauses = compliance.get("required_clauses", [])
        missing_clauses = [clause["name"] for clause in required_clauses if not clause["present"]]
        if missing_clauses:
            output += f"缺失必要条款：{', '.join(missing_clauses)}\n"
        
        # Contract Validity
        validity = analysis.get("validity_check", {})
        output += f"合同效力评分：{validity.get('validity_score', 0)}/10\n\n"
        
        # Dispute Resolution
        dispute = analysis.get("dispute_resolution", {})
        output += "--- 争议解决机制 ---\n"
        output += f"解决方式：{dispute.get('resolution_method', '未明确')}\n"
        output += f"管辖权：{dispute.get('jurisdiction', '未明确')}\n"
        output += f"适用法律：{dispute.get('applicable_law', '未明确')}\n"
        output += f"完整性评分：{dispute.get('completeness_score', 0)}/10\n\n"
        
        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            output += "--- 法律建议 ---\n"
            for i, rec in enumerate(recommendations, 1):
                output += f"{i}. [{rec['priority']}] {rec['recommendation']}\n"
            output += "\n"
        
        # Detailed Analysis
        detailed_analysis = analysis.get("detailed_analysis", "")
        if detailed_analysis:
            output += "--- 详细分析 ---\n"
            output += detailed_analysis
        
        return output

if __name__ == "__main__":
    agent = LegalAgent()
    agent.run(Config.AGENT_PORTS["legal"])