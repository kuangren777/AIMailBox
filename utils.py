"""工具函数模块

包含邮件处理相关的工具函数
"""


def is_forwarded_email(subject: str, content: str) -> bool:
    """检测是否为转发邮件"""
    if not subject and not content:
        return False
    
    # 检查主题中的转发标识
    subject_lower = subject.lower() if subject else ""
    forwarded_indicators = ['fwd:', 'fw:', '转发:', '转：', 'forward:', 'forwarded:']
    
    for indicator in forwarded_indicators:
        if indicator in subject_lower:
            return True
    
    # 检查内容中的转发标识
    if content:
        content_lower = content.lower()
        content_indicators = [
            'forwarded message', '转发的邮件', '转发邮件', 
            'original message', '原始邮件', '---------- forwarded message',
            'from:', 'sent:', 'to:', 'subject:' # 常见的邮件头信息
        ]
        
        # 如果内容中包含多个邮件头信息，很可能是转发邮件
        header_count = sum(1 for indicator in content_indicators[-4:] if indicator in content_lower)
        if header_count >= 2:
            return True
            
        # 检查其他转发标识
        for indicator in content_indicators[:-4]:
            if indicator in content_lower:
                return True
    
    return False


def extract_user_instruction(content: str, is_forwarded: bool) -> str:
    """从邮件内容中提取用户指令
    
    Args:
        content: 邮件内容
        is_forwarded: 是否为转发邮件
        
    Returns:
        提取的用户指令文本，如果没有则返回空字符串
    """
    if not content or not is_forwarded:
        return ""
    
    lines = content.split('\n')
    user_instruction_lines = []
    
    # 转发邮件的分隔符
    forwarded_separators = [
        '---------- forwarded message ----------',
        '-------- original message --------',
        '-----original message-----',
        'begin forwarded message:',
        '转发邮件',
        '原始邮件',
        '---------- 转发的邮件 ----------',
        '-------- 原邮件 --------',
        'from:',
        'sent:',
        'to:',
        'subject:',
        '发件人:',
        '发送时间:',
        '收件人:',
        '主题:'
    ]
    
    # 提取转发邮件分隔符之前的内容作为用户指令
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # 检查是否遇到转发邮件分隔符
        is_separator = False
        for separator in forwarded_separators:
            if separator in line_lower:
                is_separator = True
                break
        
        if is_separator:
            break
        
        # 跳过空行
        if line.strip():
            user_instruction_lines.append(line.strip())
    
    # 合并用户指令
    user_instruction = '\n'.join(user_instruction_lines).strip()
    
    # 如果用户指令太短（少于3个字符），可能不是有效指令
    if len(user_instruction) < 3:
        return ""
    
    return user_instruction