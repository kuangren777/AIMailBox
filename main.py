from fastapi import FastAPI, Request, Response, HTTPException
import logging
import uvicorn
from datetime import datetime

# 导入自定义模块
from config import config
from email_processor import processor, ProcessedEmail
from ai_analyzer import analyzer
from email_sender import sender
from data_storage import storage
from trans import translator
from utils import is_forwarded_email, extract_user_instruction

# 初始化FastAPI应用
app = FastAPI()
logger = logging.getLogger("mail_server")
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper()),
    format=config.LOG_FORMAT
)



@app.post("/inbound")
async def inbound(request: Request):
    """处理入站邮件的主要端点"""
    try:
        # 获取签名和载荷
        sig = request.headers.get("x-inbound-signature", "")
        payload = await request.json()
        raw_b64 = payload.get("raw_base64", "")
        
        # 记录收到邮件
        storage.log_activity(
            "email_received",
            {"signature_present": bool(sig), "payload_size": len(raw_b64)}
        )
        
        # 处理邮件
        processed_email = processor.process_email(raw_b64, sig)
        if not processed_email:
            storage.log_activity(
                "email_processing_failed",
                {"reason": "邮件处理失败"},
                "error"
            )
            raise HTTPException(status_code=400, detail="邮件处理失败")
        
        logger.info(
            f"收到邮件: 发件人={processed_email.from_email} "
            f"收件人={processed_email.to_email} 主题={processed_email.subject}"
        )
        
        # AI分析邮件内容
        analysis_result = None
        if config.AUTO_REPLY_ENABLED and processed_email.text_content:
            try:
                # 检测是否为转发邮件并提取用户指令
                is_forwarded = is_forwarded_email(processed_email.subject, processed_email.text_content)
                user_instruction = extract_user_instruction(processed_email.text_content, is_forwarded)
                
                analysis_result = analyzer.analyze_email_content(
                    processed_email.text_content,
                    processed_email.from_email,
                    user_instruction
                )
                
                storage.log_activity(
                    "email_analyzed",
                    {
                        "from": processed_email.from_email,
                        "intent": analysis_result.get('intent'),
                        "can_auto_reply": analysis_result.get('can_auto_reply')
                    }
                )
                
                logger.info(
                    f"AI分析完成: 意图={analysis_result.get('intent')}, "
                    f"可自动回复={analysis_result.get('can_auto_reply')}"
                )
                
            except Exception as e:
                logger.error(f"AI分析失败: {e}")
                storage.log_activity(
                    "analysis_failed",
                    {"error": str(e), "from": processed_email.from_email},
                    "error"
                )
        
        # 生成并发送回复
        send_result = None
        if processed_email.from_email and analysis_result:
            try:
                # 生成回复内容
                reply_subject, reply_body = analyzer.generate_reply(
                    analysis_result,
                    processed_email.subject,
                    processed_email.text_content,
                    is_forwarded
                )
                
                # 发送回复邮件
                send_result = sender.send_reply_email(
                    processed_email.from_email,
                    processed_email.subject,
                    reply_body,
                    analysis_result
                )
                
                storage.log_activity(
                    "reply_sent" if send_result['success'] else "reply_failed",
                    {
                        "to": processed_email.from_email,
                        "method": send_result.get('method'),
                        "message_id": send_result.get('message_id'),
                        "error": send_result.get('error')
                    },
                    "info" if send_result['success'] else "error"
                )
                
                if send_result['success']:
                    logger.info(
                        f"回复邮件发送成功: To={processed_email.from_email}, "
                        f"Method={send_result['method']}"
                    )
                else:
                    logger.error(
                        f"回复邮件发送失败: To={processed_email.from_email}, "
                        f"Error={send_result.get('error')}"
                    )
                    
            except Exception as e:
                logger.error(f"发送回复失败: {e}")
                send_result = {
                    'success': False,
                    'error': f'发送回复异常: {str(e)}'
                }
                storage.log_activity(
                    "reply_exception",
                    {"error": str(e), "to": processed_email.from_email},
                    "error"
                )
        
        # 保存邮件数据
        save_success = storage.save_email(
            processed_email,
            analysis_result,
            send_result
        )
        
        # 构建响应
        response_data = {
            "ok": True,
            "status": "已接收",
            "from": processed_email.from_email,
            "subject": processed_email.subject,
            "saved": save_success,
            "analyzed": analysis_result is not None,
            "replied": send_result and send_result.get('success', False)
        }
        
        # 添加分析结果摘要
        if analysis_result:
            response_data["analysis"] = {
                "intent": analysis_result.get('intent'),
                "urgency": analysis_result.get('urgency'),
                "can_auto_reply": analysis_result.get('can_auto_reply'),
                "language": analysis_result.get('detected_language')
            }
        
        # 添加发送结果
        if send_result:
            response_data["send_result"] = {
                "success": send_result.get('success'),
                "method": send_result.get('method'),
                "message_id": send_result.get('message_id')
            }
        
        # 生成状态消息
        if send_result and send_result.get('success'):
            response_data["message"] = f"邮件已保存并通过{send_result.get('method')}发送智能回复"
        elif analysis_result:
            response_data["message"] = "邮件已保存并分析，但回复发送失败"
        else:
            response_data["message"] = "邮件已保存，但未进行AI分析"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理入站邮件异常: {e}")
        storage.log_activity(
            "inbound_exception",
            {"error": str(e)},
            "error"
        )
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

