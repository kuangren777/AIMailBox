import logging
import smtplib
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import boto3
from botocore.exceptions import ClientError
from config import config

logger = logging.getLogger("email_sender")

class EmailSender:
    """邮件发送器"""
    
    def __init__(self):
        self.ses_client = None
        self.smtp_config = {
            'server': config.SMTP_SERVER,
            'port': config.SMTP_PORT,
            'username': config.SMTP_USERNAME,
            'password': config.SMTP_PASSWORD
        }
        self.ses_config = {
            'region': config.AWS_REGION,
            'access_key_id': config.AWS_ACCESS_KEY_ID,
            'secret_access_key': config.AWS_SECRET_ACCESS_KEY,
            'from_email': config.SES_FROM_EMAIL
        }
        
        # 初始化SES客户端
        self._init_ses_client()
    
    def _init_ses_client(self):
        """初始化SES客户端"""
        try:
            self.ses_client = boto3.client(
                'ses',
                region_name=self.ses_config['region'],
                aws_access_key_id=self.ses_config['access_key_id'],
                aws_secret_access_key=self.ses_config['secret_access_key']
            )
            logger.info(f"SES客户端初始化成功，区域: {self.ses_config['region']}")
        except Exception as e:
            logger.error(f"SES客户端初始化失败: {e}")
            self.ses_client = None
    
    def send_email_ses(self, to_email: str, subject: str, body_text: str, 
                       body_html: Optional[str] = None, reply_to: Optional[str] = None) -> Optional[str]:
        """使用AWS SES发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body_text: 纯文本内容
            body_html: HTML内容（可选）
            reply_to: 回复地址（可选）
            
        Returns:
            MessageId或None（失败时）
        """
        if not self.ses_client:
            logger.error("SES客户端未初始化")
            return None
        
        try:
            # 构建邮件体
            body = {'Text': {'Data': body_text, 'Charset': 'UTF-8'}}
            if body_html:
                body['Html'] = {'Data': body_html, 'Charset': 'UTF-8'}
            
            # 构建发送参数
            send_params = {
                'Source': self.ses_config['from_email'],
                'Destination': {'ToAddresses': [to_email]},
                'Message': {
                    'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                    'Body': body
                }
            }
            
            # 添加回复地址
            if reply_to:
                send_params['ReplyToAddresses'] = [reply_to]
            
            response = self.ses_client.send_email(**send_params)
            
            message_id = response['MessageId']
            logger.info(f"SES邮件发送成功: MessageId={message_id}, To={to_email}")
            return message_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"SES发送失败 [{error_code}]: {error_message}, To={to_email}")
            return None
        except Exception as e:
            logger.error(f"SES发送异常: {e}, To={to_email}")
            return None
    
    def send_email_smtp(self, to_email: str, subject: str, body_text: str, 
                        body_html: Optional[str] = None, reply_to: Optional[str] = None) -> bool:
        """使用SMTP发送邮件
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body_text: 纯文本内容
            body_html: HTML内容（可选）
            reply_to: 回复地址（可选）
            
        Returns:
            发送是否成功
        """
        try:
            # 创建邮件对象
            if body_html:
                msg = MIMEMultipart('alternative')
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                html_part = MIMEText(body_html, 'html', 'utf-8')
                msg.attach(text_part)
                msg.attach(html_part)
            else:
                msg = MIMEText(body_text, 'plain', 'utf-8')
            
            # 设置邮件头
            msg['Subject'] = subject
            msg['From'] = self.smtp_config['username']
            msg['To'] = to_email
            
            if reply_to:
                msg['Reply-To'] = reply_to
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_config['server'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)
            
            logger.info(f"SMTP邮件发送成功: To={to_email}")
            return True
            
        except Exception as e:
            logger.error(f"SMTP发送失败: {e}, To={to_email}")
            return False
    
    def send_email(self, to_email: str, subject: str, body_text: str, 
                   body_html: Optional[str] = None, reply_to: Optional[str] = None, 
                   prefer_ses: bool = True) -> Dict[str, Any]:
        """发送邮件（自动选择发送方式）
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body_text: 纯文本内容
            body_html: HTML内容（可选）
            reply_to: 回复地址（可选）
            prefer_ses: 是否优先使用SES
            
        Returns:
            发送结果字典
        """
        result = {
            'success': False,
            'method': None,
            'message_id': None,
            'error': None
        }
        
        # 提取纯净的邮箱地址
        clean_email = self.extract_email_address(to_email)
        
        # 优先尝试SES
        if prefer_ses and self.ses_client:
            message_id = self.send_email_ses(clean_email, subject, body_text, body_html, reply_to)
            if message_id:
                result.update({
                    'success': True,
                    'method': 'SES',
                    'message_id': message_id
                })
                return result
            else:
                result['error'] = 'SES发送失败，尝试SMTP备用方案'
                logger.warning(f"SES发送失败，尝试SMTP备用方案: {to_email}")
        
        # 备用SMTP发送
        smtp_success = self.send_email_smtp(clean_email, subject, body_text, body_html, reply_to)
        if smtp_success:
            result.update({
                'success': True,
                'method': 'SMTP',
                'message_id': None  # SMTP没有message_id
            })
        else:
            result['error'] = 'SES和SMTP发送都失败'
            logger.error(f"邮件发送完全失败: {to_email}")
        
        return result
    
    def send_test_email(self, to_email: str, test_subject: str = "测试邮件") -> Dict[str, Any]:
        """发送测试邮件"""
        from datetime import datetime
        
        test_body = f"""这是一封测试邮件。

发送时间: {datetime.now().isoformat()}
目标邮箱: {to_email}
SES区域: {self.ses_config['region']}
SMTP服务器: {self.smtp_config['server']}:{self.smtp_config['port']}

如果您收到此邮件，说明邮件发送配置正常。

AI助手
{self.ses_config['from_email']}"""
        
        return self.send_email(to_email, test_subject, test_body)
    
    def get_sender_status(self) -> Dict[str, Any]:
        """获取发送器状态"""
        status = {
            'ses_available': self.ses_client is not None,
            'smtp_configured': bool(self.smtp_config['password'] and 
                                  self.smtp_config['password'] != 'your_password'),
            'ses_config': {
                'region': self.ses_config['region'],
                'from_email': self.ses_config['from_email']
            },
            'smtp_config': {
                'server': f"{self.smtp_config['server']}:{self.smtp_config['port']}",
                'username': self.smtp_config['username']
            }
        }
        
        return status
    
    def extract_email_address(self, email: str) -> str:
        """从邮箱字符串中提取纯净的邮箱地址"""
        import re
        
        if not email:
            return email
        
        # 提取邮箱地址（处理 "Name <email@domain.com>" 格式）
        email_match = re.search(r'<([^>]+)>', email)
        if email_match:
            return email_match.group(1).strip()
        else:
            return email.strip()
    
    def validate_email_address(self, email: str) -> bool:
        """邮箱地址验证，支持显示名称格式"""
        import re
        
        if not email:
            return False
        
        # 提取纯净的邮箱地址
        actual_email = self.extract_email_address(email)
        
        # 验证邮箱格式
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, actual_email))
    
    def send_reply_email(self, to_email: str, original_subject: str, reply_content: str, 
                        analysis_result: Optional[Dict] = None) -> Dict[str, Any]:
        """发送回复邮件
        
        Args:
            to_email: 收件人邮箱
            original_subject: 原邮件主题
            reply_content: 回复内容
            analysis_result: AI分析结果（可选）
            
        Returns:
            发送结果
        """
        if not self.validate_email_address(to_email):
            return {
                'success': False,
                'method': None,
                'message_id': None,
                'error': '无效的邮箱地址'
            }
        
        # 构建回复主题
        if not original_subject.startswith('Re:'):
            reply_subject = f"Re: {original_subject}"
        else:
            reply_subject = original_subject
        
        # 发送邮件
        result = self.send_email(
            to_email=to_email,
            subject=reply_subject,
            body_text=reply_content,
            reply_to=self.ses_config['from_email']
        )
        
        # 记录发送日志
        if result['success']:
            logger.info(
                f"回复邮件发送成功: To={to_email}, Subject={reply_subject}, "
                f"Method={result['method']}, MessageId={result.get('message_id', 'N/A')}"
            )
        else:
            logger.error(
                f"回复邮件发送失败: To={to_email}, Subject={reply_subject}, "
                f"Error={result.get('error', 'Unknown')}"
            )
        
        return result

# 创建全局发送器实例
sender = EmailSender()