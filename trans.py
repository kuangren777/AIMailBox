#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件翻译模块
提供邮件内容的大模型翻译功能
"""

import json
import logging
import requests
from typing import Dict, Optional, Tuple
from config import config
from email_processor import ProcessedEmail

logger = logging.getLogger("mail_translator")

class EmailTranslator:
    """邮件翻译器"""
    
    def __init__(self):
        self.api_url = config.AI_API_URL
        self.api_key = config.AI_API_KEY
        self.model = config.AI_MODEL
        self.max_tokens = config.AI_MAX_TOKENS
        self.temperature = config.AI_TEMPERATURE
    
    def translate_email(self, processed_email: ProcessedEmail, target_language: str = 'zh') -> Dict:
        """
        翻译邮件内容
        
        Args:
            processed_email: 已处理的邮件对象
            target_language: 目标语言 ('zh', 'en', 'ja', 'ko', 'fr', 'de', 'es', 'ru')
        
        Returns:
            Dict: 翻译结果
        """
        try:
            # 检测原始语言
            original_language = self._detect_language(processed_email.text_content)
            
            # 如果原始语言与目标语言相同，直接返回
            if original_language == target_language:
                return {
                    'success': True,
                    'original_language': original_language,
                    'target_language': target_language,
                    'translated_subject': processed_email.subject,
                    'translated_content': processed_email.text_content,
                    'message': '原始语言与目标语言相同，无需翻译'
                }
            
            # 翻译主题
            translated_subject = self._translate_text(
                processed_email.subject, 
                original_language, 
                target_language
            )
            
            # 翻译内容
            translated_content = self._translate_text(
                processed_email.text_content, 
                original_language, 
                target_language
            )
            
            return {
                'success': True,
                'original_language': original_language,
                'target_language': target_language,
                'original_subject': processed_email.subject,
                'original_content': processed_email.text_content[:500] + '...' if len(processed_email.text_content) > 500 else processed_email.text_content,
                'translated_subject': translated_subject,
                'translated_content': translated_content,
                'from_email': processed_email.from_email,
                'to_email': processed_email.to_email,
                'message_id': processed_email.message_id
            }
            
        except Exception as e:
            logger.error(f"邮件翻译失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'original_subject': processed_email.subject,
                'original_content': processed_email.text_content[:200] + '...' if len(processed_email.text_content) > 200 else processed_email.text_content
            }
    
    def _detect_language(self, text: str) -> str:
        """
        检测文本语言
        
        Args:
            text: 待检测的文本
        
        Returns:
            str: 语言代码
        """
        if not text:
            return 'unknown'
        
        # 简单的语言检测逻辑
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        total_chars = len(text.replace(' ', '').replace('\n', ''))
        
        if total_chars == 0:
            return 'unknown'
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return 'zh'
        elif any(char in text.lower() for char in 'abcdefghijklmnopqrstuvwxyz'):
            return 'en'
        else:
            return 'unknown'
    
    def _translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        使用大模型翻译文本
        
        Args:
            text: 待翻译的文本
            source_lang: 源语言
            target_lang: 目标语言
        
        Returns:
            str: 翻译后的文本
        """
        if not text or not text.strip():
            return text
        
        # 语言映射
        lang_map = {
            'zh': '中文',
            'en': '英文',
            'ja': '日文',
            'ko': '韩文',
            'fr': '法文',
            'de': '德文',
            'es': '西班牙文',
            'ru': '俄文'
        }
        
        source_name = lang_map.get(source_lang, source_lang)
        target_name = lang_map.get(target_lang, target_lang)
        
        # 构建翻译提示
        prompt = f"""请将以下{source_name}文本翻译成{target_name}，保持原文的语气、格式和专业术语。只返回翻译结果，不要添加任何解释或说明。

原文：
{text}

翻译："""
        
        try:
            # 调用AI API
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            }
            
            data = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': min(self.max_tokens, len(text) * 2 + 1000),
                'temperature': 0.3,  # 翻译使用较低的温度以保证准确性
                'stream': False
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    translated_text = result['choices'][0]['message']['content'].strip()
                    return translated_text
                else:
                    logger.error(f"AI API返回格式错误: {result}")
                    return text
            else:
                logger.error(f"AI API请求失败: {response.status_code} - {response.text}")
                return text
                
        except requests.exceptions.Timeout:
            logger.error("AI API请求超时")
            return text
        except requests.exceptions.RequestException as e:
            logger.error(f"AI API请求异常: {e}")
            return text
        except Exception as e:
            logger.error(f"翻译过程中发生错误: {e}")
            return text
    
    def get_supported_languages(self) -> Dict[str, str]:
        """
        获取支持的语言列表
        
        Returns:
            Dict[str, str]: 语言代码到语言名称的映射
        """
        return {
            'zh': '中文',
            'en': '英文',
            'ja': '日文',
            'ko': '韩文',
            'fr': '法文',
            'de': '德文',
            'es': '西班牙文',
            'ru': '俄文'
        }
    
    def batch_translate(self, texts: list, source_lang: str, target_lang: str) -> list:
        """
        批量翻译文本
        
        Args:
            texts: 待翻译的文本列表
            source_lang: 源语言
            target_lang: 目标语言
        
        Returns:
            list: 翻译结果列表
        """
        results = []
        for text in texts:
            try:
                translated = self._translate_text(text, source_lang, target_lang)
                results.append({
                    'success': True,
                    'original': text,
                    'translated': translated
                })
            except Exception as e:
                results.append({
                    'success': False,
                    'original': text,
                    'error': str(e)
                })
        return results

# 创建全局翻译器实例
translator = EmailTranslator()