@app.post("/inbound/trans")
async def translate_inbound_default(request: Request):
    """处理入站邮件翻译的端点（默认翻译成中文）"""
    return await translate_inbound_with_language("zh", request)

@app.post("/inbound/trans/{target_language}")
async def translate_inbound_with_language(target_language: str, request: Request):
    """处理入站邮件翻译的端点"""
    try:
        # 获取签名和载荷
        sig = request.headers.get("x-inbound-signature", "")
        payload = await request.json()
        raw_b64 = payload.get("raw_base64", "")
        
        # 记录收到翻译请求
        storage.log_activity(
            "translation_request_received",
            {
                "target_language": target_language,
                "signature_present": bool(sig), 
                "payload_size": len(raw_b64)
            }
        )
        
        # 处理邮件
        processed_email = processor.process_email(raw_b64, sig)
        if not processed_email:
            storage.log_activity(
                "translation_email_processing_failed",
                {"reason": "邮件处理失败", "target_language": target_language},
                "error"
            )
            raise HTTPException(status_code=400, detail="邮件处理失败")
        
        logger.info(
            f"收到翻译请求: 发件人={processed_email.from_email} "
            f"目标语言={target_language} 主题={processed_email.subject}"
        )
        
        # 验证目标语言
        supported_languages = translator.get_supported_languages()
        if target_language not in supported_languages:
            storage.log_activity(
                "unsupported_language",
                {
                    "target_language": target_language,
                    "supported_languages": list(supported_languages.keys())
                },
                "error"
            )
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的目标语言: {target_language}。支持的语言: {list(supported_languages.keys())}"
            )
        
        # 执行翻译
        translation_result = translator.translate_email(processed_email, target_language)
        
        if translation_result['success']:
            # 发送翻译结果给原发件人
            try:
                reply_subject = f"翻译结果: {translation_result.get('translated_subject', processed_email.subject)}"
                reply_content = f"""您好，

以下是您邮件的翻译结果：

原始主题：{processed_email.subject}
翻译后主题：{translation_result.get('translated_subject', processed_email.subject)}

原始内容：
{processed_email.text_content}

翻译后内容：
{translation_result.get('translated_content', processed_email.text_content)}

翻译语言：{translation_result.get('original_language', 'unknown')} -> {target_language}

此邮件由智能翻译系统自动发送。
"""
                
                send_result = sender.send_email(
                            to_email=processed_email.from_email,
                            subject=reply_subject,
                            body_text=reply_content,
                            reply_to=config.TRANS_FROM_EMAIL
                        )
                
                if send_result["success"]:
                    logger.info(f"翻译结果已发送给 {processed_email.from_email}")
                    storage.log_activity(
                        "translation_sent",
                        {
                            "to": processed_email.from_email,
                            "target_language": target_language,
                            "original_language": translation_result.get('original_language'),
                            "message_id": processed_email.message_id
                        }
                    )
                else:
                    logger.error(f"翻译结果发送失败: {send_result.get('error')}")
                    storage.log_activity(
                        "translation_send_failed",
                        {
                            "to": processed_email.from_email,
                            "error": send_result.get('error'),
                            "target_language": target_language
                        },
                        "error"
                    )
            except Exception as e:
                logger.error(f"发送翻译结果时出错: {e}")
                storage.log_activity(
                    "translation_send_exception",
                    {
                        "to": processed_email.from_email,
                        "error": str(e),
                        "target_language": target_language
                    },
                    "error"
                )
            
            storage.log_activity(
                "translation_completed",
                {
                    "from": processed_email.from_email,
                    "target_language": target_language,
                    "original_language": translation_result.get('original_language'),
                    "message_id": processed_email.message_id
                }
            )
            
            logger.info(
                f"翻译完成: {translation_result.get('original_language')} -> {target_language} "
                f"发件人={processed_email.from_email}"
            )
        else:
            storage.log_activity(
                "translation_failed",
                {
                    "error": translation_result.get('error'),
                    "from": processed_email.from_email,
                    "target_language": target_language
                },
                "error"
            )
        
        return {
            "status": "success" if translation_result['success'] else "error",
            "translation_result": translation_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"翻译处理异常: {e}")
        storage.log_activity(
            "translation_exception",
            {"error": str(e), "target_language": target_language},
            "error"
        )
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/")
async def root():
    """主页"""
    config_info = config.get_config_info()
    sender_status = sender.get_sender_status()
    stats = storage.get_statistics()
    
    return {
        "service": "智能邮件服务器",
        "version": "2.0.0",
        "status": "运行中",
        "description": "接收邮件，AI分析并智能回复",
        "features": [
            "邮件接收和解析",
            "AI内容分析",
            "智能自动回复",
            "多语言支持",
            "SES/SMTP双重发送"
        ],
        "config": config_info,
        "sender_status": sender_status,
        "statistics": stats
    }

