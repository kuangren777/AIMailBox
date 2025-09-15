import base64
import hmac
import hashlib
import logging
from typing import Optional, List, Tuple, Dict
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from pydantic import BaseModel
from config import config

logger = logging.getLogger("email_processor")

class InboundPayload(BaseModel):
    """入站邮件载荷模型"""
    from_: Optional[str] = None
    to: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    message_id: Optional[str] = None
    raw_base64: str
    received_at: Optional[str] = None

class ProcessedEmail(BaseModel):
    """处理后的邮件模型"""
    from_email: str
    to_email: str
    subject: str
    date: str
    message_id: str
    text_content: Optional[str]
    html_content: Optional[str]
    attachments: List[Dict] = []
    raw_size: int = 0

class EmailProcessor:
    """邮件处理器"""
    
    def __init__(self):
        self.inbound_secret = config.INBOUND_SECRET
        self.max_content_length = config.MAX_EMAIL_CONTENT_LENGTH
    
    def verify_signature(self, raw_b64: str, sig_hex: str) -> bool:
        """验证HMAC签名"""
        try:
            mac = hmac.new(
                self.inbound_secret.encode(), 
                raw_b64.encode(), 
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(mac, sig_hex)
        except Exception as e:
            logger.error(f"签名验证失败: {e}")
            return False
    
    def parse_raw_email(self, raw_b64: str) -> Optional[EmailMessage]:
        """解析原始邮件"""
        try:
            raw_bytes = base64.b64decode(raw_b64)
            msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw_bytes)
            return msg
        except Exception as e:
            logger.error(f"邮件解析失败: {e}")
            return None
    
    def extract_text_parts(self, msg: EmailMessage) -> Tuple[Optional[str], Optional[str]]:
        """提取邮件文本部分
        
        Returns:
            Tuple[Optional[str], Optional[str]]: (text_plain, text_html)
        """
        if msg.is_multipart():
            plain_parts: List[str] = []
            html_parts: List[str] = []
            
            for part in msg.walk():
                ctype = part.get_content_type()
                disp = part.get_content_disposition()
                
                # 跳过附件
                if disp == "attachment":
                    continue
                
                if ctype == "text/plain":
                    try:
                        content = part.get_content()
                        if content:
                            plain_parts.append(content)
                    except Exception:
                        try:
                            payload = part.get_payload(decode=True) or b""
                            charset = part.get_content_charset() or "utf-8"
                            content = payload.decode(charset, errors="replace")
                            if content:
                                plain_parts.append(content)
                        except Exception as e:
                            logger.warning(f"提取纯文本部分失败: {e}")
                
                elif ctype == "text/html":
                    try:
                        content = part.get_content()
                        if content:
                            html_parts.append(content)
                    except Exception:
                        try:
                            payload = part.get_payload(decode=True) or b""
                            charset = part.get_content_charset() or "utf-8"
                            content = payload.decode(charset, errors="replace")
                            if content:
                                html_parts.append(content)
                        except Exception as e:
                            logger.warning(f"提取HTML部分失败: {e}")
            
            plain = "\n\n".join([p for p in plain_parts if p.strip()])
            html = "\n\n".join([h for h in html_parts if h.strip()])
            
            return (plain or None, html or None)
        
        else:
            # 单部分邮件
            ctype = msg.get_content_type()
            try:
                content = msg.get_content()
            except Exception:
                try:
                    payload = msg.get_payload(decode=True) or b""
                    charset = msg.get_content_charset() or "utf-8"
                    content = payload.decode(charset, errors="replace")
                except Exception as e:
                    logger.error(f"提取单部分邮件内容失败: {e}")
                    return (None, None)
            
            if ctype == "text/plain":
                return (content, None)
            elif ctype == "text/html":
                return (None, content)
            else:
                return (None, None)
    
    def extract_attachments(self, msg: EmailMessage) -> List[Dict]:
        """提取附件信息"""
        attachments = []
        
        if not msg.is_multipart():
            return attachments
        
        try:
            for part in msg.walk():
                disp = part.get_content_disposition()
                if disp == "attachment":
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            "filename": filename,
                            "content_type": part.get_content_type(),
                            "size": len(part.get_payload(decode=True) or b"")
                        })
        except Exception as e:
            logger.warning(f"提取附件信息失败: {e}")
        
        return attachments
    
    def process_email(self, raw_b64: str, signature: str) -> Optional[ProcessedEmail]:
        """处理邮件的完整流程"""
        try:
            # 验证签名
            if not self.verify_signature(raw_b64, signature):
                logger.warning("邮件签名验证失败")
                return None
            
            # 解析邮件
            msg = self.parse_raw_email(raw_b64)
            if not msg:
                logger.error("邮件解析失败")
                return None
            
            # 提取基本信息
            mail_from = msg.get("From", "")
            rcpt_to = msg.get("To", "")
            subject = msg.get("Subject", "无主题")
            message_id = msg.get("Message-ID", "")
            date = msg.get("Date", "")
            
            # 提取文本内容
            text_plain, text_html = self.extract_text_parts(msg)
            
            # 限制内容长度
            if text_plain and len(text_plain) > self.max_content_length:
                text_plain = text_plain[:self.max_content_length] + "...[内容已截断]"
            
            if text_html and len(text_html) > self.max_content_length:
                text_html = text_html[:self.max_content_length] + "...[内容已截断]"
            
            # 提取附件信息
            attachments = self.extract_attachments(msg)
            
            # 创建处理结果
            processed_email = ProcessedEmail(
                from_email=mail_from,
                to_email=rcpt_to,
                subject=subject,
                date=date,
                message_id=message_id,
                text_content=text_plain,
                html_content=text_html,
                attachments=attachments,
                raw_size=len(base64.b64decode(raw_b64))
            )
            
            logger.info(
                f"邮件处理成功: 发件人={mail_from}, 收件人={rcpt_to}, "
                f"主题={subject}, 附件数={len(attachments)}"
            )
            
            return processed_email
            
        except Exception as e:
            logger.error(f"邮件处理异常: {e}")
            return None
    
    def get_email_summary(self, processed_email: ProcessedEmail) -> Dict:
        """获取邮件摘要信息"""
        content = processed_email.text_content or processed_email.html_content or ""
        
        return {
            "from": processed_email.from_email,
            "to": processed_email.to_email,
            "subject": processed_email.subject,
            "date": processed_email.date,
            "message_id": processed_email.message_id,
            "content_length": len(content),
            "has_attachments": len(processed_email.attachments) > 0,
            "attachment_count": len(processed_email.attachments),
            "raw_size": processed_email.raw_size,
            "content_preview": content[:200] if content else ""
        }
    
    def validate_email_data(self, processed_email: ProcessedEmail) -> List[str]:
        """验证邮件数据完整性"""
        errors = []
        
        if not processed_email.from_email:
            errors.append("缺少发件人信息")
        
        if not processed_email.to_email:
            errors.append("缺少收件人信息")
        
        if not processed_email.text_content and not processed_email.html_content:
            errors.append("邮件内容为空")
        
        if processed_email.raw_size > 10 * 1024 * 1024:  # 10MB
            errors.append("邮件大小超过限制")
        
        return errors

# 创建全局处理器实例
processor = EmailProcessor()