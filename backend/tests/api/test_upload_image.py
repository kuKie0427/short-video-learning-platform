"""
上传服务补充测试

- upload_image：base64 图片上传（带/不带 data: 前缀、无效数据 422）
- upload_chunk：参数校验分支（缺 upload_id / 缺 chunk_index / 非整数索引 → 400）
"""
import base64
import uuid
import pytest

from services.upload.app.services.storage import LocalStorageService


@pytest.mark.api
class TestUploadImage:
    """图片上传"""

    def test_upload_image_with_data_prefix(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """带 data:image/...;base64, 前缀的 base64 上传成功"""
        from services.upload.app.api import upload as upload_api

        storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
        monkeypatch.setattr(upload_api, "get_storage_service", lambda: storage)

        png_base64 = base64.b64encode(b"\x89PNG fake image data").decode()
        response = upload_client.post(
            "/api/upload/image",
            headers=auth_headers,
            json={"image": f"data:image/png;base64,{png_base64}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["url"].startswith("/uploads/avatars/")

    def test_upload_image_without_prefix(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """无前缀的纯 base64 也能上传"""
        from services.upload.app.api import upload as upload_api

        storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
        monkeypatch.setattr(upload_api, "get_storage_service", lambda: storage)

        raw = base64.b64encode(b"plain image bytes").decode()
        response = upload_client.post(
            "/api/upload/image",
            headers=auth_headers,
            json={"image": raw}
        )

        assert response.status_code == 200

    def test_upload_image_invalid_base64(
        self, upload_client, auth_headers, db, test_user, tmp_path, monkeypatch
    ):
        """无效 base64 → 422（客户端输入错误，而非 500 服务器错误）

        历史缺陷：binascii.Error 未被捕获，落入通用 except → 500；
        已修复为 binascii.Error 单独捕获返回 422。
        """
        from services.upload.app.api import upload as upload_api

        storage = LocalStorageService(base_dir=str(tmp_path / "uploads"))
        monkeypatch.setattr(upload_api, "get_storage_service", lambda: storage)

        response = upload_client.post(
            "/api/upload/image",
            headers=auth_headers,
            json={"image": "!!!not-base64!!!"}
        )

        assert response.status_code == 422
        assert response.json()["code"] == 422


@pytest.mark.api
class TestUploadChunkValidation:
    """分片上传参数校验"""

    def test_missing_upload_id_returns_400(self, upload_client, auth_headers):
        response = upload_client.put(
            "/api/upload/chunk",
            headers={**auth_headers, "chunk_index": "0"},
            content=b"data"
        )
        assert response.status_code == 400

    def test_missing_chunk_index_returns_400(self, upload_client, auth_headers):
        response = upload_client.put(
            "/api/upload/chunk",
            headers={**auth_headers, "upload_id": "UP_X"},
            content=b"data"
        )
        assert response.status_code == 400

    def test_non_integer_chunk_index_returns_400(self, upload_client, auth_headers):
        response = upload_client.put(
            "/api/upload/chunk",
            headers={**auth_headers, "upload_id": "UP_X", "chunk_index": "abc"},
            content=b"data"
        )
        assert response.status_code == 400
