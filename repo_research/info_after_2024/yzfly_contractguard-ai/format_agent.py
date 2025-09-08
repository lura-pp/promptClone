import re
import json
from typing import Dict, List, Any, Optional
from base_agent import BaseAgent
from config import Config

class FormatAgent(BaseAgent):
    """Agent specialized in document formatting and structure analysis"""
    
    def __init__(self):
        system_prompt = """你是专门进行文档格式检查和结构分析的智能体。你的职责包括：

1. 文档格式规范性检查
2. 合同结构完整性分析
3. 章节条款编号规范性
4. 文档排版和布局检查
5. 标准化格式建议
6. 可读性和专业性评估

重点检查项目：
- 合同标题和头部信息
- 章节结构和编号体系
- 条款层次和缩进格式
- 签署区和日期格式
- 页眉页脚和页码
- 字体字号和行间距
- 表格和列表格式
- 附件和引用格式

你的分析应该：
- 识别格式不规范的地方
- 提供具体的修改建议
- 确保文档的专业性
- 提高文档的可读性
- 符合行业标准和最佳实践"""
        
        super().__init__("FormatAgent", system_prompt)
        self.format_standards = self.initialize_format_standards()
    
    def initialize_format_standards(self) -> Dict[str, Dict[str, Any]]:
        """Initialize format standards and requirements"""
        return {
            "title_format": {
                "required_elements": ["合同名称", "合同编号", "签署日期"],
                "naming_conventions": ["××合同", "××协议", "××契约"],
                "position": "居中对齐"
            },
            "party_format": {
                "required_info": ["当事人名称", "地址", "联系方式", "法定代表人"],
                "standard_labels": ["甲方", "乙方", "第一方", "第二方"],
                "alignment": "左对齐"
            },
            "clause_format": {
                "numbering_systems": ["1.1.1", "一、（一）1.", "第一条"],
                "indentation": "统一缩进",
                "spacing": "条款间空行"
            },
            "signature_format": {
                "required_elements": ["签字栏", "盖章栏", "日期栏"],
                "layout": "表格形式",
                "position": "文档末尾"
            }
        }
    
    def process_text_message(self, message):
        """Process format analysis requests"""
        user_text = message.content.text
        self.logger.info("Processing format analysis request")
        
        try:
            # Extract task and content
            task_info = self.extract_task_info(user_text)
            document_content = task_info.get("content", user_text)
            
            # Perform format analysis
            format_analysis = self.perform_format_analysis(document_content)
            
            # Format response
            response_text = self.format_analysis_results(format_analysis)
            
            return self.create_response_message(message, response_text)
            
        except Exception as e:
            self.logger.error(f"Error in format analysis: {str(e)}")
            error_response = f"格式分析过程中发生错误：{str(e)}"
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
    
    def perform_format_analysis(self, document_text: str) -> Dict[str, Any]:
        """Perform comprehensive format analysis"""
        analysis = {
            "document_structure": self.analyze_document_structure(document_text),
            "title_analysis": self.analyze_title_format(document_text),
            "party_section": self.analyze_party_section(document_text),
            "clause_formatting": self.analyze_clause_formatting(document_text),
            "numbering_system": self.analyze_numbering_system(document_text),
            "signature_section": self.analyze_signature_section(document_text),
            "text_formatting": self.analyze_text_formatting(document_text),
            "layout_issues": self.identify_layout_issues(document_text),
            "recommendations": self.generate_format_recommendations(document_text),
            "compliance_score": 0
        }
        
        # Calculate compliance score
        analysis["compliance_score"] = self.calculate_compliance_score(analysis)
        
        # Get detailed analysis from LLM
        llm_analysis = self.get_llm_format_analysis(document_text)
        analysis["detailed_analysis"] = llm_analysis
        
        return analysis
    
    def analyze_document_structure(self, text: str) -> Dict[str, Any]:
        """Analyze overall document structure"""
        structure = {
            "has_title": False,
            "has_parties_section": False,
            "has_main_content": False,
            "has_signature_section": False,
            "section_order": [],
            "structure_score": 0
        }
        
        lines = text.split('\n')
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Check for title (usually first substantial line)
            if i < 5 and re.search(r'合同|协议|契约', line) and not structure["has_title"]:
                structure["has_title"] = True
                structure["section_order"].append("标题")
                current_section = "title"
            
            # Check for parties section
            elif re.search(r'甲方|乙方|第一方|第二方', line) and current_section != "parties":
                structure["has_parties_section"] = True
                if "当事人信息" not in structure["section_order"]:
                    structure["section_order"].append("当事人信息")
                current_section = "parties"
            
            # Check for main content (numbered clauses)
            elif re.search(r'^(第?[一二三四五六七八九十\d]+[条章节]|Article\s+\d+)', line) and current_section != "content":
                structure["has_main_content"] = True
                if "正文内容" not in structure["section_order"]:
                    structure["section_order"].append("正文内容")
                current_section = "content"
            
            # Check for signature section
            elif re.search(r'签字|签名|盖章|签署', line) and current_section != "signature":
                structure["has_signature_section"] = True
                if "签署区" not in structure["section_order"]:
                    structure["section_order"].append("签署区")
                current_section = "signature"
        
        # Calculate structure score
        score = 0
        if structure["has_title"]:
            score += 2
        if structure["has_parties_section"]:
            score += 3
        if structure["has_main_content"]:
            score += 4
        if structure["has_signature_section"]:
            score += 1
        
        structure["structure_score"] = score
        
        return structure
    
    def analyze_title_format(self, text: str) -> Dict[str, Any]:
        """Analyze title format and requirements"""
        title_analysis = {
            "title_found": False,
            "title_text": "",
            "title_position": "未确定",
            "has_contract_number": False,
            "has_date": False,
            "format_issues": [],
            "title_score": 0
        }
        
        lines = text.split('\n')
        
        # Look for title in first few lines
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            if re.search(r'合同|协议|契约', line) and len(line) < 100:
                title_analysis["title_found"] = True
                title_analysis["title_text"] = line
                
                # Check if title appears centered (rough heuristic)
                if len(line) < 50 and i < 3:
                    title_analysis["title_position"] = "居中"
                else:
                    title_analysis["title_position"] = "左对齐"
                
                # Check for contract number
                if re.search(r'[编号|合同号][:：]\s*\w+', line):
                    title_analysis["has_contract_number"] = True
                
                # Check for date in title area
                if re.search(r'\d{4}年\d{1,2}月\d{1,2}日', line):
                    title_analysis["has_date"] = True
                
                break
        
        # Identify format issues
        if not title_analysis["title_found"]:
            title_analysis["format_issues"].append("缺少合同标题")
        elif len(title_analysis["title_text"]) > 80:
            title_analysis["format_issues"].append("标题过长，建议简化")
        
        if not title_analysis["has_contract_number"]:
            title_analysis["format_issues"].append("缺少合同编号")
        
        # Calculate title score
        score = 0
        if title_analysis["title_found"]:
            score += 4
        if title_analysis["has_contract_number"]:
            score += 2
        if title_analysis["title_position"] == "居中":
            score += 1
        if len(title_analysis["format_issues"]) == 0:
            score += 3
        
        title_analysis["title_score"] = score
        
        return title_analysis
    
    def analyze_party_section(self, text: str) -> Dict[str, Any]:
        """Analyze parties section format"""
        party_analysis = {
            "parties_found": [],
            "format_consistency": True,
            "required_info_present": {},
            "alignment_issues": [],
            "party_score": 0
        }
        
        lines = text.split('\n')
        current_party = None
        party_info = {}
        
        for line in lines:
            line = line.strip()
            
            # Check for party labels
            party_match = re.match(r'(甲方|乙方|第一方|第二方)[:：]\s*(.*)', line)
            if party_match:
                if current_party:
                    party_analysis["parties_found"].append({
                        "label": current_party,
                        "info": party_info
                    })
                
                current_party = party_match.group(1)
                party_info = {"name": party_match.group(2).strip()}
                continue
            
            # Collect additional party information
            if current_party:
                if re.search(r'地址|住址|住所', line):
                    party_info["address"] = line
                elif re.search(r'电话|联系|手机', line):
                    party_info["contact"] = line
                elif re.search(r'法定代表人|负责人', line):
                    party_info["representative"] = line
                elif re.search(r'统一社会信用代码|营业执照', line):
                    party_info["registration"] = line
        
        # Add last party if exists
        if current_party:
            party_analysis["parties_found"].append({
                "label": current_party,
                "info": party_info
            })
        
        # Check required information
        required_fields = ["name", "address", "contact"]
        for party in party_analysis["parties_found"]:
            party_label = party["label"]
            party_analysis["required_info_present"][party_label] = {}
            
            for field in required_fields:
                party_analysis["required_info_present"][party_label][field] = field in party["info"]
        
        # Calculate party score
        score = 0
        if len(party_analysis["parties_found"]) >= 2:
            score += 4
        
        # Check completeness of information
        for party in party_analysis["parties_found"]:
            info = party["info"]
            if "name" in info and "address" in info:
                score += 2
            if "contact" in info:
                score += 1
        
        party_analysis["party_score"] = min(score, 10)
        
        return party_analysis
    
    def analyze_clause_formatting(self, text: str) -> Dict[str, Any]:
        """Analyze clause formatting and structure"""
        clause_analysis = {
            "clause_count": 0,
            "numbering_consistency": True,
            "indentation_consistency": True,
            "spacing_issues": [],
            "formatting_issues": [],
            "clause_score": 0
        }
        
        lines = text.split('\n')
        clause_lines = []
        previous_indent = None
        
        for i, line in enumerate(lines):
            # Identify clause lines
            if re.match(r'^\s*(第?[一二三四五六七八九十\d]+[条章节部分]|\d+\.\d*|[一二三四五六七八九十]+、)', line):
                clause_lines.append({
                    "line_number": i + 1,
                    "text": line,
                    "indent": len(line) - len(line.lstrip())
                })
                clause_analysis["clause_count"] += 1
        
        # Check indentation consistency
        if clause_lines:
            first_indent = clause_lines[0]["indent"]
            for clause in clause_lines:
                if abs(clause["indent"] - first_indent) > 2:  # Allow small variations
                    clause_analysis["indentation_consistency"] = False
                    clause_analysis["formatting_issues"].append(
                        f"第{clause['line_number']}行缩进不一致"
                    )
        
        # Check spacing between clauses
        for i in range(len(clause_lines) - 1):
            current_line = clause_lines[i]["line_number"]
            next_line = clause_lines[i + 1]["line_number"]
            
            # Check if there's appropriate spacing
            if next_line - current_line == 1:  # No space between clauses
                clause_analysis["spacing_issues"].append(
                    f"第{current_line}条和第{next_line}条之间缺少空行"
                )
        
        # Calculate clause score
        score = 0
        if clause_analysis["clause_count"] > 0:
            score += 3
        if clause_analysis["numbering_consistency"]:
            score += 2
        if clause_analysis["indentation_consistency"]:
            score += 2
        if len(clause_analysis["spacing_issues"]) == 0:
            score += 2
        if len(clause_analysis["formatting_issues"]) == 0:
            score += 1
        
        clause_analysis["clause_score"] = score
        
        return clause_analysis
    
    def analyze_numbering_system(self, text: str) -> Dict[str, Any]:
        """Analyze numbering system consistency"""
        numbering_analysis = {
            "numbering_style": "混合",
            "consistency_score": 0,
            "numbering_errors": [],
            "suggested_system": "阿拉伯数字"
        }
        
        lines = text.split('\n')
        numbering_patterns = {
            "arabic": 0,  # 1. 2. 3.
            "chinese": 0,  # 一、二、三、
            "roman": 0,   # (一) (二) (三)
            "mixed": 0    # 第一条、第二条
        }
        
        for line in lines:
            if re.search(r'^\s*\d+\.', line):
                numbering_patterns["arabic"] += 1
            elif re.search(r'^\s*[一二三四五六七八九十]+、', line):
                numbering_patterns["chinese"] += 1
            elif re.search(r'^\s*\([一二三四五六七八九十]+\)', line):
                numbering_patterns["roman"] += 1
            elif re.search(r'^\s*第[一二三四五六七八九十\d]+[条章节]', line):
                numbering_patterns["mixed"] += 1
        
        # Determine dominant style
        max_count = max(numbering_patterns.values())
        for style, count in numbering_patterns.items():
            if count == max_count and count > 0:
                numbering_analysis["numbering_style"] = style
                break
        
        # Calculate consistency score
        total_numbered_items = sum(numbering_patterns.values())
        if total_numbered_items > 0:
            consistency_ratio = max_count / total_numbered_items
            numbering_analysis["consistency_score"] = int(consistency_ratio * 10)
        
        # Suggest improvements
        if numbering_analysis["consistency_score"] < 8:
            numbering_analysis["numbering_errors"].append("编号体系不统一，建议使用单一编号风格")
        
        return numbering_analysis
    
    def analyze_signature_section(self, text: str) -> Dict[str, Any]:
        """Analyze signature section format"""
        signature_analysis = {
            "has_signature_section": False,
            "signature_elements": {},
            "format_completeness": 0,
            "layout_issues": [],
            "signature_score": 0
        }
        
        lines = text.split('\n')
        signature_section_start = -1
        
        # Find signature section
        for i, line in enumerate(lines):
            if re.search(r'签字|签名|盖章|签署', line):
                signature_section_start = i
                signature_analysis["has_signature_section"] = True
                break
        
        if signature_section_start >= 0:
            # Analyze signature section content
            signature_lines = lines[signature_section_start:]
            
            elements_to_check = {
                "party_a_signature": r'甲方.*?签字|甲方.*?签名',
                "party_b_signature": r'乙方.*?签字|乙方.*?签名',
                "party_a_seal": r'甲方.*?盖章|甲方.*?印章',
                "party_b_seal": r'乙方.*?盖章|乙方.*?印章',
                "date_field": r'日期|年.*?月.*?日',
                "representative": r'法定代表人|授权代表'
            }
            
            for element, pattern in elements_to_check.items():
                found = any(re.search(pattern, line) for line in signature_lines)
                signature_analysis["signature_elements"][element] = found
                if found:
                    signature_analysis["format_completeness"] += 1
            
            # Check layout issues
            if len(signature_lines) < 5:
                signature_analysis["layout_issues"].append("签署区过于简单，缺少必要元素")
            
            # Check for table-like structure
            has_table_structure = any('|' in line or '\t' in line for line in signature_lines)
            if not has_table_structure:
                signature_analysis["layout_issues"].append("建议使用表格形式组织签署信息")
        
        # Calculate signature score
        score = 0
        if signature_analysis["has_signature_section"]:
            score += 3
        score += signature_analysis["format_completeness"]
        if len(signature_analysis["layout_issues"]) == 0:
            score += 2
        
        signature_analysis["signature_score"] = min(score, 10)
        
        return signature_analysis
    
    def analyze_text_formatting(self, text: str) -> Dict[str, Any]:
        """Analyze text formatting and typography"""
        text_analysis = {
            "line_length_issues": [],
            "paragraph_structure": {},
            "special_formatting": {},
            "readability_score": 0
        }
        
        lines = text.split('\n')
        
        # Check line lengths
        long_lines = 0
        short_lines = 0
        
        for i, line in enumerate(lines):
            if line.strip():  # Non-empty lines
                if len(line) > 100:
                    long_lines += 1
                    if long_lines <= 3:  # Report first few issues
                        text_analysis["line_length_issues"].append(
                            f"第{i+1}行过长 ({len(line)} 字符)"
                        )
                elif len(line) < 10:
                    short_lines += 1
        
        # Analyze paragraph structure
        empty_lines = sum(1 for line in lines if not line.strip())
        non_empty_lines = len(lines) - empty_lines
        
        text_analysis["paragraph_structure"] = {
            "total_lines": len(lines),
            "content_lines": non_empty_lines,
            "empty_lines": empty_lines,
            "avg_paragraph_length": non_empty_lines // max(empty_lines, 1)
        }
        
        # Check special formatting
        text_analysis["special_formatting"] = {
            "has_bold_indicators": bool(re.search(r'\*\*.*?\*\*', text)),
            "has_emphasis": bool(re.search(r'重要|注意|特别', text)),
            "has_lists": bool(re.search(r'^\s*[-*]\s', text, re.MULTILINE)),
            "has_tables": bool(re.search(r'\|.*?\|', text))
        }
        
        # Calculate readability score
        score = 8  # Base score
        if long_lines > 5:
            score -= 2
        if empty_lines / len(lines) < 0.1:  # Too dense
            score -= 1
        if text_analysis["special_formatting"]["has_lists"]:
            score += 1
        
        text_analysis["readability_score"] = max(score, 0)
        
        return text_analysis
    
    def identify_layout_issues(self, text: str) -> List[Dict[str, str]]:
        """Identify layout and formatting issues"""
        issues = []
        lines = text.split('\n')
        
        # Check for inconsistent spacing
        consecutive_empty_lines = 0
        for i, line in enumerate(lines):
            if not line.strip():
                consecutive_empty_lines += 1
            else:
                if consecutive_empty_lines > 3:
                    issues.append({
                        "type": "spacing",
                        "line": i + 1,
                        "description": f"第{i+1}行前有过多空行 ({consecutive_empty_lines}行)"
                    })
                consecutive_empty_lines = 0
        
        # Check for alignment issues
        indent_levels = []
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                indent_levels.append(indent)
        
        if len(set(indent_levels)) > 5:  # Too many different indent levels
            issues.append({
                "type": "alignment",
                "line": 0,
                "description": f"发现{len(set(indent_levels))}种不同的缩进级别，建议统一"
            })
        
        # Check for special characters
        for i, line in enumerate(lines):
            if re.search(r'[^\u4e00-\u9fff\w\s\.,;:!?()[]{}"""''－—–\-+=<>/@#$%^&*|\\~`]', line):
                issues.append({
                    "type": "characters",
                    "line": i + 1,
                    "description": f"第{i+1}行包含特殊字符，可能影响显示"
                })
        
        return issues
    
    def generate_format_recommendations(self, text: str) -> List[Dict[str, str]]:
        """Generate format improvement recommendations"""
        recommendations = []
        
        # Title recommendations
        if not re.search(r'^.*?(合同|协议|契约)', text[:200]):
            recommendations.append({
                "category": "标题格式",
                "priority": "高",
                "recommendation": "建议在文档开头添加居中对齐的合同标题"
            })
        
        # Structure recommendations
        if not re.search(r'甲方.*?乙方', text):
            recommendations.append({
                "category": "结构完整性",
                "priority": "高", 
                "recommendation": "建议添加完整的当事人信息部分"
            })
        
        # Numbering recommendations
        numbering_styles = len(re.findall(r'第[一二三四五六七八九十\d]+条', text))
        arabic_numbering = len(re.findall(r'^\s*\d+\.', text, re.MULTILINE))
        
        if numbering_styles > 0 and arabic_numbering > 0:
            recommendations.append({
                "category": "编号体系",
                "priority": "中",
                "recommendation": "建议统一使用单一编号体系，如'第一条、第二条'或'1. 2. 3.'"
            })
        
        # Signature recommendations
        if not re.search(r'签字|签名|盖章', text):
            recommendations.append({
                "category": "签署区",
                "priority": "高",
                "recommendation": "建议在文档末尾添加标准的签署区，包含双方签字和盖章位置"
            })
        
        # Spacing recommendations
        lines = text.split('\n')
        if sum(1 for line in lines if not line.strip()) / len(lines) < 0.05:
            recommendations.append({
                "category": "版式设计",
                "priority": "中",
                "recommendation": "建议在段落和条款之间增加适当的空行，提高可读性"
            })
        
        return recommendations
    
    def calculate_compliance_score(self, analysis: Dict[str, Any]) -> int:
        """Calculate overall format compliance score"""
        scores = []
        
        # Collect all available scores
        if "document_structure" in analysis:
            scores.append(analysis["document_structure"].get("structure_score", 0))
        
        if "title_analysis" in analysis:
            scores.append(analysis["title_analysis"].get("title_score", 0))
        
        if "party_section" in analysis:
            scores.append(analysis["party_section"].get("party_score", 0))
        
        if "clause_formatting" in analysis:
            scores.append(analysis["clause_formatting"].get("clause_score", 0))
        
        if "signature_section" in analysis:
            scores.append(analysis["signature_section"].get("signature_score", 0))
        
        if "text_formatting" in analysis:
            scores.append(analysis["text_formatting"].get("readability_score", 0))
        
        # Calculate weighted average
        if scores:
            return sum(scores) // len(scores)
        else:
            return 5  # Default score
    
    def get_llm_format_analysis(self, text: str) -> str:
        """Get detailed format analysis from LLM"""
        analysis_prompt = f"""
        请对以下合同文档进行专业的格式分析：
        
        文档内容：{text[:1500]}...
        
        请从以下格式角度进行详细分析：
        1. 文档整体结构和布局
        2. 标题格式和位置是否恰当
        3. 当事人信息格式是否规范
        4. 条款编号和层次结构
        5. 段落格式和文本排版
        6. 签署区格式是否完整
        7. 专业性和可读性评估
        
        请提供具体的格式改进建议和最佳实践指导。
        """
        
        return self.call_llm(analysis_prompt)
    
    def format_analysis_results(self, analysis: Dict[str, Any]) -> str:
        """Format analysis results for output"""
        output = "=== 格式分析报告 ===\n\n"
        
        # Overall compliance score
        output += f"格式规范性评分：{analysis.get('compliance_score', 0)}/10\n\n"
        
        # Document structure
        structure = analysis.get("document_structure", {})
        output += "--- 文档结构 ---\n"
        output += f"结构完整性：{structure.get('structure_score', 0)}/10\n"
        output += f"包含标题：{'是' if structure.get('has_title') else '否'}\n"
        output += f"包含当事人信息：{'是' if structure.get('has_parties_section') else '否'}\n"
        output += f"包含正文内容：{'是' if structure.get('has_main_content') else '否'}\n"
        output += f"包含签署区：{'是' if structure.get('has_signature_section') else '否'}\n"
        
        section_order = structure.get("section_order", [])
        if section_order:
            output += f"章节顺序：{' → '.join(section_order)}\n"
        output += "\n"
        
        # Title analysis
        title = analysis.get("title_analysis", {})
        output += "--- 标题格式 ---\n"
        output += f"标题评分：{title.get('title_score', 0)}/10\n"
        if title.get("title_found"):
            output += f"标题内容：{title.get('title_text', '未找到')}\n"
            output += f"标题位置：{title.get('title_position', '未确定')}\n"
        
        title_issues = title.get("format_issues", [])
        if title_issues:
            output += "标题问题：\n"
            for issue in title_issues:
                output += f"  - {issue}\n"
        output += "\n"
        
        # Party section
        party = analysis.get("party_section", {})
        output += "--- 当事人信息 ---\n"
        output += f"当事人格式评分：{party.get('party_score', 0)}/10\n"
        
        parties = party.get("parties_found", [])
        output += f"发现当事人：{len(parties)}个\n"
        for p in parties:
            output += f"  - {p['label']}：{p['info'].get('name', '未明确')}\n"
        output += "\n"
        
        # Clause formatting
        clause = analysis.get("clause_formatting", {})
        output += "--- 条款格式 ---\n"
        output += f"条款格式评分：{clause.get('clause_score', 0)}/10\n"
        output += f"条款数量：{clause.get('clause_count', 0)}\n"
        output += f"编号一致性：{'是' if clause.get('numbering_consistency') else '否'}\n"
        output += f"缩进一致性：{'是' if clause.get('indentation_consistency') else '否'}\n"
        
        spacing_issues = clause.get("spacing_issues", [])
        if spacing_issues:
            output += f"发现{len(spacing_issues)}个间距问题\n"
        
        formatting_issues = clause.get("formatting_issues", [])
        if formatting_issues:
            output += f"发现{len(formatting_issues)}个格式问题\n"
        output += "\n"
        
        # Numbering system
        numbering = analysis.get("numbering_system", {})
        output += "--- 编号体系 ---\n"
        output += f"编号风格：{numbering.get('numbering_style', '未识别')}\n"
        output += f"一致性评分：{numbering.get('consistency_score', 0)}/10\n"
        
        numbering_errors = numbering.get("numbering_errors", [])
        if numbering_errors:
            for error in numbering_errors:
                output += f"  - {error}\n"
        output += "\n"
        
        # Signature section
        signature = analysis.get("signature_section", {})
        output += "--- 签署区 ---\n"
        output += f"签署区评分：{signature.get('signature_score', 0)}/10\n"
        output += f"包含签署区：{'是' if signature.get('has_signature_section') else '否'}\n"
        
        if signature.get("has_signature_section"):
            elements = signature.get("signature_elements", {})
            output += f"格式完整性：{signature.get('format_completeness', 0)}/6\n"
            
            layout_issues = signature.get("layout_issues", [])
            if layout_issues:
                output += "布局问题：\n"
                for issue in layout_issues:
                    output += f"  - {issue}\n"
        output += "\n"
        
        # Text formatting
        text_format = analysis.get("text_formatting", {})
        output += "--- 文本格式 ---\n"
        output += f"可读性评分：{text_format.get('readability_score', 0)}/10\n"
        
        line_issues = text_format.get("line_length_issues", [])
        if line_issues:
            output += f"行长度问题：{len(line_issues)}个\n"
            for issue in line_issues[:3]:  # Show first 3
                output += f"  - {issue}\n"
        
        paragraph = text_format.get("paragraph_structure", {})
        output += f"总行数：{paragraph.get('total_lines', 0)}\n"
        output += f"内容行数：{paragraph.get('content_lines', 0)}\n"
        output += "\n"
        
        # Layout issues
        layout_issues = analysis.get("layout_issues", [])
        if layout_issues:
            output += f"--- 布局问题 ({len(layout_issues)}项) ---\n"
            for issue in layout_issues[:5]:  # Show first 5
                output += f"• {issue['description']}\n"
            output += "\n"
        
        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            output += "--- 格式改进建议 ---\n"
            for i, rec in enumerate(recommendations, 1):
                output += f"{i}. [{rec['priority']}] {rec['recommendation']}\n"
            output += "\n"
        
        # Detailed analysis
        detailed_analysis = analysis.get("detailed_analysis", "")
        if detailed_analysis:
            output += "--- 详细格式分析 ---\n"
            output += detailed_analysis
        
        return output

if __name__ == "__main__":
    agent = FormatAgent()
    agent.run(Config.AGENT_PORTS["format"])