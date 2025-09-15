from fastapi import FastAPI, Request, Response, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Tuple
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.mime.text import MIMEText
import base64
import hmac
import hashlib
import logging
import smtplib
import os
import json
from datetime import datetime
import uvicorn
import boto3
from botocore.exceptions import ClientError
from config import config

app = FastAPI()
logger = logging.getLogger("mail")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 配置从config模块读取
SMTP_SERVER = config.SMTP_SERVER
SMTP_PORT = config.SMTP_PORT
SMTP_USERNAME = config.SMTP_USERNAME
SMTP_PASSWORD = config.SMTP_PASSWORD
SERVER_PORT = config.SERVER_PORT
INBOUND_SECRET = config.INBOUND_SECRET

# AWS SES 配置
AWS_REGION = config.AWS_REGION
AWS_ACCESS_KEY_ID = config.AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY = config.AWS_SECRET_ACCESS_KEY
SES_FROM_EMAIL = config.SES_FROM_EMAIL

# SES 客户端初始化
try:
    ses_client = boto3.client(
        'ses',
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    logger.info(f"SES客户端初始化成功，区域: {AWS_REGION}")
except Exception as e:
    logger.error(f"SES客户端初始化失败: {e}")
    ses_client = None


class InboundPayload(BaseModel):
    from_: Optional[str] = None
    to: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[str] = None
    message_id: Optional[str] = None
    raw_base64: str
    received_at: Optional[str] = None


def verify_signature(raw_b64: str, sig_hex: str) -> bool:
    """验证HMAC签名"""
    mac = hmac.new(INBOUND_SECRET.encode(), raw_b64.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, sig_hex)


def send_ses_email(to_email: str, subject: str, body_text: str, body_html: Optional[str] = None) -> Optional[str]:
    """
    使用AWS SES发送邮件
    返回MessageId或None（失败时）
    """
    if not ses_client:
        logger.error("SES客户端未初始化")
        return None
    
    try:
        # 构建邮件体
        body = {'Text': {'Data': body_text, 'Charset': 'UTF-8'}}
        if body_html:
            body['Html'] = {'Data': body_html, 'Charset': 'UTF-8'}
        
        response = ses_client.send_email(
            Source=SES_FROM_EMAIL,
            Destination={'ToAddresses': [to_email]},
            Message={
                'Subject': {'Data': subject, 'Charset': 'UTF-8'},
                'Body': body
            }
        )
        
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


def extract_text_parts(msg: EmailMessage) -> Tuple[Optional[str], Optional[str]]:
    """
    返回 (text_plain, text_html)
    优先提取 text/plain；若无则返回 text/html 供降级渲染或后续转文本。
    """
    if msg.is_multipart():
        plain_parts: List[str] = []
        html_parts: List[str] = []
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = part.get_content_disposition()
            if disp == "attachment":
                continue
            if ctype == "text/plain":
                try:
                    plain_parts.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    plain_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
            elif ctype == "text/html":
                try:
                    html_parts.append(part.get_content())
                except Exception:
                    payload = part.get_payload(decode=True) or b""
                    html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
        plain = "\n\n".join([p for p in plain_parts if p])
        html = "\n\n".join([h for h in html_parts if h])
        return (plain or None, html or None)
    else:
        ctype = msg.get_content_type()
        try:
            content = msg.get_content()
        except Exception:
            payload = msg.get_payload(decode=True) or b""
            content = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        if ctype == "text/plain":
            return (content, None)
        if ctype == "text/html":
            return (None, content)
        return (None, None)


def save_email(email_data):
    """保存邮件到文件"""
    try:
        emails_file = "emails.json"
        email_entry = {
            "timestamp": datetime.now().isoformat(),
            "data": email_data
        }
        
        # 读取现有邮件
        if os.path.exists(emails_file):
            with open(emails_file, 'r', encoding='utf-8') as f:
                emails = json.load(f)
        else:
            emails = []
        
        emails.append(email_entry)
        
        # 保存邮件
        with open(emails_file, 'w', encoding='utf-8') as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        
        logger.info("邮件已保存")
        return True
    except Exception as e:
        logger.error(f"保存邮件失败: {e}")
        return False


def send_reply(to: str, subject: str, analysis: Optional[dict] = None) -> bool:
    """发送回复邮件（使用SES）"""
    try:
        # 根据分析结果决定回复内容
        if analysis and analysis.get('missing_info'):
            reply_subject = f"Re: {subject} - 需要更多信息"
            reply_body = f"""您好！

感谢您的邮件。为了更好地为您服务，请提供以下信息：

{chr(10).join(['• ' + info for info in analysis['missing_info']])}

请回复此邮件并提供上述信息，我们会尽快为您处理。

此致
敬礼！

AI助手
{config.SES_FROM_EMAIL}"""
        else:
            reply_subject = f"Re: {subject}"
            reply_body = """您好！

我们已收到您的邮件，感谢您的来信。

我们会尽快处理您的邮件并回复。

此致
敬礼！

AI助手
{config.SES_FROM_EMAIL}"""
        
        # 使用SES发送邮件
        message_id = send_ses_email(to, reply_subject, reply_body)
        
        if message_id:
            logger.info(f"SES回复邮件已发送到: {to}, MessageId: {message_id}")
            return True
        else:
            logger.error(f"SES回复邮件发送失败: {to}")
            return False
            
    except Exception as e:
        logger.error(f"发送回复失败 {to}: {e}")
        return False


def send_reply_smtp(to: str, subject: str) -> bool:
    """发送回复邮件（SMTP备用方案）"""
    try:
        reply_body = """您好！

我们已收到您的邮件，感谢您的来信。

我们会尽快处理您的邮件并回复。

此致
敬礼！

AI助手
ai@kr777.top"""
        
        msg = MIMEText(reply_body, 'plain', 'utf-8')
        msg['Subject'] = f"Re: {subject}"
        msg['From'] = SMTP_USERNAME
        msg['To'] = to
        
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"SMTP回复邮件已发送到: {to}")
        return True
    except Exception as e:
        logger.error(f"SMTP发送回复失败 {to}: {e}")
        return False