@app.get("/emails")
async def get_emails(limit: int = 10, offset: int = 0):
    """查看最近接收的邮件"""
    try:
        result = storage.get_emails(limit, offset)
        return result
    except Exception as e:
        logger.error(f"获取邮件列表失败: {e}")
        return Response(
            status_code=500,
            content=f"获取邮件列表错误: {str(e)}"
        )

@app.get("/emails/search")
async def search_emails(q: str, limit: int = 10):
    """搜索邮件"""
    try:
        emails = storage.search_emails(q, limit)
        return {
            "query": q,
            "results": emails,
            "count": len(emails)
        }
    except Exception as e:
        logger.error(f"搜索邮件失败: {e}")
        return Response(
            status_code=500,
            content=f"搜索邮件错误: {str(e)}"
        )

@app.get("/emails/{message_id}")
async def get_email_detail(message_id: str):
    """获取邮件详情"""
    try:
        email = storage.get_email_by_message_id(message_id)
        if email:
            return email
        else:
            raise HTTPException(status_code=404, detail="邮件未找到")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取邮件详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取邮件详情错误: {str(e)}")

@app.post("/test-ses")
async def test_ses(to_email: str, test_subject: str = "SES测试邮件"):
    """测试SES发送功能"""
    try:
        result = sender.send_test_email(to_email, test_subject)
        
        storage.log_activity(
            "test_email_sent" if result['success'] else "test_email_failed",
            {
                "to": to_email,
                "method": result.get('method'),
                "error": result.get('error')
            }
        )
        
        return {
            "success": result['success'],
            "method": result.get('method'),
            "message_id": result.get('message_id'),
            "to": to_email,
            "message": "测试邮件发送成功" if result['success'] else f"测试邮件发送失败: {result.get('error')}"
        }
        
    except Exception as e:
        logger.error(f"测试邮件发送异常: {e}")
        return {
            "success": False,
            "to": to_email,
            "message": f"测试邮件发送异常: {str(e)}"
        }

