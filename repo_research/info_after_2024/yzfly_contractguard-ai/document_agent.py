import re
import json
from typing import Dict, List, Any, Optional
from base_agent import BaseAgent
from config import Config

class DocumentProcessingAgent(BaseAgent):
    """Agent specialized in document processing and text extraction"""
    
    def __init__(self):
        system_prompt = """你是专门处理合同文档的智能体。你的职责包括：

1. 文档解析和文本提取
2. 识别文档结构（条款、章节、附件等）
3. 提取关键信息（当事人、金额、日期、期限等）
4. 识别合同类型
5. 清理和标准化文本格式

你需要：
- 准确识别合同的各个部分
- 提取结构化信息
- 识别潜在的格式问题
- 为后续分析提供清洁的文本数据

输出格式应该结构化，便于其他智能体处理。"""
        
        super().__init__("DocumentProcessingAgent", system_prompt)
    
    def process_text_message(self, message):
        """Process document analysis requests"""
        user_text = message.content.text
        self.logger.info("Processing document analysis request")
        
        try:
            # Extract task and content
            task_info = self.extract_task_info(user_text)
            document_content = task_info.get("content", user_text)
            
            # Perform document processing
            processing_results = self.process_document(document_content)
            
            # Format response
            response_text = self.format_processing_results(processing_results)
            
            return self.create_response_message(message, response_text)
            
        except Exception as e:
            self.logger.error(f"Error in document processing: {str(e)}")
            error_response = f"文档处理过程中发生错误：{str(e)}"
            return self.create_response_message(message, error_response)
    
    def extract_task_info(self, text: str) -> Dict[str, Any]:
        """Extract task information from the input text"""
        lines = text.split('\n')
        task_info = {"content": text}
        
        for line in lines:
            if line.startswith("任务："):
                task_info["task"] = line.replace("任务：", "").strip()
            elif line.startswith("上下文："):
                # Everything after "上下文：" is the document content
                context_start = text.find("上下文：")
                if context_start != -1:
                    task_info["content"] = text[context_start + 4:].strip()
                break
        
        return task_info
    
    def process_document(self, document_text: str) -> Dict[str, Any]:
        """Main document processing function"""
        results = {
            "document_structure": self.analyze_document_structure(document_text),
            "key_information": self.extract_key_information(document_text),
            "contract_type": self.identify_contract_type(document_text),
            "parties": self.extract_parties(document_text),
            "financial_terms": self.extract_financial_terms(document_text),
            "dates_and_deadlines": self.extract_dates_and_deadlines(document_text),
            "format_issues": self.identify_format_issues(document_text),
            "text_statistics": self.calculate_text_statistics(document_text)
        }
        
        return results
    
    def analyze_document_structure(self, text: str) -> Dict[str, Any]:
        """Analyze the structure of the document"""
        structure = {
            "sections": [],
            "clauses": [],
            "appendices": [],
            "has_signature_block": False,
            "has_date_field": False
        }
        
        lines = text.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for section headers (numbered or titled)
            if re.match(r'^(第?[一二三四五六七八九十\d]+[条章节部分]|Article\s+\d+|Section\s+\d+)', line, re.IGNORECASE):
                section_info = {
                    "line_number": i + 1,
                    "title": line,
                    "type": "section"
                }
                structure["sections"].append(section_info)
                current_section = section_info
            
            # Check for clause markers
            elif re.match(r'^\d+\.\d*', line) or re.match(r'^\([一二三四五六七八九十\d]+\)', line):
                clause_info = {
                    "line_number": i + 1,
                    "text": line,
                    "section": current_section["title"] if current_section else None
                }
                structure["clauses"].append(clause_info)
            
            # Check for appendices
            elif re.match(r'^附件|附录|Appendix|Exhibit', line, re.IGNORECASE):
                structure["appendices"].append({
                    "line_number": i + 1,
                    "title": line
                })
            
            # Check for signature blocks
            elif re.search(r'签字|签名|signature|签署', line, re.IGNORECASE):
                structure["has_signature_block"] = True
            
            # Check for date fields
            elif re.search(r'\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{1,2}-\d{1,2}', line):
                structure["has_date_field"] = True
        
        return structure
    
    def extract_key_information(self, text: str) -> Dict[str, Any]:
        """Extract key information from the document"""
        key_info = {}
        
        # Use LLM to extract structured information
        extraction_prompt = f"""
        请从以下合同文本中提取关键信息，以JSON格式返回：
        
        文本：{text[:2000]}...
        
        请提取：
        1. contract_title - 合同标题
        2. contract_number - 合同编号
        3. signing_date - 签署日期
        4. effective_date - 生效日期
        5. expiry_date - 到期日期
        6. contract_amount - 合同金额
        7. currency - 货币类型
        8. main_subject - 合同主要标的物
        9. key_obligations - 主要义务
        10. penalty_clauses - 违约条款
        
        返回JSON格式，如果某项信息未找到，请标记为null。
        """
        
        llm_response = self.call_llm(extraction_prompt)
        
        try:
            extracted_info = json.loads(llm_response)
            key_info.update(extracted_info)
        except json.JSONDecodeError:
            # Fallback to regex-based extraction
            key_info = self.regex_based_extraction(text)
        
        return key_info
    
    def regex_based_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback regex-based information extraction"""
        info = {}
        
        # Extract dates
        date_patterns = [
            r'(\d{4})年(\d{1,2})月(\d{1,2})日',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            r'(\d{4})-(\d{1,2})-(\d{1,2})'
        ]
        
        dates_found = []
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates_found.extend(matches)
        
        info['dates_found'] = dates_found
        
        # Extract monetary amounts
        money_pattern = r'([￥$¥]\s*[\d,]+(?:\.\d{2})?|[\d,]+(?:\.\d{2})?\s*[元万千万亿])'
        money_matches = re.findall(money_pattern, text)
        info['monetary_amounts'] = money_matches
        
        # Extract contract parties (basic pattern)
        party_pattern = r'(甲方|乙方|第一方|第二方)[:：]\s*([^，。；\n]+)'
        party_matches = re.findall(party_pattern, text)
        info['parties'] = dict(party_matches)
        
        return info
    
    def identify_contract_type(self, text: str) -> str:
        """Identify the type of contract"""
        contract_types = {
            '销售合同': ['销售', '买卖', '购买', '出售'],
            '服务合同': ['服务', '咨询', '技术服务', '维护'],
            '租赁合同': ['租赁', '出租', '承租', '租金'],
            '劳动合同': ['劳动', '雇佣', '员工', '工资'],
            '合作协议': ['合作', '协议', '合作协议', '战略合作'],
            '保密协议': ['保密', 'NDA', '机密', '保密协议'],
            '许可协议': ['许可', '授权', '许可协议', '使用权'],
            '供应合同': ['供应', '采购', '供货', '供应商']
        }
        
        text_lower = text.lower()
        
        for contract_type, keywords in contract_types.items():
            if any(keyword in text for keyword in keywords):
                return contract_type
        
        return "未识别类型"
    
    def extract_parties(self, text: str) -> Dict[str, str]:
        """Extract contract parties"""
        parties = {}
        
        # Common patterns for Chinese contracts
        party_patterns = [
            r'甲方[:：]\s*([^，。；\n]+)',
            r'乙方[:：]\s*([^，。；\n]+)',
            r'第一方[:：]\s*([^，。；\n]+)',
            r'第二方[:：]\s*([^，。；\n]+)',
            r'委托方[:：]\s*([^，。；\n]+)',
            r'受托方[:：]\s*([^，。；\n]+)',
            r'买方[:：]\s*([^，。；\n]+)',
            r'卖方[:：]\s*([^，。；\n]+)'
        ]
        
        for pattern in party_patterns:
            matches = re.findall(pattern, text)
            if matches:
                if '甲方' in pattern:
                    parties['甲方'] = matches[0].strip()
                elif '乙方' in pattern:
                    parties['乙方'] = matches[0].strip()
                elif '第一方' in pattern:
                    parties['第一方'] = matches[0].strip()
                elif '第二方' in pattern:
                    parties['第二方'] = matches[0].strip()
        
        return parties
    
    def extract_financial_terms(self, text: str) -> Dict[str, Any]:
        """Extract financial terms and amounts"""
        financial_terms = {
            "amounts": [],
            "payment_terms": [],
            "penalties": []
        }
        
        # Extract monetary amounts
        amount_patterns = [
            r'([￥$¥]\s*[\d,]+(?:\.\d{2})?)',
            r'([\d,]+(?:\.\d{2})?\s*[元万千万亿])',
            r'([一二三四五六七八九十百千万亿]+[元万千万亿])'
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text)
            financial_terms["amounts"].extend(matches)
        
        # Extract payment terms
        payment_keywords = ['支付', '付款', '结算', '预付', '尾款', '分期']
        lines = text.split('\n')
        
        for line in lines:
            if any(keyword in line for keyword in payment_keywords):
                financial_terms["payment_terms"].append(line.strip())
        
        return financial_terms
    
    def extract_dates_and_deadlines(self, text: str) -> Dict[str, List[str]]:
        """Extract dates and deadlines"""
        dates_info = {
            "dates_found": [],
            "deadlines": []
        }
        
        # Date patterns
        date_patterns = [
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{1,2}/\d{1,2}/\d{4}',
            r'\d{4}-\d{1,2}-\d{1,2}'
        ]
        
        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            dates_info["dates_found"].extend(matches)
        
        # Deadline keywords
        deadline_keywords = ['期限', '截止', '到期', '届满', '终止', '完成时间']
        lines = text.split('\n')
        
        for line in lines:
            if any(keyword in line for keyword in deadline_keywords):
                dates_info["deadlines"].append(line.strip())
        
        return dates_info
    
    def identify_format_issues(self, text: str) -> List[Dict[str, Any]]:
        """Identify potential format issues"""
        issues = []
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            # Check for very long lines
            if len(line) > 200:
                issues.append({
                    "type": "long_line",
                    "line_number": i + 1,
                    "description": f"第{i+1}行过长 ({len(line)} 字符)"
                })
            
            # Check for inconsistent spacing
            if re.search(r'\s{3,}', line):
                issues.append({
                    "type": "inconsistent_spacing",
                    "line_number": i + 1,
                    "description": f"第{i+1}行存在不一致的空格"
                })
            
            # Check for missing punctuation at end of sentences
            if len(line.strip()) > 20 and not line.strip().endswith(('。', '；', '：', '！', '？', '.', ';', ':', '!', '?')):
                issues.append({
                    "type": "missing_punctuation",
                    "line_number": i + 1,
                    "description": f"第{i+1}行可能缺少标点符号"
                })
        
        return issues
    
    def calculate_text_statistics(self, text: str) -> Dict[str, int]:
        """Calculate basic text statistics"""
        lines = text.split('\n')
        words = text.split()
        
        return {
            "total_characters": len(text),
            "total_lines": len(lines),
            "non_empty_lines": len([line for line in lines if line.strip()]),
            "total_words": len(words),
            "average_line_length": sum(len(line) for line in lines) // len(lines) if lines else 0
        }
    
    def format_processing_results(self, results: Dict[str, Any]) -> str:
        """Format processing results for output"""
        output = "=== 文档处理结果 ===\n\n"
        
        # Document type and basic info
        output += f"合同类型：{results.get('contract_type', '未识别')}\n"
        
        # Key information
        key_info = results.get('key_information', {})
        if key_info:
            output += "\n--- 关键信息 ---\n"
            for key, value in key_info.items():
                if value and value != "null":
                    output += f"{key}: {value}\n"
        
        # Parties
        parties = results.get('parties', {})
        if parties:
            output += "\n--- 合同当事人 ---\n"
            for role, party in parties.items():
                output += f"{role}: {party}\n"
        
        # Document structure
        structure = results.get('document_structure', {})
        output += f"\n--- 文档结构 ---\n"
        output += f"章节数量: {len(structure.get('sections', []))}\n"
        output += f"条款数量: {len(structure.get('clauses', []))}\n"
        output += f"附件数量: {len(structure.get('appendices', []))}\n"
        output += f"包含签名区: {'是' if structure.get('has_signature_block') else '否'}\n"
        
        # Text statistics
        stats = results.get('text_statistics', {})
        output += f"\n--- 文本统计 ---\n"
        output += f"总字符数: {stats.get('total_characters', 0)}\n"
        output += f"总行数: {stats.get('total_lines', 0)}\n"
        output += f"有效行数: {stats.get('non_empty_lines', 0)}\n"
        
        # Format issues
        issues = results.get('format_issues', [])
        if issues:
            output += f"\n--- 格式问题 ({len(issues)}项) ---\n"
            for issue in issues[:5]:  # Limit to first 5 issues
                output += f"- {issue['description']}\n"
        
        return output

if __name__ == "__main__":
    agent = DocumentProcessingAgent()
    agent.run(Config.AGENT_PORTS["document"])