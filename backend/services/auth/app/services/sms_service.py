"""
短信服务抽象层
支持多个短信服务商（阿里云、腾讯云等）
"""
import os
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class SMSServiceInterface(ABC):
    """短信服务接口"""
    
    @abstractmethod
    def send_sms(self, phone: str, code: str) -> bool:
        """发送短信验证码
        
        Args:
            phone: 手机号
            code: 验证码
            
        Returns:
            是否发送成功
        """
        pass


class MockSMSService(SMSServiceInterface):
    """模拟短信服务（开发环境）"""
    
    def send_sms(self, phone: str, code: str) -> bool:
        """模拟发送短信（开发环境）"""
        logger.info(f"[模拟] 发送短信到 {phone}，验证码: {code}")
        # 开发环境不实际发送短信，只记录日志
        return True


class AliyunSMSService(SMSServiceInterface):
    """阿里云短信服务"""
    
    def __init__(self, access_key_id: str, access_key_secret: str, sign_name: str, template_code: str):
        """初始化阿里云短信服务
        
        Args:
            access_key_id: 访问密钥ID
            access_key_secret: 访问密钥Secret
            sign_name: 短信签名
            template_code: 模板代码
        """
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest
        except ImportError:
            logger.error("阿里云SDK未安装，请安装: pip install aliyun-python-sdk-core aliyun-python-sdk-dysmsapi")
            raise ImportError("请安装阿里云SDK")
        
        self.client = AcsClient(access_key_id, access_key_secret, 'cn-hangzhou')
        self.sign_name = sign_name
        self.template_code = template_code
        logger.info("使用阿里云短信服务")
    
    def send_sms(self, phone: str, code: str) -> bool:
        """发送短信"""
        try:
            from aliyunsdkcore.request import CommonRequest
            
            request = CommonRequest()
            request.set_accept_format('json')
            request.set_domain('dysmsapi.aliyuncs.com')
            request.set_method('POST')
            request.set_protocol_type('https')
            request.set_version('2017-05-25')
            request.set_action_name('SendSms')
            
            request.add_query_param('RegionId', "cn-hangzhou")
            request.add_query_param('PhoneNumbers', phone)
            request.add_query_param('SignName', self.sign_name)
            request.add_query_param('TemplateCode', self.template_code)
            request.add_query_param('TemplateParam', f'{{"code":"{code}"}}')
            
            response = self.client.do_action_with_exception(request)
            logger.info(f"阿里云短信发送成功: {phone}")
            return True
        
        except Exception as e:
            logger.error(f"阿里云短信发送失败: {e}", exc_info=True)
            return False


class TencentSMSService(SMSServiceInterface):
    """腾讯云短信服务"""
    
    def __init__(self, secret_id: str, secret_key: str, app_id: str, sign_name: str, template_id: str):
        """初始化腾讯云短信服务
        
        Args:
            secret_id: 密钥ID
            secret_key: 密钥Key
            app_id: 应用ID
            sign_name: 短信签名
            template_id: 模板ID
        """
        try:
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.sms.v20210111 import sms_client, models
        except ImportError:
            logger.error("腾讯云SDK未安装，请安装: pip install tencentcloud-sdk-python")
            raise ImportError("请安装腾讯云SDK")
        
        cred = credential.Credential(secret_id, secret_key)
        http_profile = HttpProfile()
        http_profile.endpoint = "sms.tencentcloudapi.com"
        
        client_profile = ClientProfile()
        client_profile.httpProfile = http_profile
        
        self.client = sms_client.SmsClient(cred, "ap-beijing", client_profile)
        self.app_id = app_id
        self.sign_name = sign_name
        self.template_id = template_id
        logger.info("使用腾讯云短信服务")
    
    def send_sms(self, phone: str, code: str) -> bool:
        """发送短信"""
        try:
            from tencentcloud.sms.v20210111 import models
            
            req = models.SendSmsRequest()
            req.SmsSdkAppId = self.app_id
            req.SignName = self.sign_name
            req.TemplateId = self.template_id
            req.PhoneNumberSet = [phone]
            req.TemplateParamSet = [code]
            
            resp = self.client.SendSms(req)
            if resp.SendStatusSet and resp.SendStatusSet[0].Code == "Ok":
                logger.info(f"腾讯云短信发送成功: {phone}")
                return True
            else:
                logger.error(f"腾讯云短信发送失败: {resp.SendStatusSet[0].Message if resp.SendStatusSet else 'Unknown error'}")
                return False
        
        except Exception as e:
            logger.error(f"腾讯云短信发送失败: {e}", exc_info=True)
            return False


def get_sms_service() -> SMSServiceInterface:
    """获取短信服务实例（工厂函数）"""
    sms_provider = os.getenv("SMS_PROVIDER", "mock").lower()
    
    if sms_provider == "aliyun":
        # 使用阿里云短信服务
        access_key_id = os.getenv("ALIYUN_ACCESS_KEY_ID")
        access_key_secret = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        sign_name = os.getenv("ALIYUN_SMS_SIGN_NAME", "短视频平台")
        template_code = os.getenv("ALIYUN_SMS_TEMPLATE_CODE")
        
        if not access_key_id or not access_key_secret or not template_code:
            logger.warning("阿里云短信配置不完整，使用模拟服务")
            return MockSMSService()
        
        return AliyunSMSService(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            sign_name=sign_name,
            template_code=template_code
        )
    
    elif sms_provider == "tencent":
        # 使用腾讯云短信服务
        secret_id = os.getenv("TENCENT_SECRET_ID")
        secret_key = os.getenv("TENCENT_SECRET_KEY")
        app_id = os.getenv("TENCENT_SMS_APP_ID")
        sign_name = os.getenv("TENCENT_SMS_SIGN_NAME", "短视频平台")
        template_id = os.getenv("TENCENT_SMS_TEMPLATE_ID")
        
        if not secret_id or not secret_key or not app_id or not template_id:
            logger.warning("腾讯云短信配置不完整，使用模拟服务")
            return MockSMSService()
        
        return TencentSMSService(
            secret_id=secret_id,
            secret_key=secret_key,
            app_id=app_id,
            sign_name=sign_name,
            template_id=template_id
        )
    
    else:
        # 默认使用模拟服务（开发环境）
        return MockSMSService()