@app.get("/logs")
async def get_logs(limit: int = 50, activity_type: str = None):
    """获取系统日志"""
    try:
        logs = storage.get_logs(limit, activity_type)
        return {
            "logs": logs,
            "count": len(logs),
            "activity_type": activity_type
        }
    except Exception as e:
        logger.error(f"获取日志失败: {e}")
        return Response(
            status_code=500,
            content=f"获取日志错误: {str(e)}"
        )

@app.get("/statistics")
async def get_statistics():
    """获取统计信息"""
    try:
        stats = storage.get_statistics()
        return stats
    except Exception as e:
        logger.error(f"获取统计信息失败: {e}")
        return Response(
            status_code=500,
            content=f"获取统计信息错误: {str(e)}"
        )

@app.post("/analyze")
async def analyze_text(text: str, sender: str = "", user_instruction: str = ""):
    """手动分析文本内容"""
    try:
        analysis = analyzer.analyze_email_content(text, sender, user_instruction)
        return {
            "text": text[:200] + "..." if len(text) > 200 else text,
            "user_instruction": user_instruction if user_instruction else "无",
            "analysis": analysis
        }
    except Exception as e:
        logger.error(f"文本分析失败: {e}")
        return Response(
            status_code=500,
            content=f"文本分析错误: {str(e)}"
        )

@app.post("/cleanup")
async def cleanup_data(days: int = 30):
    """清理旧数据"""
    try:
        result = storage.cleanup_old_data(days)
        storage.log_activity(
            "data_cleanup",
            result
        )
        return result
    except Exception as e:
        logger.error(f"数据清理失败: {e}")
        return Response(
            status_code=500,
            content=f"数据清理错误: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """健康检查"""
    try:
        # 检查配置
        config_errors = config.validate_config()
        
        # 检查发送器状态
        sender_status = sender.get_sender_status()
        
        # 检查存储
        stats = storage.get_statistics()
        
        health_status = {
            "status": "healthy" if not config_errors else "warning",
            "timestamp": datetime.now().isoformat(),
            "config_errors": config_errors,
            "sender_available": sender_status['ses_available'] or sender_status['smtp_configured'],
            "total_emails": stats.get('total_emails', 0),
            "success_rate": stats.get('success_rate', 0)
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

if __name__ == "__main__":
    print(f"启动智能邮件服务器，端口: {config.SERVER_PORT}")
    print(f"SMTP配置: {config.SMTP_SERVER}:{config.SMTP_PORT} ({config.SMTP_USERNAME})")
    print(f"SES配置: 区域={config.AWS_REGION}, 发件人={config.SES_FROM_EMAIL}")
    print(f"AI分析: 模型={config.AI_MODEL}, API={config.AI_API_URL}")
    print("\n功能特性:")
    print("- 智能邮件接收和解析")
    print("- AI内容分析和意图识别")
    print("- 多语言智能回复")
    print("- SES/SMTP双重发送保障")
    print("- 完整的日志和统计")
    print("\n环境变量说明:")
    print("- AI_API_KEY: AI分析API密钥")
    print("- AWS_SECRET_ACCESS_KEY: AWS密钥")
    print("- INBOUND_SECRET: 入站验证密钥")
    print("- SMTP_PASSWORD: SMTP密码（备用）")
    print("\n测试端点:")
    print(f"- POST /test-ses?to_email=your@email.com - 测试邮件发送")
    print(f"- GET /emails - 查看收到的邮件")
    print(f"- GET /logs - 查看系统日志")
    print(f"- GET /statistics - 查看统计信息")
    print(f"- GET /health - 健康检查")
    
    # 检查配置
    config_errors = config.validate_config()
    if config_errors:
        print("\n⚠️ 配置警告:")
        for error in config_errors:
            print(f"  - {error}")
    
    uvicorn.run(
        app,
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        log_level=config.LOG_LEVEL
    )