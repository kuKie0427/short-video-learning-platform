"""
存储服务适配层测试

- LocalStorageService：本地上传/删除/存在性/URL（临时目录，不污染工作区）
- 工厂函数：STORAGE_TYPE=local 默认、s3 分支
- S3StorageService：注入假 boto3 验证 URL 构造、删除失败处理；boto3 未安装时明确报错
"""
import sys
import types
import pytest
from unittest import mock

from services.upload.app.services.storage import (
    get_storage_service,
    LocalStorageService,
    S3StorageService,
)


@pytest.mark.unit
class TestLocalStorageService:
    """本地存储"""

    def test_upload_and_exists_and_delete(self, tmp_path):
        service = LocalStorageService(base_dir=str(tmp_path))
        url = service.upload_file(b"hello", "videos/1.mp4", content_type="video/mp4")

        assert url == "/uploads/videos/1.mp4"
        assert (tmp_path / "videos" / "1.mp4").read_bytes() == b"hello"
        assert service.file_exists("videos/1.mp4") is True

        assert service.delete_file("videos/1.mp4") is True
        assert service.file_exists("videos/1.mp4") is False
        # 删除不存在的文件返回 False
        assert service.delete_file("videos/none.mp4") is False

    def test_presigned_url_is_local_path(self, tmp_path):
        service = LocalStorageService(base_dir=str(tmp_path))
        assert service.get_presigned_url("videos/1.mp4") == "/uploads/videos/1.mp4"


@pytest.mark.unit
class TestGetStorageServiceFactory:
    """存储工厂函数"""

    def test_default_is_local(self, monkeypatch, tmp_path):
        monkeypatch.delenv("STORAGE_TYPE", raising=False)
        monkeypatch.setenv("UPLOAD_BASE_DIR", str(tmp_path / "uploads"))
        service = get_storage_service()
        assert isinstance(service, LocalStorageService)

    def test_s3_type_constructs_s3_service(self, monkeypatch):
        monkeypatch.setenv("STORAGE_TYPE", "s3")
        monkeypatch.setenv("S3_ENDPOINT", "http://localhost:9000")

        # 注入假 boto3 避免真实 SDK 依赖
        class FakeClient:
            def head_bucket(self, **kw):
                raise Exception("not found")

            def create_bucket(self, **kw):
                pass

        fake_mod = types.ModuleType("boto3")
        fake_mod.client = mock.MagicMock(return_value=FakeClient())
        cfg_mod = types.ModuleType("botocore.config")
        cfg_mod.Config = mock.MagicMock
        sys.modules["boto3"] = fake_mod
        sys.modules["botocore.config"] = cfg_mod
        try:
            service = get_storage_service()
        finally:
            sys.modules.pop("boto3", None)
            sys.modules.pop("botocore.config", None)

        assert isinstance(service, S3StorageService)


@pytest.mark.unit
class TestS3StorageService:
    """S3 存储（注入假 boto3）"""

    def _install_fake_boto3(self, client):
        fake_mod = types.ModuleType("boto3")
        fake_mod.client = mock.MagicMock(return_value=client)
        cfg_mod = types.ModuleType("botocore.config")
        cfg_mod.Config = mock.MagicMock
        sys.modules["boto3"] = fake_mod
        sys.modules["botocore.config"] = cfg_mod

    @pytest.fixture(autouse=True)
    def _cleanup(self):
        yield
        sys.modules.pop("boto3", None)
        sys.modules.pop("botocore.config", None)

    def test_upload_builds_url(self):
        class FakeClient:
            def head_bucket(self, **kw):
                raise Exception()

            def create_bucket(self, **kw):
                pass

            def put_object(self, **kw):
                pass

        self._install_fake_boto3(FakeClient())
        service = S3StorageService("http://localhost:9000", "ak", "sk", "videos")
        url = service.upload_file(b"data", "videos/1.mp4", content_type="video/mp4")

        assert url == "http://localhost:9000/videos/videos/1.mp4"

    def test_delete_failure_returns_false(self):
        class FakeClient:
            def head_bucket(self, **kw):
                raise Exception()

            def create_bucket(self, **kw):
                pass

            def delete_object(self, **kw):
                raise RuntimeError("s3 down")

        self._install_fake_boto3(FakeClient())
        service = S3StorageService("http://localhost:9000", "ak", "sk", "videos")
        assert service.delete_file("videos/1.mp4") is False

    def test_file_exists_head_failure_returns_false(self):
        class FakeClient:
            def head_bucket(self, **kw):
                raise Exception()

            def create_bucket(self, **kw):
                pass

            def head_object(self, **kw):
                raise Exception("not found")

        self._install_fake_boto3(FakeClient())
        service = S3StorageService("http://localhost:9000", "ak", "sk", "videos")
        assert service.file_exists("videos/1.mp4") is False

    def test_sdk_missing_raises_import_error(self):
        """boto3 未安装时应给出明确错误而非崩溃"""
        sys.modules.pop("boto3", None)
        sys.modules.pop("botocore", None)
        with pytest.raises(ImportError):
            S3StorageService("http://localhost:9000", "ak", "sk", "videos")
