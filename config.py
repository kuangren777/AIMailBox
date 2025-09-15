import os
import configparser
from typing import Optional

class Config:
    """邮件服务器配置类"""
    
    def __init__(self):
        self.config = configparser.ConfigParser()
        self._load_config()
        
    def _load_config(self):
        """加载配置文件"""
        config_file = 'config.ini'
        if os.path.exists(config_file):
            self.config.read(config_file, encoding='utf-8')
        else:
            # 如果配置文件不存在，使用默认值
            print(f"警告: 配置文件 {config_file} 不存在，使用默认配置")
    
    def _get_str(self, section: str, key: str, default: str = '', env_key: str = None) -> str:
        """获取字符串配置，优先使用环境变量"""
        if env_key and os.getenv(env_key):
            return os.getenv(env_key)
        try:
            return self.config.get(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default
    
    def _get_int(self, section: str, key: str, default: int = 0, env_key: str = None) -> int:
        """获取整数配置，优先使用环境变量"""
        if env_key and os.getenv(env_key):
            return int(os.getenv(env_key))
        try:
            return self.config.getint(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def _get_float(self, section: str, key: str, default: float = 0.0, env_key: str = None) -> float:
        """获取浮点数配置，优先使用环境变量"""
        if env_key and os.getenv(env_key):
            return float(os.getenv(env_key))
        try:
            return self.config.getfloat(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    def _get_bool(self, section: str, key: str, default: bool = False, env_key: str = None) -> bool:
        """获取布尔配置，优先使用环境变量"""
        if env_key and os.getenv(env_key):
            return os.getenv(env_key).lower() in ('true', '1', 'yes', 'on')
        try:
            return self.config.getboolean(section, key)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return default
    
    # SMTP 配置
    @property
    def SMTP_SERVER(self) -> str:
        return self._get_str('SMTP', 'server', '31.57.172.116')
    
    @property
    def SMTP_PORT(self) -> int:
        return self._get_int('SMTP', 'port', 587)
    
    @property
    def SMTP_USERNAME(self) -> str:
        return self._get_str('SMTP', 'username', 'ai@kr777.top')
    
    @property
    def SMTP_PASSWORD(self) -> str:
        return self._get_str('SMTP', 'password', 'your_password', 'SMTP_PASSWORD')
    
    # 服务器配置
    @property
    def SERVER_PORT(self) -> int:
        return self._get_int('SERVER', 'port', 7582)
    
    @property
    def SERVER_HOST(self) -> str:
        return self._get_str('SERVER', 'host', '0.0.0.0')
    
    @property
    def LOG_LEVEL(self) -> str:
        return self._get_str('SERVER', 'log_level', 'info')
    
    # 安全配置
    @property
    def INBOUND_SECRET(self) -> str:
        return self._get_str('SECURITY', 'inbound_secret', 'jsdiaojdisajdiofhu9u83huiwu9w8ug8', 'INBOUND_SECRET')
    
    # AWS SES 配置
    @property
    def AWS_REGION(self) -> str:
        return self._get_str('AWS', 'region', 'ap-southeast-2')
    
    @property
    def AWS_ACCESS_KEY_ID(self) -> str:
        return self._get_str('AWS', 'access_key_id', 'your_aws_key_id', 'AWS_ACCESS_KEY_ID')
    
    @property
    def AWS_SECRET_ACCESS_KEY(self) -> str:
        return self._get_str('AWS', 'secret_access_key', 'your_aws_secret_key', 'AWS_SECRET_ACCESS_KEY')
    
    @property
    def SES_FROM_EMAIL(self) -> str:
        return self._get_str('AWS', 'ses_from_email', 'ai@kr777.top')
    
    @property
    def TRANS_FROM_EMAIL(self) -> str:
        return self._get_str('AWS', 'trans_from_email', 'trans@kr777.top')
    
    # 文件存储配置
    @property
    def EMAILS_FILE(self) -> str:
        return self._get_str('FILES', 'emails_file', 'emails.json')
    
    @property
    def EMAIL_LOGS_FILE(self) -> str:
        return self._get_str('FILES', 'email_logs_file', 'email_logs.json')
    
    # AI 分析配置
    @property
    def AI_API_URL(self) -> str:
        return self._get_str('AI', 'api_url', 'https://kr777.top/v1/chat/completions', 'AI_API_URL')
    
    @property
    def AI_API_KEY(self) -> str:
        return self._get_str('AI', 'api_key', 'kuangren777', 'AI_API_KEY')
    
    @property
    def AI_MODEL(self) -> str:
        return self._get_str('AI', 'model', 'grok-3', 'AI_MODEL')
    
    @property
    def AI_MAX_TOKENS(self) -> int:
        return self._get_int('AI', 'max_tokens', 10000, 'AI_MAX_TOKENS')
    
    @property
    def AI_TEMPERATURE(self) -> float:
        return self._get_float('AI', 'temperature', 0.7, 'AI_TEMPERATURE')
    
    # 邮件处理配置
    @property
    def MAX_EMAIL_CONTENT_LENGTH(self) -> int:
        return self._get_int('EMAIL_PROCESSING', 'max_content_length', 100000)
    
    @property
    def DEFAULT_REPLY_LANGUAGE(self) -> str:
        return self._get_str('EMAIL_PROCESSING', 'default_reply_language', 'zh')
    
    @property
    def AUTO_REPLY_ENABLED(self) -> bool:
        return self._get_bool('EMAIL_PROCESSING', 'auto_reply_enabled', True)
    
    # 日志配置
    @property
    def LOG_FORMAT(self) -> str:
        return self._get_str('LOGGING', 'format', '%(asctime)s %(levelname)s %(message)s')
    
    def get_config_info(self) -> dict:
        """获取配置信息摘要"""
        return {
            "smtp_server": f"{self.SMTP_SERVER}:{self.SMTP_PORT}",
            "smtp_username": self.SMTP_USERNAME,
            "server_port": self.SERVER_PORT,
            "aws_region": self.AWS_REGION,
            "ses_from_email": self.SES_FROM_EMAIL,
            "ai_model": self.AI_MODEL,
            "auto_reply_enabled": self.AUTO_REPLY_ENABLED
        }
    
    def validate_config(self) -> list:
        """验证配置，返回错误列表"""
        errors = []
        
        if not self.SMTP_PASSWORD or self.SMTP_PASSWORD == 'your_password':
            errors.append("SMTP_PASSWORD 未设置或使用默认值")
            
        if not self.AI_API_KEY:
            errors.append("AI_API_KEY 未设置")
            
        if not self.AWS_SECRET_ACCESS_KEY or 'your_key' in self.AWS_SECRET_ACCESS_KEY.lower():
            errors.append("AWS_SECRET_ACCESS_KEY 未正确设置")
            
        return errors

# 创建全局配置实例
config = Config()