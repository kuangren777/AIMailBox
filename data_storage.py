import json
import os
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from config import config
from email_processor import ProcessedEmail

logger = logging.getLogger("data_storage")

class DataStorage:
    """数据存储管理器"""
    
    def __init__(self):
        self.emails_file = config.EMAILS_FILE
        self.logs_file = config.EMAIL_LOGS_FILE
        
        # 确保文件存在
        self._ensure_files_exist()
    
    def _ensure_files_exist(self):
        """确保存储文件存在"""
        for file_path in [self.emails_file, self.logs_file]:
            if not os.path.exists(file_path):
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump([], f)
                    logger.info(f"创建存储文件: {file_path}")
                except Exception as e:
                    logger.error(f"创建存储文件失败 {file_path}: {e}")
    
    def save_email(self, processed_email: ProcessedEmail, analysis_result: Optional[Dict] = None, 
                   send_result: Optional[Dict] = None) -> bool:
        """保存邮件数据
        
        Args:
            processed_email: 处理后的邮件对象
            analysis_result: AI分析结果
            send_result: 发送结果
            
        Returns:
            保存是否成功
        """
        try:
            # 构建邮件记录
            email_record = {
                "timestamp": datetime.now().isoformat(),
                "email_data": {
                    "from": processed_email.from_email,
                    "to": processed_email.to_email,
                    "subject": processed_email.subject,
                    "date": processed_email.date,
                    "message_id": processed_email.message_id,
                    "text_content": processed_email.text_content,
                    "html_content": processed_email.html_content,
                    "attachments": processed_email.attachments,
                    "raw_size": processed_email.raw_size
                },
                "analysis_result": analysis_result,
                "send_result": send_result,
                "processing_status": "completed"
            }
            
            # 读取现有邮件
            emails = self._load_emails()
            
            # 添加新邮件
            emails.append(email_record)
            
            # 保存邮件
            success = self._save_emails(emails)
            
            if success:
                logger.info(f"邮件保存成功: {processed_email.from_email} -> {processed_email.subject}")
            else:
                logger.error(f"邮件保存失败: {processed_email.from_email} -> {processed_email.subject}")
            
            return success
            
        except Exception as e:
            logger.error(f"保存邮件异常: {e}")
            return False
    
    def _load_emails(self) -> List[Dict]:
        """加载邮件数据"""
        try:
            if os.path.exists(self.emails_file):
                with open(self.emails_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载邮件数据失败: {e}")
            return []
    
    def _save_emails(self, emails: List[Dict]) -> bool:
        """保存邮件数据"""
        try:
            with open(self.emails_file, 'w', encoding='utf-8') as f:
                json.dump(emails, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存邮件数据失败: {e}")
            return False
    
    def get_emails(self, limit: int = 10, offset: int = 0) -> Dict[str, Any]:
        """获取邮件列表
        
        Args:
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            邮件列表和统计信息
        """
        try:
            emails = self._load_emails()
            total_count = len(emails)
            
            # 按时间倒序排列（最新的在前）
            emails.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 分页
            start_idx = offset
            end_idx = offset + limit
            paginated_emails = emails[start_idx:end_idx]
            
            return {
                "emails": paginated_emails,
                "total_count": total_count,
                "showing": len(paginated_emails),
                "offset": offset,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"获取邮件列表失败: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "showing": 0,
                "offset": offset,
                "limit": limit,
                "error": str(e)
            }
    
    def search_emails(self, query: str, limit: int = 10) -> List[Dict]:
        """搜索邮件
        
        Args:
            query: 搜索关键词
            limit: 返回数量限制
            
        Returns:
            匹配的邮件列表
        """
        try:
            emails = self._load_emails()
            query_lower = query.lower()
            
            matched_emails = []
            for email in emails:
                email_data = email.get('email_data', {})
                
                # 搜索字段
                search_fields = [
                    email_data.get('from', ''),
                    email_data.get('subject', ''),
                    email_data.get('text_content', '') or '',
                    email_data.get('html_content', '') or ''
                ]
                
                # 检查是否匹配
                if any(query_lower in field.lower() for field in search_fields if field):
                    matched_emails.append(email)
                
                if len(matched_emails) >= limit:
                    break
            
            return matched_emails
            
        except Exception as e:
            logger.error(f"搜索邮件失败: {e}")
            return []
    
    def get_email_by_message_id(self, message_id: str) -> Optional[Dict]:
        """根据Message-ID获取邮件"""
        try:
            emails = self._load_emails()
            for email in emails:
                email_data = email.get('email_data', {})
                if email_data.get('message_id') == message_id:
                    return email
            return None
        except Exception as e:
            logger.error(f"根据Message-ID获取邮件失败: {e}")
            return None
    
    def log_activity(self, activity_type: str, details: Dict, level: str = "info") -> bool:
        """记录活动日志
        
        Args:
            activity_type: 活动类型（如：email_received, email_sent, analysis_completed等）
            details: 详细信息
            level: 日志级别
            
        Returns:
            记录是否成功
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "activity_type": activity_type,
                "level": level,
                "details": details
            }
            
            # 读取现有日志
            logs = self._load_logs()
            
            # 添加新日志
            logs.append(log_entry)
            
            # 限制日志数量（保留最近1000条）
            if len(logs) > 1000:
                logs = logs[-1000:]
            
            # 保存日志
            return self._save_logs(logs)
            
        except Exception as e:
            logger.error(f"记录活动日志失败: {e}")
            return False
    
    def _load_logs(self) -> List[Dict]:
        """加载日志数据"""
        try:
            if os.path.exists(self.logs_file):
                with open(self.logs_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载日志数据失败: {e}")
            return []
    
    def _save_logs(self, logs: List[Dict]) -> bool:
        """保存日志数据"""
        try:
            with open(self.logs_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"保存日志数据失败: {e}")
            return False
    
    def get_logs(self, limit: int = 50, activity_type: Optional[str] = None) -> List[Dict]:
        """获取日志列表
        
        Args:
            limit: 返回数量限制
            activity_type: 活动类型过滤
            
        Returns:
            日志列表
        """
        try:
            logs = self._load_logs()
            
            # 按活动类型过滤
            if activity_type:
                logs = [log for log in logs if log.get('activity_type') == activity_type]
            
            # 按时间倒序排列
            logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # 限制数量
            return logs[:limit]
            
        except Exception as e:
            logger.error(f"获取日志列表失败: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            emails = self._load_emails()
            logs = self._load_logs()
            
            # 邮件统计
            total_emails = len(emails)
            today = datetime.now().date().isoformat()
            
            today_emails = sum(1 for email in emails 
                             if email.get('timestamp', '').startswith(today))
            
            # 发送统计
            successful_sends = sum(1 for email in emails 
                                 if email.get('send_result', {}).get('success', False))
            
            # AI分析统计
            analyzed_emails = sum(1 for email in emails 
                                if email.get('analysis_result') is not None)
            
            return {
                "total_emails": total_emails,
                "today_emails": today_emails,
                "successful_sends": successful_sends,
                "analyzed_emails": analyzed_emails,
                "total_logs": len(logs),
                "success_rate": (successful_sends / total_emails * 100) if total_emails > 0 else 0,
                "analysis_rate": (analyzed_emails / total_emails * 100) if total_emails > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {
                "total_emails": 0,
                "today_emails": 0,
                "successful_sends": 0,
                "analyzed_emails": 0,
                "total_logs": 0,
                "success_rate": 0,
                "analysis_rate": 0,
                "error": str(e)
            }
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """清理旧数据
        
        Args:
            days: 保留天数
            
        Returns:
            清理统计
        """
        try:
            from datetime import timedelta
            
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # 清理邮件
            emails = self._load_emails()
            original_email_count = len(emails)
            emails = [email for email in emails 
                     if email.get('timestamp', '') >= cutoff_date]
            cleaned_emails = original_email_count - len(emails)
            
            # 清理日志
            logs = self._load_logs()
            original_log_count = len(logs)
            logs = [log for log in logs 
                   if log.get('timestamp', '') >= cutoff_date]
            cleaned_logs = original_log_count - len(logs)
            
            # 保存清理后的数据
            self._save_emails(emails)
            self._save_logs(logs)
            
            logger.info(f"数据清理完成: 清理了{cleaned_emails}封邮件，{cleaned_logs}条日志")
            
            return {
                "cleaned_emails": cleaned_emails,
                "cleaned_logs": cleaned_logs,
                "remaining_emails": len(emails),
                "remaining_logs": len(logs)
            }
            
        except Exception as e:
            logger.error(f"清理旧数据失败: {e}")
            return {
                "cleaned_emails": 0,
                "cleaned_logs": 0,
                "remaining_emails": 0,
                "remaining_logs": 0,
                "error": str(e)
            }

# 创建全局存储实例
storage = DataStorage()