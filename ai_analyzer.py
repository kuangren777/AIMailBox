import json
import logging
import re
from typing import Dict, List, Optional, Tuple
import requests
from config import config

logger = logging.getLogger("ai_analyzer")

class EmailAnalyzer:
    """邮件内容分析器，使用AI分析邮件内容并生成回复"""
    
    def __init__(self):
        self.api_url = config.AI_API_URL
        self.api_key = config.AI_API_KEY
        self.model = config.AI_MODEL
        self.max_tokens = config.AI_MAX_TOKENS
        self.temperature = config.AI_TEMPERATURE
    
    def detect_language(self, text: str) -> str:
        """检测文本语言"""
        if not text:
            return 'zh'
        
        # 简单的语言检测逻辑
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        
        if chinese_chars > english_chars:
            return 'zh'
        elif english_chars > 0:
            return 'en'
        else:
            # 检测其他常见语言
            if re.search(r'[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]', text.lower()):
                return 'fr'  # 法语
            elif re.search(r'[äöüß]', text.lower()):
                return 'de'  # 德语
            elif re.search(r'[áéíóúñü]', text.lower()):
                return 'es'  # 西班牙语
            else:
                return 'en'  # 默认英语
    
    def analyze_email_content(self, email_content: str, sender: str = "") -> Dict:
        """分析邮件内容"""
        if not email_content:
            return self._get_default_analysis(email_content)
        
        # 检测语言
        detected_language = self.detect_language(email_content)
        
        # 构建分析提示
        prompt = self._build_analysis_prompt(email_content, detected_language)
        
        # 调用AI API
        ai_response = self._call_ai_api(prompt)
        
        if ai_response:
            try:
                analysis = self._parse_ai_response(ai_response)
                analysis['detected_language'] = detected_language
                analysis['sender'] = sender
                return analysis
            except Exception as e:
                logger.error(f"解析AI响应失败: {e}")
        
        # 返回默认分析
        return self._get_default_analysis(email_content, detected_language)
    
    def _build_analysis_prompt(self, content: str, language: str) -> str:
        """构建AI分析提示"""
        return f"""你是一个邮件助手，当我给你邮件的时候，你需要根据我给你的指令（如有）：
1. 提取出这个邮件是要干什么的，目前的进展有哪些（中文回答）
2. 判断是否需要回信（中文回答）
3. 如果需要我提供的信息，可以先问我，我会提供。当你拿到可以写回信的信息的时候，你可以开始写作。
4. 如果需要回信，请给出回信的具体内容。（英文）
我也会给你提要求，需要你帮我写邮件。

邮件内容：
{content}

请严格按照以下JSON格式返回分析结果，必须用```json ```包围：

```json
{{
  "intent": "邮件意图（inquiry/request/complaint/meeting/order/support/other）",
  "urgency": "紧急程度（low/medium/high）",
  "can_auto_reply": "是否可以自动回复（true/false）",
  "chinese_content": "邮件的中文摘要和目的分析",
  "todo_items": ["需要完成的事项列表（需要尽可能详细）"],
  "main_topic": "主要话题",
  "requires_info": "如果不能自动回复，需要什么额外信息，需要尽可能详细",
  "sentiment": "情感倾向（positive/neutral/negative）",
  "need_reply": "是否需要回信（true/false）",
  "reply_content": "如果需要回信，提供英文回信内容，如果不需要则为空字符串"
}}
```

只返回JSON格式的内容，用```json ```包围，不要其他文字。"""
    
    def _call_ai_api(self, prompt: str) -> Optional[str]:
        """调用AI API"""
        if not self.api_key:
            logger.warning("AI API密钥未配置")
            return None
        
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': self.max_tokens,
                'temperature': self.temperature
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                logger.error(f"AI API调用失败: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"AI API调用异常: {e}")
            return None
    
    def _parse_ai_response(self, response: str) -> Dict:
        """解析AI响应"""
        try:
            # 首先尝试提取```json ```包围的JSON内容
            json_code_block_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
            if json_code_block_match:
                json_content = json_code_block_match.group(1).strip()
                return json.loads(json_content)
            
            # 如果没有找到代码块，尝试提取普通JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(response)
        except json.JSONDecodeError:
            logger.error(f"无法解析AI响应为JSON: {response}")
            raise
    
    def _get_default_analysis(self, content: str, language: str = 'zh') -> Dict:
        """获取默认分析结果"""
        return {
            'intent': 'other',
            'urgency': 'medium',
            'can_auto_reply': False,
            'chinese_content': content[:100] if language == 'zh' else '需要人工翻译',
            'todo_items': ['人工处理邮件'],
            'main_topic': '未知主题',
            'requires_info': '需要人工分析',
            'sentiment': 'neutral',
            'detected_language': language,
            'need_reply': True,
            'reply_content': ''
        }
    
    def generate_reply(self, analysis: Dict, original_subject: str, original_content: str = "", is_forwarded_email: bool = False) -> Tuple[str, str]:
        """生成回复邮件
        
        Args:
            analysis: AI分析结果
            original_subject: 原邮件主题
            original_content: 原邮件内容
            is_forwarded_email: 是否为用户转发的邮件（需要回复给原发件人）
        """
        # 确定回复语言策略
        reply_language = self._determine_reply_language(analysis, is_forwarded_email)
        
        # 如果AI已经提供了回复内容，直接使用
        if analysis.get('reply_content') and analysis.get('need_reply', False):
            reply_subject = f"Re: {original_subject}"
            # 在AI提供的回复内容中也添加原邮件引用
            reply_with_quote = self._add_original_quote(analysis['reply_content'], original_content, reply_language)
            return reply_subject, reply_with_quote
        
        # 否则使用原有逻辑
        if analysis.get('can_auto_reply', False):
            return self._generate_auto_reply(analysis, original_subject, original_content, reply_language, is_forwarded_email)
        else:
            return self._generate_info_request_reply(analysis, original_subject, original_content, reply_language, is_forwarded_email)
    
    def _determine_reply_language(self, analysis: Dict, is_forwarded_email: bool) -> str:
        """确定回复邮件的语言策略
        
        Args:
            analysis: AI分析结果
            is_forwarded_email: 是否为用户转发的邮件
            
        Returns:
            回复语言代码 ('zh' 或 'en')
        """
        if is_forwarded_email:
            # 用户转发的邮件，使用原邮件的语言回复
            return analysis.get('detected_language', 'zh')
        else:
            # 系统详细内容邮件，永远使用中文
            return 'zh'
    
    def _generate_info_request_reply(self, analysis: Dict, subject: str, original_content: str, language: str, is_forwarded_email: bool = False) -> Tuple[str, str]:
        """生成信息请求回复"""
        requires_info = analysis.get('requires_info', '更多详细信息')
        main_topic = analysis.get('main_topic', '您的请求')
        
        if language == 'en' and is_forwarded_email:
            reply_subject = f"Re: {subject} - Additional Information Needed"
            reply_body = f"""Dear Sender,

Thank you for your email regarding "{main_topic}".

To better assist you, we need some additional information: {requires_info}

Could you please provide these details so we can give you a more accurate response?

Best regards,
AI Assistant
{config.SES_FROM_EMAIL}"""
        else:
            # 系统详细回复或中文邮件，使用详细的中文回复
            reply_subject = f"Re: {subject} - 需要补充信息"
            detailed_info = self._generate_detailed_info_request(analysis, main_topic, requires_info)
            reply_body = f"""您好！

感谢您关于"{main_topic}"的邮件。我们已仔细审阅了您的来信内容。

{detailed_info}

为了能够为您提供最准确、最有针对性的解决方案，我们需要您提供以下补充信息：

{self._format_required_info(requires_info)}

请您在回复邮件时详细提供上述信息。我们的技术团队会根据您提供的具体情况，为您制定个性化的解决方案。

如果您在提供信息时遇到任何困难，或者有其他相关问题，请随时与我们联系。我们承诺会在收到您的详细信息后24小时内给出专业回复。

此致
敬礼！

AI智能助手
技术支持团队
ai@kr777.top

---
本邮件由AI智能系统自动生成，如需人工客服协助，请在邮件中注明"转人工客服"。"""
        
        # 添加原邮件引用
        reply_body = self._add_original_quote(reply_body, original_content, language)
        return reply_subject, reply_body
    
    def _generate_auto_reply(self, analysis: Dict, subject: str, original_content: str, language: str, is_forwarded_email: bool = False) -> Tuple[str, str]:
        """生成自动回复"""
        main_topic = analysis.get('main_topic', '您的请求')
        summary = analysis.get('chinese_content', '')
        
        if language == 'en' and is_forwarded_email:
            # 用户转发的英文邮件，使用英文回复
            reply_subject = f"Re: {subject}"
            reply_body = f"""Dear Sender,

Thank you for your email regarding "{main_topic}".

We have received and reviewed your message. {summary[:200] if summary else 'We will process your request accordingly.'}

We will get back to you soon.

Best regards,
AI Assistant
ai@kr777.top"""
        else:
            # 系统详细回复或中文邮件，使用详细的中文回复
            reply_subject = f"Re: {subject}"
            detailed_response = self._generate_detailed_auto_reply(analysis, main_topic, summary)
            reply_body = f"""您好！

感谢您关于"{main_topic}"的邮件。我们已收到并仔细审阅了您的来信。

{detailed_response}

我们的处理流程如下：
1. 邮件内容分析和分类（已完成）
2. 相关部门分配和评估（进行中）
3. 制定详细解决方案（24小时内）
4. 专业回复和后续跟进（48小时内）

在处理您的请求期间，如果您有任何补充信息或紧急情况，请随时回复此邮件。我们会优先处理您的后续来信。

我们承诺为您提供最专业、最及时的服务。感谢您对我们的信任与支持。

此致
敬礼！

AI智能助手
客户服务中心
ai@kr777.top

---
邮件处理编号：{self._generate_ticket_id()}
如需查询处理进度，请在回复中提供此编号。"""
        
        # 添加原邮件引用
        reply_body = self._add_original_quote(reply_body, original_content, language)
        return reply_subject, reply_body
    
    def _add_original_quote(self, reply_body: str, original_content: str, language: str) -> str:
        """在回复邮件中添加原邮件引用"""
        if not original_content or not original_content.strip():
            return reply_body
        
        # 清理原邮件内容，移除多余的空行和格式
        cleaned_content = self._clean_original_content(original_content)
        
        if language == 'en':
            quote_header = "\n\n--- Original Message ---\n"
        else:
            quote_header = "\n\n--- 原邮件 ---\n"
        
        # 为原邮件内容添加引用前缀
        quoted_lines = []
        for line in cleaned_content.split('\n'):
            quoted_lines.append(f"> {line}")
        
        quoted_content = '\n'.join(quoted_lines)
        
        return reply_body + quote_header + quoted_content
    
    def _clean_original_content(self, content: str) -> str:
        """清理原邮件内容"""
        if not content:
            return ""
        
        # 移除HTML标签（如果有）
        import re
        content = re.sub(r'<[^>]+>', '', content)
        
        # 移除多余的空行
        lines = content.split('\n')
        cleaned_lines = []
        prev_empty = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if not prev_empty:
                    cleaned_lines.append('')
                prev_empty = True
            else:
                cleaned_lines.append(line)
                prev_empty = False
        
        # 移除开头和结尾的空行
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()
        
        # 限制内容长度，避免引用过长
        result = '\n'.join(cleaned_lines)
        # if len(result) > 500:
        #     result = result[:500] + '\n[内容已截断...]'
        
        return result
    
    def _generate_detailed_info_request(self, analysis: Dict, main_topic: str, requires_info: str) -> str:
        """生成详细的信息请求说明"""
        intent = analysis.get('intent', '未知')
        urgency = analysis.get('urgency', 'normal')
        
        detail_text = f"根据我们的AI智能分析系统判断，您的邮件属于'{intent}'类型，紧急程度为'{urgency}'。"
        
        if urgency == 'high':
            detail_text += "鉴于此事的紧急性，我们已将您的邮件标记为高优先级处理。"
        elif urgency == 'low':
            detail_text += "我们会按照标准流程为您处理此事。"
        
        return detail_text
    
    def _generate_detailed_auto_reply(self, analysis: Dict, main_topic: str, summary: str) -> str:
        """生成详细的自动回复内容"""
        intent = analysis.get('intent', '未知')
        urgency = analysis.get('urgency', 'normal')
        todo_items = analysis.get('todo_items', [])
        
        detail_parts = []
        
        # 添加分析结果
        detail_parts.append(f"经过我们的AI智能分析系统处理，您的邮件已被识别为'{intent}'类型。")
        
        # 添加内容摘要
        if summary:
            detail_parts.append(f"邮件内容摘要：{summary[:300]}")
        
        # 添加待办事项
        if todo_items:
            detail_parts.append("我们已为您的请求生成以下处理要点：")
            for i, item in enumerate(todo_items[:5], 1):
                detail_parts.append(f"{i}. {item}")
        
        # 添加紧急程度说明
        if urgency == 'high':
            detail_parts.append("⚠️ 重要提醒：您的邮件已被标记为高优先级，我们会加急处理。")
        elif urgency == 'medium':
            detail_parts.append("📋 处理说明：您的邮件为中等优先级，我们会在标准时间内处理。")
        
        return "\n\n".join(detail_parts)
    
    def _format_required_info(self, requires_info: str) -> str:
        """格式化所需信息列表"""
        if not requires_info:
            return "• 更多详细信息"
        
        # 如果是逗号分隔的列表，转换为项目符号格式
        if ',' in requires_info:
            items = [item.strip() for item in requires_info.split(',')]
            return "\n".join([f"• {item}" for item in items if item])
        else:
            return f"• {requires_info}"
    
    def _generate_ticket_id(self) -> str:
        """生成邮件处理编号"""
        import time
        import random
        timestamp = str(int(time.time()))
        random_suffix = str(random.randint(1000, 9999))
        return f"TK{timestamp[-6:]}{random_suffix}"

# 创建全局分析器实例
analyzer = EmailAnalyzer()