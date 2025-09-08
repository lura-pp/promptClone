import json
import re
from typing import Dict, List, Any, Optional
from base_agent import BaseAgent
from config import Config

class BusinessAgent(BaseAgent):
    """Agent specialized in business terms and commercial analysis"""
    
    def __init__(self):
        system_prompt = """你是专门进行商业条款分析的智能体。你的职责包括：

1. 商业条款和商务条件分析
2. 财务风险评估和成本效益分析
3. 市场价格合理性评估
4. 商业模式和盈利能力分析
5. 竞争优势和市场地位评估
6. 业务流程和运营风险分析

重点分析领域：
- 价格条款和支付条件
- 交付条件和履行方式
- 质量标准和验收条件
- 售后服务和维护条款
- 市场竞争和商业机会
- 财务指标和投资回报
- 运营效率和成本控制
- 风险管控和应急预案

你的分析应该：
- 从商业角度评估合同的合理性
- 识别商业机会和风险
- 提供市场导向的建议
- 评估财务影响和投资价值
- 为决策提供商业智慧支持"""
        
        super().__init__("BusinessAgent", system_prompt)
        self.business_metrics = self.initialize_business_metrics()
    
    def initialize_business_metrics(self) -> Dict[str, List[str]]:
        """Initialize business analysis metrics and keywords"""
        return {
            "财务条款": [
                "价格", "费用", "成本", "预算", "利润", "收益", "投资", "回报"
            ],
            "支付条件": [
                "支付", "付款", "结算", "预付", "分期", "押金", "保证金", "尾款"
            ],
            "交付条款": [
                "交付", "发货", "运输", "物流", "仓储", "包装", "验收", "签收"
            ],
            "质量标准": [
                "质量", "标准", "规格", "检验", "测试", "认证", "合格", "缺陷"
            ],
            "服务条款": [
                "服务", "维护", "技术支持", "培训", "安装", "调试", "升级"
            ],
            "市场条款": [
                "市场", "销售", "推广", "渠道", "客户", "竞争", "独家", "区域"
            ],
            "风险管控": [
                "风险", "保险", "担保", "抵押", "违约", "赔偿", "损失", "补偿"
            ],
            "绩效指标": [
                "KPI", "指标", "目标", "业绩", "考核", "评估", "奖励", "激励"
            ]
        }
    
    def process_text_message(self, message):
        """Process business analysis requests"""
        user_text = message.content.text
        self.logger.info("Processing business analysis request")
        
        try:
            # Extract task and content
            task_info = self.extract_task_info(user_text)
            document_content = task_info.get("content", user_text)
            
            # Perform business analysis
            business_analysis = self.perform_business_analysis(document_content)
            
            # Format response
            response_text = self.format_business_analysis(business_analysis)
            
            return self.create_response_message(message, response_text)
            
        except Exception as e:
            self.logger.error(f"Error in business analysis: {str(e)}")
            error_response = f"商业分析过程中发生错误：{str(e)}"
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
    
    def perform_business_analysis(self, document_text: str) -> Dict[str, Any]:
        """Perform comprehensive business analysis"""
        analysis = {
            "financial_analysis": self.analyze_financial_terms(document_text),
            "commercial_risks": self.assess_commercial_risks(document_text),
            "market_analysis": self.analyze_market_conditions(document_text),
            "operational_analysis": self.analyze_operational_aspects(document_text),
            "performance_metrics": self.analyze_performance_metrics(document_text),
            "business_value": self.assess_business_value(document_text),
            "recommendations": self.generate_business_recommendations(document_text)
        }
        
        # Get detailed analysis from LLM
        llm_analysis = self.get_llm_business_analysis(document_text)
        analysis["detailed_analysis"] = llm_analysis
        
        return analysis
    
    def analyze_financial_terms(self, text: str) -> Dict[str, Any]:
        """Analyze financial terms and conditions"""
        financial_analysis = {
            "pricing_structure": self.analyze_pricing_structure(text),
            "payment_terms": self.analyze_payment_terms(text),
            "cost_implications": self.analyze_cost_implications(text),
            "financial_risks": self.identify_financial_risks(text),
            "roi_potential": self.assess_roi_potential(text)
        }
        
        return financial_analysis
    
    def analyze_pricing_structure(self, text: str) -> Dict[str, Any]:
        """Analyze pricing structure and competitiveness"""
        pricing = {
            "amounts_found": [],
            "pricing_model": "未明确",
            "price_competitiveness": "待评估",
            "currency": "未明确"
        }
        
        # Extract monetary amounts
        amount_patterns = [
            r'([￥$¥]\s*[\d,]+(?:\.\d{2})?)',
            r'([\d,]+(?:\.\d{2})?\s*[元万千万亿])',
            r'([一二三四五六七八九十百千万亿]+[元万千万亿])'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            pricing["amounts_found"].extend(matches)
        
        # Identify pricing model
        if re.search(r'单价|每.*?元|价格.*?元', text):
            pricing["pricing_model"] = "单价定价"
        elif re.search(r'总价|总计.*?元|合计.*?元', text):
            pricing["pricing_model"] = "总价定价"
        elif re.search(r'分期|阶段.*?付款', text):
            pricing["pricing_model"] = "分期定价"
        
        # Identify currency
        if re.search(r'人民币|元|￥', text):
            pricing["currency"] = "人民币"
        elif re.search(r'美元|\$|USD', text):
            pricing["currency"] = "美元"
        
        return pricing
    
    def analyze_payment_terms(self, text: str) -> Dict[str, Any]:
        """Analyze payment terms and cash flow implications"""
        payment_analysis = {
            "payment_schedule": self.extract_payment_schedule(text),
            "payment_methods": self.extract_payment_methods(text),
            "credit_terms": self.analyze_credit_terms(text),
            "cash_flow_impact": self.assess_cash_flow_impact(text)
        }
        
        return payment_analysis
    
    def extract_payment_schedule(self, text: str) -> List[Dict[str, str]]:
        """Extract payment schedule information"""
        schedule = []
        lines = text.split('\n')
        
        payment_keywords = ['预付', '首付', '进度款', '尾款', '分期', '按月', '按季度', '按年']
        
        for line in lines:
            for keyword in payment_keywords:
                if keyword in line:
                    schedule.append({
                        "type": keyword,
                        "description": line.strip()
                    })
                    break
        
        return schedule
    
    def extract_payment_methods(self, text: str) -> List[str]:
        """Extract payment methods"""
        methods = []
        method_keywords = ['银行转账', '现金', '支票', '承兑汇票', '信用证', '电汇', '网银']
        
        for method in method_keywords:
            if method in text:
                methods.append(method)
        
        return methods
    
    def analyze_credit_terms(self, text: str) -> Dict[str, Any]:
        """Analyze credit terms and conditions"""
        credit_terms = {
            "credit_period": "未明确",
            "credit_limit": "未明确",
            "early_payment_discount": False,
            "late_payment_penalty": False
        }
        
        # Extract credit period
        credit_match = re.search(r'(\d+)天.*?付款|(\d+)日.*?内.*?支付', text)
        if credit_match:
            days = credit_match.group(1) or credit_match.group(2)
            credit_terms["credit_period"] = f"{days}天"
        
        # Check for discounts and penalties
        if re.search(r'提前.*?优惠|早付.*?折扣', text):
            credit_terms["early_payment_discount"] = True
        
        if re.search(r'逾期.*?利息|延期.*?费用|滞纳金', text):
            credit_terms["late_payment_penalty"] = True
        
        return credit_terms
    
    def assess_cash_flow_impact(self, text: str) -> Dict[str, Any]:
        """Assess cash flow impact"""
        cash_flow = {
            "upfront_payment_required": False,
            "payment_distribution": "均匀分布",
            "working_capital_impact": "中等",
            "liquidity_requirements": "标准"
        }
        
        # Check for upfront payments
        if re.search(r'预付|首付|定金|保证金', text):
            cash_flow["upfront_payment_required"] = True
            cash_flow["working_capital_impact"] = "较高"
        
        # Analyze payment distribution
        payment_terms = len(re.findall(r'分期|阶段|批次', text))
        if payment_terms > 2:
            cash_flow["payment_distribution"] = "分散分布"
            cash_flow["liquidity_requirements"] = "较低"
        elif payment_terms == 0:
            cash_flow["payment_distribution"] = "一次性支付"
            cash_flow["liquidity_requirements"] = "较高"
        
        return cash_flow
    
    def analyze_cost_implications(self, text: str) -> Dict[str, Any]:
        """Analyze cost implications and hidden costs"""
        cost_analysis = {
            "direct_costs": self.extract_direct_costs(text),
            "indirect_costs": self.identify_indirect_costs(text),
            "variable_costs": self.identify_variable_costs(text),
            "cost_escalation": self.check_cost_escalation(text)
        }
        
        return cost_analysis
    
    def extract_direct_costs(self, text: str) -> List[Dict[str, str]]:
        """Extract direct costs"""
        direct_costs = []
        lines = text.split('\n')
        
        cost_keywords = ['费用', '成本', '价格', '金额', '报酬', '服务费']
        
        for line in lines:
            if any(keyword in line for keyword in cost_keywords):
                # Extract amount if present
                amount_match = re.search(r'[\d,]+(?:\.\d{2})?\s*[元万千万亿]', line)
                direct_costs.append({
                    "description": line.strip(),
                    "amount": amount_match.group(0) if amount_match else "未明确"
                })
        
        return direct_costs
    
    def identify_indirect_costs(self, text: str) -> List[str]:
        """Identify potential indirect costs"""
        indirect_costs = []
        
        indirect_keywords = {
            '运输费': ['运输', '物流', '快递', '邮费'],
            '保险费': ['保险', '投保'],
            '税费': ['税', '税费', '增值税', '所得税'],
            '手续费': ['手续费', '服务费', '管理费'],
            '维护费': ['维护', '保养', '维修'],
            '培训费': ['培训', '学习', '教育']
        }
        
        for cost_type, keywords in indirect_keywords.items():
            if any(keyword in text for keyword in keywords):
                indirect_costs.append(cost_type)
        
        return indirect_costs
    
    def identify_variable_costs(self, text: str) -> List[str]:
        """Identify variable costs"""
        variable_costs = []
        
        if re.search(r'按.*?计费|根据.*?收费|浮动.*?价格', text):
            variable_costs.append("浮动计费")
        
        if re.search(r'超出.*?费用|额外.*?成本', text):
            variable_costs.append("超量费用")
        
        if re.search(r'加急.*?费|紧急.*?费', text):
            variable_costs.append("加急费用")
        
        return variable_costs
    
    def check_cost_escalation(self, text: str) -> Dict[str, Any]:
        """Check for cost escalation clauses"""
        escalation = {
            "has_escalation_clause": False,
            "escalation_basis": "未明确",
            "frequency": "未明确",
            "cap": "未明确"
        }
        
        if re.search(r'调价|价格.*?调整|费用.*?变动', text):
            escalation["has_escalation_clause"] = True
            
            if re.search(r'年度|每年', text):
                escalation["frequency"] = "年度调整"
            elif re.search(r'季度|每季', text):
                escalation["frequency"] = "季度调整"
            
            if re.search(r'CPI|物价指数|通胀', text):
                escalation["escalation_basis"] = "物价指数"
            elif re.search(r'市场价格|市场价', text):
                escalation["escalation_basis"] = "市场价格"
        
        return escalation
    
    def identify_financial_risks(self, text: str) -> List[Dict[str, str]]:
        """Identify financial risks"""
        risks = []
        
        # Currency risk
        if re.search(r'美元|外币|汇率', text):
            risks.append({
                "type": "汇率风险",
                "description": "涉及外币交易，存在汇率波动风险",
                "severity": "中"
            })
        
        # Credit risk
        if not re.search(r'保证金|担保|抵押', text):
            risks.append({
                "type": "信用风险",
                "description": "缺少信用保障措施",
                "severity": "中"
            })
        
        # Liquidity risk
        if re.search(r'大额.*?预付|巨额.*?首付', text):
            risks.append({
                "type": "流动性风险",
                "description": "需要大额预付款，影响资金流动性",
                "severity": "高"
            })
        
        # Price volatility risk
        if re.search(r'原材料.*?价格|市场.*?波动', text):
            risks.append({
                "type": "价格波动风险",
                "description": "原材料或市场价格波动可能影响成本",
                "severity": "中"
            })
        
        return risks
    
    def assess_roi_potential(self, text: str) -> Dict[str, Any]:
        """Assess return on investment potential"""
        roi_assessment = {
            "revenue_potential": "待评估",
            "cost_benefit_ratio": "待计算",
            "payback_period": "未明确",
            "long_term_value": "待评估"
        }
        
        # Look for revenue indicators
        if re.search(r'销售|收入|盈利|利润', text):
            roi_assessment["revenue_potential"] = "有明确收入预期"
        
        # Look for investment period
        period_match = re.search(r'(\d+)年|(\d+)个月', text)
        if period_match:
            period = period_match.group(1) or period_match.group(2)
            roi_assessment["payback_period"] = f"约{period}{'年' if period_match.group(1) else '个月'}"
        
        return roi_assessment
    
    def assess_commercial_risks(self, text: str) -> Dict[str, Any]:
        """Assess commercial risks"""
        commercial_risks = {
            "market_risks": self.identify_market_risks(text),
            "operational_risks": self.identify_operational_risks(text),
            "strategic_risks": self.identify_strategic_risks(text),
            "overall_risk_level": "中等"
        }
        
        # Calculate overall risk level
        total_risks = len(commercial_risks["market_risks"]) + \
                     len(commercial_risks["operational_risks"]) + \
                     len(commercial_risks["strategic_risks"])
        
        if total_risks >= 6:
            commercial_risks["overall_risk_level"] = "高"
        elif total_risks <= 2:
            commercial_risks["overall_risk_level"] = "低"
        
        return commercial_risks
    
    def identify_market_risks(self, text: str) -> List[Dict[str, str]]:
        """Identify market-related risks"""
        risks = []
        
        if re.search(r'竞争|竞争对手', text):
            risks.append({
                "type": "竞争风险",
                "description": "市场竞争可能影响业务表现"
            })
        
        if re.search(r'独家|专属|排他', text):
            risks.append({
                "type": "依赖风险",
                "description": "过度依赖单一渠道或伙伴"
            })
        
        if re.search(r'市场变化|需求波动', text):
            risks.append({
                "type": "需求风险",
                "description": "市场需求可能发生变化"
            })
        
        return risks
    
    def identify_operational_risks(self, text: str) -> List[Dict[str, str]]:
        """Identify operational risks"""
        risks = []
        
        if re.search(r'交付.*?延迟|延期.*?交付', text):
            risks.append({
                "type": "交付风险",
                "description": "可能存在交付延迟风险"
            })
        
        if re.search(r'质量.*?问题|质量.*?风险', text):
            risks.append({
                "type": "质量风险",
                "description": "产品或服务质量可能不达标"
            })
        
        if not re.search(r'备用.*?方案|应急.*?预案', text):
            risks.append({
                "type": "应急风险",
                "description": "缺少应急预案"
            })
        
        return risks
    
    def identify_strategic_risks(self, text: str) -> List[Dict[str, str]]:
        """Identify strategic risks"""
        risks = []
        
        if re.search(r'长期|多年|永久', text):
            risks.append({
                "type": "长期承诺风险",
                "description": "长期合同可能限制灵活性"
            })
        
        if re.search(r'技术.*?变化|技术.*?更新', text):
            risks.append({
                "type": "技术风险",
                "description": "技术变化可能影响合同执行"
            })
        
        return risks
    
    def analyze_market_conditions(self, text: str) -> Dict[str, Any]:
        """Analyze market conditions and competitive positioning"""
        market_analysis = {
            "market_positioning": self.assess_market_positioning(text),
            "competitive_advantage": self.identify_competitive_advantages(text),
            "market_opportunity": self.assess_market_opportunity(text),
            "customer_value": self.analyze_customer_value(text)
        }
        
        return market_analysis
    
    def assess_market_positioning(self, text: str) -> Dict[str, str]:
        """Assess market positioning"""
        positioning = {
            "market_segment": "未明确",
            "target_customer": "未明确",
            "value_proposition": "未明确"
        }
        
        # Identify market segment
        if re.search(r'高端|高级|豪华', text):
            positioning["market_segment"] = "高端市场"
        elif re.search(r'中端|标准|普通', text):
            positioning["market_segment"] = "中端市场"
        elif re.search(r'经济|低价|基础', text):
            positioning["market_segment"] = "经济型市场"
        
        # Identify target customer
        if re.search(r'企业|公司|机构', text):
            positioning["target_customer"] = "企业客户"
        elif re.search(r'个人|消费者|用户', text):
            positioning["target_customer"] = "个人客户"
        
        return positioning
    
    def identify_competitive_advantages(self, text: str) -> List[str]:
        """Identify competitive advantages"""
        advantages = []
        
        advantage_keywords = {
            '技术优势': ['技术', '专利', '创新', '先进'],
            '成本优势': ['低成本', '价格优势', '经济', '实惠'],
            '服务优势': ['服务', '支持', '响应', '专业'],
            '品牌优势': ['品牌', '知名', '信誉', '声誉'],
            '规模优势': ['规模', '批量', '大型', '领先'],
            '渠道优势': ['渠道', '网络', '覆盖', '分销']
        }
        
        for advantage, keywords in advantage_keywords.items():
            if any(keyword in text for keyword in keywords):
                advantages.append(advantage)
        
        return advantages
    
    def assess_market_opportunity(self, text: str) -> Dict[str, str]:
        """Assess market opportunity"""
        opportunity = {
            "market_size": "未评估",
            "growth_potential": "未评估",
            "entry_barriers": "未评估"
        }
        
        # Market size indicators
        if re.search(r'大型.*?市场|巨大.*?市场|市场.*?庞大', text):
            opportunity["market_size"] = "大型市场"
        elif re.search(r'小型.*?市场|细分.*?市场|利基.*?市场', text):
            opportunity["market_size"] = "细分市场"
        
        # Growth potential
        if re.search(r'增长|扩大|发展|上升', text):
            opportunity["growth_potential"] = "正增长"
        elif re.search(r'下降|萎缩|减少', text):
            opportunity["growth_potential"] = "负增长"
        
        return opportunity
    
    def analyze_customer_value(self, text: str) -> Dict[str, Any]:
        """Analyze customer value proposition"""
        customer_value = {
            "value_drivers": self.identify_value_drivers(text),
            "customer_benefits": self.identify_customer_benefits(text),
            "satisfaction_indicators": self.identify_satisfaction_indicators(text)
        }
        
        return customer_value
    
    def identify_value_drivers(self, text: str) -> List[str]:
        """Identify value drivers"""
        drivers = []
        
        driver_keywords = {
            '成本节约': ['节约', '降低成本', '减少费用'],
            '效率提升': ['效率', '提升', '优化', '改善'],
            '质量改进': ['质量', '改进', '提高', '优质'],
            '便利性': ['便利', '方便', '简化', '快捷'],
            '创新性': ['创新', '新颖', '独特', '前沿']
        }
        
        for driver, keywords in driver_keywords.items():
            if any(keyword in text for keyword in keywords):
                drivers.append(driver)
        
        return drivers
    
    def identify_customer_benefits(self, text: str) -> List[str]:
        """Identify customer benefits"""
        benefits = []
        
        benefit_patterns = [
            r'为.*?提供.*?[价值|服务|便利]',
            r'帮助.*?[降低|提高|改善]',
            r'使.*?能够.*?[实现|达到|获得]'
        ]
        
        for pattern in benefit_patterns:
            matches = re.findall(pattern, text)
            benefits.extend(matches)
        
        return benefits
    
    def identify_satisfaction_indicators(self, text: str) -> List[str]:
        """Identify customer satisfaction indicators"""
        indicators = []
        
        if re.search(r'满意度|客户满意', text):
            indicators.append("客户满意度指标")
        
        if re.search(r'投诉|抱怨|意见', text):
            indicators.append("投诉处理机制")
        
        if re.search(r'反馈|评价|评估', text):
            indicators.append("客户反馈机制")
        
        return indicators
    
    def analyze_operational_aspects(self, text: str) -> Dict[str, Any]:
        """Analyze operational aspects"""
        operational_analysis = {
            "delivery_terms": self.analyze_delivery_terms(text),
            "quality_standards": self.analyze_quality_standards(text),
            "service_levels": self.analyze_service_levels(text),
            "operational_efficiency": self.assess_operational_efficiency(text)
        }
        
        return operational_analysis
    
    def analyze_delivery_terms(self, text: str) -> Dict[str, Any]:
        """Analyze delivery terms and logistics"""
        delivery = {
            "delivery_method": "未明确",
            "delivery_timeline": "未明确",
            "delivery_location": "未明确",
            "logistics_responsibility": "未明确"
        }
        
        # Delivery method
        if re.search(r'快递|邮寄', text):
            delivery["delivery_method"] = "快递邮寄"
        elif re.search(r'自提|上门', text):
            delivery["delivery_method"] = "自提或上门"
        elif re.search(r'物流|运输', text):
            delivery["delivery_method"] = "物流运输"
        
        # Timeline
        timeline_match = re.search(r'(\d+)天.*?交付|(\d+)工作日.*?交付', text)
        if timeline_match:
            days = timeline_match.group(1) or timeline_match.group(2)
            delivery["delivery_timeline"] = f"{days}天"
        
        return delivery
    
    def analyze_quality_standards(self, text: str) -> Dict[str, Any]:
        """Analyze quality standards and requirements"""
        quality = {
            "quality_criteria": self.extract_quality_criteria(text),
            "testing_requirements": self.extract_testing_requirements(text),
            "acceptance_standards": self.extract_acceptance_standards(text),
            "quality_assurance": self.assess_quality_assurance(text)
        }
        
        return quality
    
    def extract_quality_criteria(self, text: str) -> List[str]:
        """Extract quality criteria"""
        criteria = []
        lines = text.split('\n')
        
        quality_keywords = ['质量', '标准', '规格', '要求', '指标']
        
        for line in lines:
            if any(keyword in line for keyword in quality_keywords):
                if re.search(r'符合|达到|满足', line):
                    criteria.append(line.strip())
        
        return criteria
    
    def extract_testing_requirements(self, text: str) -> List[str]:
        """Extract testing requirements"""
        testing = []
        
        testing_keywords = ['检验', '测试', '检测', '试验', '认证']
        lines = text.split('\n')
        
        for line in lines:
            if any(keyword in line for keyword in testing_keywords):
                testing.append(line.strip())
        
        return testing
    
    def extract_acceptance_standards(self, text: str) -> List[str]:
        """Extract acceptance standards"""
        acceptance = []
        
        acceptance_keywords = ['验收', '接受', '确认', '签收']
        lines = text.split('\n')
        
        for line in lines:
            if any(keyword in line for keyword in acceptance_keywords):
                acceptance.append(line.strip())
        
        return acceptance
    
    def assess_quality_assurance(self, text: str) -> Dict[str, bool]:
        """Assess quality assurance measures"""
        qa_measures = {
            "has_quality_control": bool(re.search(r'质量控制|质量管理', text)),
            "has_certification": bool(re.search(r'认证|证书|资质', text)),
            "has_warranty": bool(re.search(r'保修|保证|担保', text)),
            "has_penalty_for_defects": bool(re.search(r'质量.*?责任|缺陷.*?赔偿', text))
        }
        
        return qa_measures
    
    def analyze_service_levels(self, text: str) -> Dict[str, Any]:
        """Analyze service levels and support"""
        service_analysis = {
            "service_scope": self.define_service_scope(text),
            "support_levels": self.analyze_support_levels(text),
            "response_times": self.extract_response_times(text),
            "service_metrics": self.identify_service_metrics(text)
        }
        
        return service_analysis
    
    def define_service_scope(self, text: str) -> List[str]:
        """Define service scope"""
        scope = []
        
        service_types = {
            '技术支持': ['技术支持', '技术服务', '技术咨询'],
            '维护服务': ['维护', '保养', '维修'],
            '培训服务': ['培训', '教学', '指导'],
            '安装服务': ['安装', '部署', '实施'],
            '咨询服务': ['咨询', '建议', '方案']
        }
        
        for service_type, keywords in service_types.items():
            if any(keyword in text for keyword in keywords):
                scope.append(service_type)
        
        return scope
    
    def analyze_support_levels(self, text: str) -> Dict[str, str]:
        """Analyze support levels"""
        support = {
            "availability": "未明确",
            "escalation": "未明确",
            "contact_methods": "未明确"
        }
        
        # Availability
        if re.search(r'24小时|全天候', text):
            support["availability"] = "24/7支持"
        elif re.search(r'工作日|工作时间', text):
            support["availability"] = "工作时间支持"
        
        # Contact methods
        contact_methods = []
        if re.search(r'电话|热线', text):
            contact_methods.append("电话")
        if re.search(r'邮件|邮箱', text):
            contact_methods.append("邮件")
        if re.search(r'在线|网络', text):
            contact_methods.append("在线")
        
        support["contact_methods"] = ", ".join(contact_methods) if contact_methods else "未明确"
        
        return support
    
    def extract_response_times(self, text: str) -> Dict[str, str]:
        """Extract response times"""
        response_times = {}
        
        # Look for response time patterns
        response_patterns = [
            (r'(\d+)小时.*?响应', 'initial_response'),
            (r'(\d+)天.*?解决', 'resolution_time'),
            (r'(\d+)分钟.*?回复', 'reply_time')
        ]
        
        for pattern, key in response_patterns:
            match = re.search(pattern, text)
            if match:
                response_times[key] = f"{match.group(1)}{'小时' if 'small' in pattern else '天' if '天' in pattern else '分钟'}"
        
        return response_times
    
    def identify_service_metrics(self, text: str) -> List[str]:
        """Identify service metrics and KPIs"""
        metrics = []
        
        metric_keywords = {
            '响应时间': ['响应时间', '回复时间'],
            '解决率': ['解决率', '完成率'],
            '满意度': ['满意度', '客户满意'],
            '可用性': ['可用性', '正常运行时间'],
            '准确性': ['准确性', '正确率']
        }
        
        for metric, keywords in metric_keywords.items():
            if any(keyword in text for keyword in keywords):
                metrics.append(metric)
        
        return metrics
    
    def assess_operational_efficiency(self, text: str) -> Dict[str, Any]:
        """Assess operational efficiency"""
        efficiency = {
            "process_optimization": self.assess_process_optimization(text),
            "resource_utilization": self.assess_resource_utilization(text),
            "automation_level": self.assess_automation_level(text),
            "scalability": self.assess_scalability(text)
        }
        
        return efficiency
    
    def assess_process_optimization(self, text: str) -> Dict[str, bool]:
        """Assess process optimization"""
        optimization = {
            "has_standardized_processes": bool(re.search(r'标准.*?流程|规范.*?程序', text)),
            "has_improvement_mechanism": bool(re.search(r'改进|优化|提升', text)),
            "has_monitoring": bool(re.search(r'监控|跟踪|监测', text))
        }
        
        return optimization
    
    def assess_resource_utilization(self, text: str) -> Dict[str, str]:
        """Assess resource utilization"""
        utilization = {
            "human_resources": "未评估",
            "technology_resources": "未评估",
            "financial_resources": "未评估"
        }
        
        if re.search(r'人员|员工|团队', text):
            utilization["human_resources"] = "有人力资源投入"
        
        if re.search(r'技术|系统|设备', text):
            utilization["technology_resources"] = "有技术资源投入"
        
        if re.search(r'投资|资金|预算', text):
            utilization["financial_resources"] = "有资金投入"
        
        return utilization
    
    def assess_automation_level(self, text: str) -> str:
        """Assess automation level"""
        if re.search(r'自动化|自动.*?处理|智能.*?系统', text):
            return "高度自动化"
        elif re.search(r'半自动|部分.*?自动', text):
            return "部分自动化"
        else:
            return "主要依赖人工"
    
    def assess_scalability(self, text: str) -> Dict[str, str]:
        """Assess scalability"""
        scalability = {
            "volume_scalability": "未评估",
            "geographic_scalability": "未评估",
            "functional_scalability": "未评估"
        }
        
        if re.search(r'扩容|扩展|增加.*?规模', text):
            scalability["volume_scalability"] = "支持规模扩展"
        
        if re.search(r'多地|跨区域|全国', text):
            scalability["geographic_scalability"] = "支持地域扩展"
        
        if re.search(r'增加.*?功能|扩展.*?服务', text):
            scalability["functional_scalability"] = "支持功能扩展"
        
        return scalability
    
    def analyze_performance_metrics(self, text: str) -> Dict[str, Any]:
        """Analyze performance metrics and KPIs"""
        performance = {
            "key_metrics": self.identify_key_metrics(text),
            "benchmarks": self.identify_benchmarks(text),
            "reporting_requirements": self.identify_reporting_requirements(text),
            "performance_incentives": self.identify_performance_incentives(text)
        }
        
        return performance
    
    def identify_key_metrics(self, text: str) -> List[Dict[str, str]]:
        """Identify key performance metrics"""
        metrics = []
        
        metric_patterns = [
            (r'(\d+)%.*?以上', '百分比指标'),
            (r'不少于.*?(\d+)', '最小值指标'),  
            (r'不超过.*?(\d+)', '最大值指标'),
            (r'达到.*?(\d+)', '目标值指标')
        ]
        
        for pattern, metric_type in metric_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                metrics.append({
                    "value": match,
                    "type": metric_type
                })
        
        return metrics
    
    def identify_benchmarks(self, text: str) -> List[str]:
        """Identify benchmarks and standards"""
        benchmarks = []
        
        benchmark_keywords = ['行业标准', '最佳实践', '国际标准', '国家标准', '基准', '标杆']
        
        for keyword in benchmark_keywords:
            if keyword in text:
                benchmarks.append(keyword)
        
        return benchmarks
    
    def identify_reporting_requirements(self, text: str) -> Dict[str, Any]:
        """Identify reporting requirements"""
        reporting = {
            "frequency": "未明确",
            "format": "未明确",
            "recipients": "未明确",
            "content": []
        }
        
        # Frequency
        if re.search(r'每月|月度', text):
            reporting["frequency"] = "月度报告"
        elif re.search(r'每季|季度', text):
            reporting["frequency"] = "季度报告"
        elif re.search(r'每年|年度', text):
            reporting["frequency"] = "年度报告"
        
        # Format
        if re.search(r'书面|报告|文档', text):
            reporting["format"] = "书面报告"
        elif re.search(r'电子|邮件|系统', text):
            reporting["format"] = "电子报告"
        
        return reporting
    
    def identify_performance_incentives(self, text: str) -> List[Dict[str, str]]:
        """Identify performance incentives"""
        incentives = []
        
        incentive_patterns = [
            (r'超过.*?奖励', '超额奖励'),
            (r'达到.*?奖金', '达标奖金'),
            (r'提前.*?奖励', '提前完成奖励'),
            (r'质量.*?奖励', '质量奖励')
        ]
        
        for pattern, incentive_type in incentive_patterns:
            if re.search(pattern, text):
                incentives.append({
                    "type": incentive_type,
                    "description": "基于绩效的激励机制"
                })
        
        return incentives
    
    def assess_business_value(self, text: str) -> Dict[str, Any]:
        """Assess overall business value"""
        business_value = {
            "strategic_alignment": self.assess_strategic_alignment(text),
            "competitive_impact": self.assess_competitive_impact(text),
            "financial_impact": self.assess_financial_impact(text),
            "operational_impact": self.assess_operational_impact(text),
            "overall_value_score": 0
        }
        
        # Calculate overall value score
        scores = []
        for key, value in business_value.items():
            if isinstance(value, dict) and "score" in value:
                scores.append(value["score"])
        
        business_value["overall_value_score"] = sum(scores) // len(scores) if scores else 7
        
        return business_value
    
    def assess_strategic_alignment(self, text: str) -> Dict[str, Any]:
        """Assess strategic alignment"""
        alignment = {
            "supports_core_business": False,
            "enables_growth": False,
            "reduces_risks": False,
            "score": 5
        }
        
        if re.search(r'核心.*?业务|主营.*?业务', text):
            alignment["supports_core_business"] = True
            alignment["score"] += 2
        
        if re.search(r'增长|扩展|发展', text):
            alignment["enables_growth"] = True
            alignment["score"] += 2
        
        if re.search(r'降低.*?风险|减少.*?风险', text):
            alignment["reduces_risks"] = True
            alignment["score"] += 1
        
        return alignment
    
    def assess_competitive_impact(self, text: str) -> Dict[str, Any]:
        """Assess competitive impact"""
        impact = {
            "strengthens_position": False,
            "creates_differentiation": False,
            "improves_capabilities": False,
            "score": 5
        }
        
        if re.search(r'竞争.*?优势|市场.*?地位', text):
            impact["strengthens_position"] = True
            impact["score"] += 2
        
        if re.search(r'差异化|独特|创新', text):
            impact["creates_differentiation"] = True
            impact["score"] += 2
        
        if re.search(r'能力.*?提升|技能.*?提升', text):
            impact["improves_capabilities"] = True
            impact["score"] += 1
        
        return impact
    
    def assess_financial_impact(self, text: str) -> Dict[str, Any]:
        """Assess financial impact"""
        impact = {
            "revenue_impact": "中性",
            "cost_impact": "中性", 
            "profitability_impact": "中性",
            "score": 5
        }
        
        # Revenue impact
        if re.search(r'增加.*?收入|提高.*?销售', text):
            impact["revenue_impact"] = "正面"
            impact["score"] += 2
        elif re.search(r'减少.*?收入|降低.*?销售', text):
            impact["revenue_impact"] = "负面"
            impact["score"] -= 1
        
        # Cost impact
        if re.search(r'降低.*?成本|节约.*?费用', text):
            impact["cost_impact"] = "正面"
            impact["score"] += 1
        elif re.search(r'增加.*?成本|提高.*?费用', text):
            impact["cost_impact"] = "负面"
            impact["score"] -= 1
        
        return impact
    
    def assess_operational_impact(self, text: str) -> Dict[str, Any]:
        """Assess operational impact"""
        impact = {
            "efficiency_impact": "中性",
            "quality_impact": "中性",
            "flexibility_impact": "中性",
            "score": 5
        }
        
        # Efficiency impact
        if re.search(r'提高.*?效率|改善.*?效率', text):
            impact["efficiency_impact"] = "正面"
            impact["score"] += 2
        
        # Quality impact
        if re.search(r'提高.*?质量|改善.*?质量', text):
            impact["quality_impact"] = "正面"
            impact["score"] += 1
        
        # Flexibility impact
        if re.search(r'灵活|弹性|适应', text):
            impact["flexibility_impact"] = "正面"
            impact["score"] += 1
        
        return impact
    
    def get_llm_business_analysis(self, text: str) -> str:
        """Get detailed business analysis from LLM"""
        analysis_prompt = f"""
        请对以下合同文本进行全面的商业分析：
        
        合同文本：{text[:1500]}...
        
        请从以下商业角度进行深入分析：
        1. 商业价值和机会评估
        2. 财务条款的合理性和竞争力
        3. 运营风险和市场风险分析
        4. 投资回报和成本效益分析
        5. 竞争优势和市场定位
        6. 业务流程和运营效率
        7. 长期战略价值和发展潜力
        
        请提供专业的商业洞察和建议。
        """
        
        return self.call_llm(analysis_prompt)
    
    def generate_business_recommendations(self, text: str) -> List[Dict[str, str]]:
        """Generate business recommendations"""
        recommendations = []
        
        # Financial recommendations
        if not re.search(r'分期|分批', text):
            recommendations.append({
                "category": "财务优化",
                "priority": "中",
                "recommendation": "建议采用分期付款方式，优化现金流管理"
            })
        
        # Risk management recommendations
        if not re.search(r'保险|担保', text):
            recommendations.append({
                "category": "风险管控",
                "priority": "高",
                "recommendation": "建议增加保险或担保条款，降低商业风险"
            })
        
        # Performance recommendations
        if not re.search(r'KPI|指标|考核', text):
            recommendations.append({
                "category": "绩效管理",
                "priority": "中",
                "recommendation": "建议设定明确的绩效指标和考核标准"
            })
        
        # Market recommendations
        if re.search(r'独家|专属', text):
            recommendations.append({
                "category": "市场策略",
                "priority": "中",
                "recommendation": "独家条款存在依赖风险，建议评估多元化合作的可能性"
            })
        
        return recommendations
    
    def format_business_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format business analysis results for output"""
        output = "=== 商业分析报告 ===\n\n"
        
        # Business Value Assessment
        business_value = analysis.get("business_value", {})
        output += f"整体商业价值评分：{business_value.get('overall_value_score', 0)}/10\n\n"
        
        # Financial Analysis
        financial = analysis.get("financial_analysis", {})
        output += "--- 财务分析 ---\n"
        
        pricing = financial.get("pricing_structure", {})
        if pricing.get("amounts_found"):
            output += f"发现金额：{', '.join(pricing['amounts_found'][:3])}\n"
        output += f"定价模式：{pricing.get('pricing_model', '未明确')}\n"
        output += f"货币类型：{pricing.get('currency', '未明确')}\n"
        
        payment_terms = financial.get("payment_terms", {})
        cash_flow = payment_terms.get("cash_flow_impact", {})
        output += f"预付款要求：{'是' if cash_flow.get('upfront_payment_required') else '否'}\n"
        output += f"现金流影响：{cash_flow.get('working_capital_impact', '中等')}\n\n"
        
        # Commercial Risks
        risks = analysis.get("commercial_risks", {})
        output += f"商业风险等级：{risks.get('overall_risk_level', '中等')}\n"
        
        high_risk_count = len(risks.get("market_risks", [])) + len(risks.get("operational_risks", []))
        if high_risk_count > 0:
            output += f"识别风险项目：{high_risk_count}项\n"
        
        output += "\n"
        
        # Market Analysis
        market = analysis.get("market_analysis", {})
        positioning = market.get("market_positioning", {})
        output += "--- 市场分析 ---\n"
        output += f"目标市场：{positioning.get('market_segment', '未明确')}\n"
        output += f"目标客户：{positioning.get('target_customer', '未明确')}\n"
        
        advantages = market.get("competitive_advantage", [])
        if advantages:
            output += f"竞争优势：{', '.join(advantages[:3])}\n"
        
        output += "\n"
        
        # Operational Analysis
        operational = analysis.get("operational_analysis", {})
        delivery = operational.get("delivery_terms", {})
        output += "--- 运营分析 ---\n"
        output += f"交付方式：{delivery.get('delivery_method', '未明确')}\n"
        output += f"交付周期：{delivery.get('delivery_timeline', '未明确')}\n"
        
        efficiency = operational.get("operational_efficiency", {})
        output += f"自动化水平：{efficiency.get('automation_level', '未评估')}\n\n"
        
        # Performance Metrics
        performance = analysis.get("performance_metrics", {})
        key_metrics = performance.get("key_metrics", [])
        if key_metrics:
            output += "--- 绩效指标 ---\n"
            for metric in key_metrics[:3]:
                output += f"• {metric.get('type', '未知指标')}：{metric.get('value', '未明确')}\n"
            output += "\n"
        
        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            output += "--- 商业建议 ---\n"
            for i, rec in enumerate(recommendations, 1):
                output += f"{i}. [{rec['priority']}] {rec['recommendation']}\n"
            output += "\n"
        
        # Detailed Analysis
        detailed_analysis = analysis.get("detailed_analysis", "")
        if detailed_analysis:
            output += "--- 详细商业分析 ---\n"
            output += detailed_analysis
        
        return output

if __name__ == "__main__":
    agent = BusinessAgent()
    agent.run(Config.AGENT_PORTS["business"])