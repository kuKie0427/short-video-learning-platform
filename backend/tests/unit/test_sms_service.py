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
    """工厂函数（数据驱动：provider × 配置完整性矩阵）

    分支（sms_service.get_sms_service）：
    - 未配置 provider → Mock
    - provider 已配置但密钥缺失 → 降级 Mock
    - provider 已配置且密钥完整，但 SDK 未安装 → 构造真实服务时抛 ImportError
    （SDK 存在时的完整实例化见 test_complete_config_with_sdk_instantiates_real_service）
    """

    # (provider, 配置完整, 期望结果类型或异常, 用例id)
    FACTORY_CASES = [
        pytest.param(None, False, MockSMSService, id="default-mock"),
        pytest.param("aliyun", False, MockSMSService, id="aliyun-incomplete-config"),
        pytest.param("tencent", False, MockSMSService, id="tencent-incomplete-config"),
        pytest.param("aliyun", True, ImportError, id="aliyun-complete-no-sdk"),
        pytest.param("tencent", True, ImportError, id="tencent-complete-no-sdk"),
    ]

    # 完整配置分支所需的全部环境变量（sms_service.py:158-192 逐一校验）
    _ALIYUN_KEYS = ("ALIYUN_ACCESS_KEY_ID", "ALIYUN_ACCESS_KEY_SECRET", "ALIYUN_SMS_TEMPLATE_CODE")
    _TENCENT_KEYS = ("TENCENT_SECRET_ID", "TENCENT_SECRET_KEY", "TENCENT_SMS_APP_ID", "TENCENT_SMS_TEMPLATE_ID")

    @pytest.mark.parametrize("provider, complete, expected", FACTORY_CASES)
    def test_factory_branch_matrix(self, monkeypatch, provider, complete, expected):
        """provider 分支矩阵：未配置/密钥缺失 → Mock；密钥完整但 SDK 缺失 → ImportError"""
        if provider:
            monkeypatch.setenv("SMS_PROVIDER", provider)
        else:
            monkeypatch.delenv("SMS_PROVIDER", raising=False)
        keys = self._ALIYUN_KEYS if provider == "aliyun" else self._TENCENT_KEYS
        for key in keys:
            if complete:
                monkeypatch.setenv(key, "test-value")
            else:
                monkeypatch.delenv(key, raising=False)
        if expected is ImportError:
            with pytest.raises(ImportError):
                get_sms_service()
        else:
            assert isinstance(get_sms_service(), expected)

    def test_complete_config_with_sdk_instantiates_real_service(self, monkeypatch):
        """完整配置 + SDK 已安装 → 实例化真实服务（注入 fake SDK 验证工厂接线）"""
        monkeypatch.setenv("SMS_PROVIDER", "aliyun")
        for key in self._ALIYUN_KEYS:
            monkeypatch.setenv(key, "test-value")
        # 注入 fake SDK（monkeypatch.setitem 自动还原，避免 sys.modules 残留）
        fake_client_mod = types.ModuleType("aliyunsdkcore.client")
        fake_client_mod.AcsClient = mock.MagicMock
        fake_req_mod = types.ModuleType("aliyunsdkcore.request")
        fake_req_mod.CommonRequest = mock.MagicMock
        monkeypatch.setitem(sys.modules, "aliyunsdkcore", types.ModuleType("aliyunsdkcore"))
        monkeypatch.setitem(sys.modules, "aliyunsdkcore.client", fake_client_mod)
        monkeypatch.setitem(sys.modules, "aliyunsdkcore.request", fake_req_mod)

        service = get_sms_service()
        assert isinstance(service, AliyunSMSService)


@pytest.mark.unit
class TestAliyunSMSService:
    """阿里云短信（注入假 SDK，monkeypatch.setitem 自动还原）"""

    def _install_fake_sdk(self, monkeypatch, response=None, exc=None):
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
        monkeypatch.setitem(sys.modules, "aliyunsdkcore", types.ModuleType("aliyunsdkcore"))
        monkeypatch.setitem(sys.modules, "aliyunsdkcore.client", fake_client_mod)
        monkeypatch.setitem(sys.modules, "aliyunsdkcore.request", fake_req_mod)

    # (SDK响应, 是否抛异常, 预期结果, 用例id)
    SEND_CASES = [
        pytest.param(b"{}", None, True, id="send-success"),
        pytest.param(None, RuntimeError("sms api down"), False, id="send-exception"),
    ]

    @pytest.mark.parametrize("response, exc, expected", SEND_CASES)
    def test_send_matrix(self, monkeypatch, response, exc, expected):
        """阿里云发送矩阵：SDK 正常返回 → True，抛异常 → False"""
        self._install_fake_sdk(monkeypatch, response=response, exc=exc)
        service = AliyunSMSService("key", "secret", "签名", "SMS_001")
        assert service.send_sms("13900000000", "123456") is expected


@pytest.mark.unit
class TestTencentSMSService:
    """腾讯云短信（注入假 SDK，monkeypatch.setitem 自动还原）"""

    def _install_fake_sdk(self, monkeypatch, code="Ok"):
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
            monkeypatch.setitem(sys.modules, name, mod)

    # (SDK返回码, 预期结果, 用例id)
    SEND_CASES = [
        pytest.param("Ok", True, id="send-success"),
        pytest.param("LimitExceeded", False, id="send-limit-exceeded"),
    ]

    @pytest.mark.parametrize("code, expected", SEND_CASES)
    def test_send_matrix(self, monkeypatch, code, expected):
        """腾讯云发送矩阵：返回码 Ok → True，业务失败码 → False"""
        self._install_fake_sdk(monkeypatch, code=code)
        service = TencentSMSService("sid", "skey", "app1", "签名", "tmpl")
        assert service.send_sms("13900000000", "123456") is expected