@app.post("/inbound")
async def inbound(request: Request):
    # 验证签名
    sig = request.headers.get("x-inbound-signature", "")
    payload = await request.json()
    raw_b64 = payload.get("raw_base64", "")
    
    if not raw_b64 or not sig or not verify_signature(raw_b64, sig):
        logger.warning("收到无效签名的请求")
        raise HTTPException(status_code=401, detail="invalid signature")

    # 解码并解析邮件
    try:
        raw_bytes = base64.b64decode(raw_b64)
        msg: EmailMessage = BytesParser(policy=policy.default).parsebytes(raw_bytes)
    except Exception as e:
        logger.error(f"邮件解析失败: {e}")
        raise HTTPException(status_code=400, detail=f"邮件解析错误: {e}")

    # 提取邮件信息
    mail_from = msg.get("From", "")
    rcpt_to = msg.get("To", "")
    subject = msg.get("Subject", "无主题")
    message_id = msg.get("Message-ID", "")
    date = msg.get("Date", "")

    # 提取纯文本正文
    text_plain, text_html = extract_text_parts(msg)

    logger.info(f"收到邮件: 发件人={mail_from} 收件人={rcpt_to} 主题={subject}")

    # 准备邮件数据
    email_data = {
        "from": mail_from,
        "to": rcpt_to,
        "subject": subject,
        "date": date,
        "message_id": message_id,
        "text_content": text_plain,
        "html_content": text_html
    }
    
    # 保存邮件
    save_success = save_email(email_data)
    
    # TODO: 调用AI分析邮件内容
    analysis = None
    # analysis = analyze_email(text_plain or "")  # 集成你的AI分析逻辑
    # 示例分析结果结构:
    # analysis = {
    #     'missing_info': ['联系电话', '具体需求'],  # 缺失信息列表
    #     'intent': 'inquiry',  # 邮件意图
    #     'urgency': 'normal'  # 紧急程度
    # }
    
    # 发送回复（使用SES）
    reply_success = False
    message_id = None
    if mail_from and save_success:
        reply_success = send_reply(mail_from, subject, analysis)
        
    # 记录发送结果
    if reply_success:
        logger.info(f"邮件处理完成: 来自={mail_from}, 主题={subject}, 已自动回复")
    else:
        logger.warning(f"邮件已保存但回复失败: 来自={mail_from}, 主题={subject}")

    return {
        "ok": True,
        "status": "已接收",
        "from": mail_from,
        "subject": subject,
        "saved": save_success,
        "replied": reply_success,
        "message": "邮件已保存并通过SES发送确认回复" if reply_success else "邮件已保存但回复发送失败"
    }


@app.get("/")
async def root():
    """主页"""
    return {
        "service": "简单邮件服务器",
        "version": "1.0.0",
        "status": "运行中",
        "description": "接收邮件，保存并自动回复"
    }


@app.get("/emails")
async def get_emails(limit: int = 10):
    """查看最近接收的邮件"""
    try:
        emails_file = "emails.json"
        if not os.path.exists(emails_file):
            return {"emails": [], "message": "暂无邮件"}
        
        with open(emails_file, 'r', encoding='utf-8') as f:
            emails = json.load(f)
        
        # 返回最近的邮件
        recent_emails = emails[-limit:] if len(emails) > limit else emails
        return {
            "emails": recent_emails,
            "total_count": len(emails),
            "showing": len(recent_emails)
        }
    except Exception as e:
        logger.error(f"读取邮件失败: {e}")
        return Response(status_code=500, content=f"读取邮件错误: {str(e)}")


@app.post("/test-ses")
async def test_ses(to_email: str, test_subject: str = "SES测试邮件"):
    """测试SES发送功能"""
    test_body = f"""这是一封SES测试邮件。

发送时间: {datetime.now().isoformat()}
目标邮箱: {to_email}
SES区域: {AWS_REGION}

如果您收到此邮件，说明SES配置正常。

AI助手
ai@kr777.top"""
    
    message_id = send_ses_email(to_email, test_subject, test_body)
    
    if message_id:
        return {
            "success": True,
            "message_id": message_id,
            "to": to_email,
            "message": "SES测试邮件发送成功"
        }
    else:
        return {
            "success": False,
            "to": to_email,
            "message": "SES测试邮件发送失败"
        }


if __name__ == "__main__":
    print(f"启动邮件服务器，端口: {SERVER_PORT}")
    print(f"SMTP配置: {SMTP_SERVER}:{SMTP_PORT} ({SMTP_USERNAME})")
    print(f"SES配置: 区域={AWS_REGION}, 发件人={SES_FROM_EMAIL}")
    print("使用 python mail.py 启动服务器")
    print("\n环境变量说明:")
    print("- AWS_SECRET_ACCESS_KEY: AWS密钥")
    print("- INBOUND_SECRET: 入站验证密钥")
    print("- SMTP_PASSWORD: SMTP密码（备用）")
    print("\n测试端点:")
    print(f"- POST /test-ses?to_email=your@email.com - 测试SES发送")
    print(f"- GET /emails - 查看收到的邮件")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=SERVER_PORT,
        log_level="info"
    )