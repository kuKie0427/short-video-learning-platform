"""
短信服务适配层测试

- MockSMSService：开发环境模拟发送
- 工厂函数：provider 分支选择、配置不完整时降级为 Mock
- 阿里云/腾讯云：注入假 SDK 验证参数构造与成功/失败分支
"""
import sys
import types
import pytest
from unittest import mock

from services.auth.app.services.sms_service import (
    get_sms_service,
    MockSMSService,
    AliyunSMSService,
    TencentSMSService,
)


@pytest.mark.unit
class TestMockSMSService:
    """模拟短信服务"""

    def test_send_returns_true(self):
        assert MockSMSService().send_sms("13900000000", "123456") is True


@pytest.mark.unit
class TestGetSmsServiceFactory:
    """工厂函数"""

    def test_default_is_mock(self, monkeypatch):
        monkeypatch.delenv("SMS_PROVIDER", raising=False)
        assert isinstance(get_sms_service(), MockSMSService)

    def test_aliyun_incomplete_config_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "aliyun")
        monkeypatch.delenv("ALIYUN_ACCESS_KEY_ID", raising=False)
        assert isinstance(get_sms_service(), MockSMSService)

    def test_tencent_incomplete_config_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("SMS_PROVIDER", "tencent")
        monkeypatch.delenv("TENCENT_SECRET_ID", raising=False)
        assert isinstance(get_sms_service(), MockSMSService)


@pytest.mark.unit
class TestAliyunSMSService:
    """阿里云短信（注入假 SDK）"""

    def _install_fake_sdk(self, response=None, exc=None):
        class FakeAcsClient:
            def __init__(self, *a, **kw):
                pass

            def do_action_with_exception(self, request):
                if exc:
                    raise exc
                return response

        fake_client_mod = types.ModuleType("aliyunsdkcore.client")
        fake_client_mod.AcsClient = FakeAcsClient
        fake_req_mod = types.ModuleType("aliyunsdkcore.request")
        fake_req_mod.CommonRequest = mock.MagicMock
        sys.modules["aliyunsdkcore"] = types.ModuleType("aliyunsdkcore")
        sys.modules["aliyunsdkcore.client"] = fake_client_mod
        sys.modules["aliyunsdkcore.request"] = fake_req_mod

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        for m in ["aliyunsdkcore", "aliyunsdkcore.client", "aliyunsdkcore.request"]:
            sys.modules.pop(m, None)

    def test_send_success(self):
        self._install_fake_sdk(response=b"{}")
        service = AliyunSMSService("key", "secret", "签名", "SMS_001")
        assert service.send_sms("13900000000", "123456") is True

    def test_send_exception_returns_false(self):
        self._install_fake_sdk(exc=RuntimeError("sms api down"))
        service = AliyunSMSService("key", "secret", "签名", "SMS_001")
        assert service.send_sms("13900000000", "123456") is False


@pytest.mark.unit
class TestTencentSMSService:
    """腾讯云短信（注入假 SDK）"""

    def _install_fake_sdk(self, code="Ok"):
        class FakeResp:
            SendStatusSet = [mock.MagicMock(Code=code, Message="ok")]

        class FakeSmsClient:
            def __init__(self, *args, **kwargs):
                pass

            def SendSms(self, req):
                return FakeResp()

        fake_common_mod = types.ModuleType("tencentcloud.common")
        fake_common_mod.credential = types.ModuleType("tencentcloud.common.credential")
        fake_common_mod.credential.Credential = mock.MagicMock
        fake_common_mod.profile = types.ModuleType("tencentcloud.common.profile")
        fake_common_mod.profile.client_profile = types.ModuleType(
            "tencentcloud.common.profile.client_profile"
        )
        fake_common_mod.profile.client_profile.ClientProfile = mock.MagicMock
        fake_common_mod.profile.http_profile = types.ModuleType(
            "tencentcloud.common.profile.http_profile"
        )
        fake_common_mod.profile.http_profile.HttpProfile = mock.MagicMock

        fake_sms = types.ModuleType("tencentcloud.sms.v20210111")
        fake_sms.sms_client = types.ModuleType("tencentcloud.sms.v20210111.sms_client")
        fake_sms.sms_client.SmsClient = FakeSmsClient
        fake_sms.models = types.ModuleType("tencentcloud.sms.v20210111.models")
        fake_sms.models.SendSmsRequest = mock.MagicMock

        for name, mod in {
            "tencentcloud.common": fake_common_mod,
            "tencentcloud.common.credential": fake_common_mod.credential,
            "tencentcloud.common.profile": fake_common_mod.profile,
            "tencentcloud.common.profile.client_profile": fake_common_mod.profile.client_profile,
            "tencentcloud.common.profile.http_profile": fake_common_mod.profile.http_profile,
            "tencentcloud.sms.v20210111": fake_sms,
            "tencentcloud.sms.v20210111.sms_client": fake_sms.sms_client,
            "tencentcloud.sms.v20210111.models": fake_sms.models,
        }.items():
            sys.modules[name] = mod

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        for m in list(sys.modules):
            if m.startswith("tencentcloud"):
                sys.modules.pop(m, None)

    def test_send_success_when_status_ok(self):
        self._install_fake_sdk(code="Ok")
        service = TencentSMSService("sid", "skey", "app1", "签名", "tmpl")
        assert service.send_sms("13900000000", "123456") is True

    def test_send_failure_when_status_not_ok(self):
        self._install_fake_sdk(code="LimitExceeded")
        service = TencentSMSService("sid", "skey", "app1", "签名", "tmpl")
        assert service.send_sms("13900000000", "123456") is False
