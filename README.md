# 智能邮箱系统

一个基于AI的智能邮件处理系统，能够自动接收、分析邮件内容并生成智能回复和翻译服务。

## 🚀 快速体验

### 📧 AI分析回复功能
发送邮件到：**ai@kr777.top**
- 自动分析邮件内容和意图
- 智能生成回复内容
- 支持中英文双语处理
- 提取待办事项和关键信息

### 🌍 翻译服务功能
发送邮件到：**trans@kr777.top**
- 自动将邮件内容翻译成中文
- 保持原文格式和结构
- 快速响应翻译结果
- 目前仅支持翻译成中文

## 功能特性

- 📧 **智能邮件接收**: 自动接收和解析入站邮件
- 🤖 **AI内容分析**: 使用AI分析邮件内容和意图
- 🌍 **多语言支持**: 自动检测语言并用相应语言回复
- 🔄 **翻译服务**: 提供邮件内容翻译功能（目前支持翻译成中文）
- 📤 **智能回复**: 根据分析结果生成并发送回复邮件
- 🔄 **双重发送**: 支持AWS SES和SMTP两种发送方式
- 📊 **完整日志**: 详细的操作日志和统计信息
- 🔍 **邮件搜索**: 支持邮件内容搜索和查询

## 系统架构

```
智能邮箱系统/
├── main.py              # 主服务器文件，FastAPI应用
├── config.py            # 配置管理模块
├── config.ini           # 配置文件
├── config.ini.example   # 配置文件示例
├── email_processor.py   # 邮件处理模块
├── ai_analyzer.py       # AI分析模块
├── email_sender.py      # 邮件发送模块
├── data_storage.py      # 数据存储模块
├── trans.py             # 翻译服务模块
├── requirements.txt     # 依赖包列表
└── README.md           # 说明文档
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置文件设置

复制配置文件模板并修改：

```bash
cp config.ini.example config.ini
```

编辑 `config.ini` 文件，配置以下关键参数：

```ini
[SMTP]
server = your_smtp_server
port = 587
username = your_email@domain.com
password = your_password

[AWS]
region = ap-southeast-2
access_key_id = your_aws_access_key
secret_access_key = your_aws_secret_key
ses_from_email = ai@kr777.top
trans_from_email = trans@kr777.top

[AI]
api_key = your_ai_api_key
api_url = https://api.openai.com/v1/chat/completions
model = gpt-3.5-turbo
```

### 3. 启动服务

```bash
python main.py
```

服务将在配置的端口启动（默认7582）。

## 使用示例

### AI分析回复功能示例

**发送邮件到：ai@kr777.top**

#### 输入邮件（英文）
```
Subject: Meeting Request
Hi, can we schedule a meeting next week to discuss the project?
```

#### AI分析结果
```json
{
  "intent": "meeting_request",
  "urgency": "medium",
  "detected_language": "en",
  "can_auto_reply": true,
  "chinese_content": "请求安排下周会议讨论项目",
  "todo_items": ["安排项目讨论会议"]
}
```

#### 自动回复（英文）
```
Subject: Re: Meeting Request

Thank you for your meeting request. I'll check my schedule and get back to you with available time slots for next week.

Best regards,
AI Assistant
ai@kr777.top
```

### 翻译服务功能示例

**发送邮件到：trans@kr777.top**

#### 输入邮件（英文）
```
Subject: Product Inquiry
Hello, I'm interested in your latest product line. Could you please provide more information about pricing and availability?
```

#### 翻译回复（中文）
```
Subject: Re: Product Inquiry - 翻译结果

原文翻译如下：

您好，我对您的最新产品线很感兴趣。您能否提供更多关于价格和供货情况的信息？

---
此邮件由AI翻译服务自动生成
trans@kr777.top
```

## API端点

### 核心功能

- `POST /inbound` - 接收入站邮件（主要端点）
- `GET /` - 服务状态和配置信息
- `GET /health` - 健康检查

### 邮件管理

- `GET /emails` - 获取邮件列表
- `GET /emails/search?q=关键词` - 搜索邮件
- `GET /emails/{message_id}` - 获取邮件详情

### 测试和分析

- `POST /test-ses?to_email=test@example.com` - 测试邮件发送
- `POST /analyze` - 手动分析文本内容

### 系统管理

- `GET /logs` - 获取系统日志
- `GET /statistics` - 获取统计信息
- `POST /cleanup?days=30` - 清理旧数据

## 邮件处理流程

### AI分析回复流程（ai@kr777.top）
```
入站邮件 → 签名验证 → 内容解析 → AI分析 → 生成回复 → 发送邮件 → 保存记录
```

### 翻译服务流程（trans@kr777.top）
```
入站邮件 → 签名验证 → 内容解析 → AI翻译 → 生成译文 → 发送回复 → 保存记录
```

## 配置说明

### 邮件服务配置

系统支持两种邮件服务：
- **ai@kr777.top**: AI分析和智能回复
- **trans@kr777.top**: 翻译服务（目前仅支持翻译成中文）

### AI分析配置

```ini
[AI]
api_key = your_openai_api_key
api_url = https://api.openai.com/v1/chat/completions
model = gpt-3.5-turbo
max_tokens = 1000
temperature = 0.7
```

### 邮件发送配置

系统支持两种发送方式：
1. **AWS SES**（推荐）- 高可靠性，适合生产环境
2. **SMTP**（备用）- 通用性强，适合开发测试

## 监控和维护

### 查看系统状态

访问服务器根路径查看：
- 服务运行状态
- 配置信息
- 发送器状态
- 统计数据

### 日志管理

- 系统自动记录所有操作日志
- 支持按类型筛选日志
- 定期清理旧日志数据

### 数据清理

```bash
# 清理30天前的数据
curl -X POST "http://your-server:7582/cleanup?days=30"
```

## 故障排除

### 常见问题

1. **AI分析失败**
   - 检查AI_API_KEY是否正确
   - 确认API_URL可访问
   - 查看日志中的错误信息

2. **邮件发送失败**
   - 检查AWS SES配置
   - 验证SMTP设置
   - 确认发件人邮箱已验证

3. **翻译服务异常**
   - 检查AI API配置
   - 确认翻译模型可用
   - 查看翻译日志

4. **入站邮件处理失败**
   - 检查签名验证设置
   - 确认邮件格式正确
   - 查看处理日志

### 调试模式

在配置文件中设置：
```ini
[LOGGING]
level = DEBUG
```

## 安全注意事项

- 妥善保管API密钥和AWS凭证
- 使用HTTPS部署生产环境
- 定期更新依赖包
- 监控系统日志异常
- 配置文件不要提交到版本控制

## 扩展开发

系统采用模块化设计，可以轻松扩展：

- 添加新的AI模型支持
- 集成更多邮件服务商
- 扩展分析规则
- 自定义回复模板
- 支持更多翻译语言

## 许可证

本项目采用MIT许可证。

---

## 联系方式

- AI分析回复服务：ai@kr777.top
- 翻译服务：trans@kr777.top
- 作者邮箱：fudan@drluo.cn

立即发送邮件体验我们的智能邮件处理服务！