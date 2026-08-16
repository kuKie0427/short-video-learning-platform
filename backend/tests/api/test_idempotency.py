"""
幂等性与并发防护测试

测试分层策略：
1. API 层幂等性：重复操作不产生重复副作用（点赞切换、重复关注、分片重传覆盖）
2. 数据库约束层：唯一约束是并发场景下防止脏数据的最后防线
   （users.phone、follows.(follower_id, following_id) 有唯一约束）

已知风险记录（测试驱动发现）：
- likes 表只有普通索引 idx_likes_video_user，没有 (video_id, user_id) 唯一约束，
  toggle_like 的"先查后写"在真实并发下可能产生重复点赞行。
  建议：为 likes 表补充 UniqueConstraint('video_id', 'user_id')。
  本文件 test_toggle_like_cycle_state_and_count 验证顺序调用下的正确性。
"""
import shutil

import pytest
from sqlalchemy.exc import IntegrityError

from common.models import Follow, Like, User
from common.models.upload import UploadTask
from services.upload.app.api.upload import CHUNK_TEMP_DIR


@pytest.mark.api
class TestLikeIdempotency:
    """点赞的幂等性与计数一致性"""

    def test_toggle_like_cycle_state_and_count(self, client, auth_headers, test_user, test_video, db):
        """重复调用点赞接口：状态在 liked/unliked 间切换，点赞数与数据库行数始终一致"""
        url = "/api/interaction/like"
        body = {"video_id": str(test_video.id)}

        # 第 1 次：点赞
        resp1 = client.post(url, json=body, headers=auth_headers)
        assert resp1.status_code == 200
        data1 = resp1.json()["data"]
        assert data1["is_liked"] is True
        assert data1["like_count"] == 1

        # 第 2 次：取消点赞（幂等切换，而非重复插入）
        resp2 = client.post(url, json=body, headers=auth_headers)
        data2 = resp2.json()["data"]
        assert data2["is_liked"] is False
        assert data2["like_count"] == 0

        # 第 3 次：重新点赞
        resp3 = client.post(url, json=body, headers=auth_headers)
        data3 = resp3.json()["data"]
        assert data3["is_liked"] is True
        assert data3["like_count"] == 1

        # 数据库最终状态与接口返回值一致
        db_rows = db.query(Like).filter(
            Like.user_id == test_user.id,
            Like.video_id == test_video.id
        ).count()
        assert db_rows == 1

    def test_like_count_aggregates_across_users(self, client, auth_headers, auth_headers_user2, test_video, db):
        """两个用户点赞同一视频：计数正确聚合，不互相覆盖"""
        url = "/api/interaction/like"
        body = {"video_id": str(test_video.id)}

        client.post(url, json=body, headers=auth_headers)
        resp = client.post(url, json=body, headers=auth_headers_user2)

        data = resp.json()["data"]
        assert data["like_count"] == 2
        db_rows = db.query(Like).filter(Like.video_id == test_video.id).count()
        assert db_rows == 2


@pytest.mark.api
class TestFollowIdempotency:
    """关注的幂等性与唯一约束"""

    def test_duplicate_follow_rejected(self, client, auth_headers, test_user, test_user2, db):
        """重复关注同一用户 → 400，数据库不产生重复关系"""
        url = f"/api/follow/{test_user2.id}"

        resp1 = client.post(url, headers=auth_headers)
        assert resp1.status_code == 200

        resp2 = client.post(url, headers=auth_headers)
        assert resp2.status_code == 400
        assert resp2.json()["code"] == 400

        follow_rows = db.query(Follow).filter(
            Follow.follower_id == test_user.id,
            Follow.following_id == test_user2.id
        ).count()
        assert follow_rows == 1

    def test_follow_self_rejected(self, client, auth_headers, test_user):
        """关注自己 → 400"""
        response = client.post(f"/api/follow/{test_user.id}", headers=auth_headers)

        assert response.status_code == 400

    def test_follow_unique_constraint_as_race_backstop(self, db, test_user, test_user2):
        """数据库唯一约束 (follower_id, following_id) 是并发重复关注的最后防线"""
        db.add(Follow(follower_id=test_user.id, following_id=test_user2.id))
        db.commit()

        # 模拟并发下绕过 API 检查的重复写入：约束必须拒绝
        db.add(Follow(follower_id=test_user.id, following_id=test_user2.id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


@pytest.mark.api
class TestUploadIdempotency:
    """分片上传的幂等性"""

    def test_chunk_reupload_overwrites_content(self, upload_client, auth_headers, test_user, db):
        """同一 chunk_index 重复上传：后写覆盖先写（网络重试安全），落盘内容为最后一次"""
        upload_id = "test-idem-upload"
        task = UploadTask(
            upload_id=upload_id,
            user_id=test_user.id,
            file_name="retry.mp4",
            file_size=9,
            duration=60,
            video_type="short",
            status="initialized"
        )
        db.add(task)
        db.commit()

        chunk_dir = CHUNK_TEMP_DIR / upload_id
        try:
            # 第一次上传 4 字节
            resp1 = upload_client.put(
                "/api/upload/chunk",
                content=b"AAAA",
                headers={**auth_headers, "upload_id": upload_id, "chunk_index": "0"}
            )
            assert resp1.status_code == 200
            assert resp1.json()["data"]["chunk_size"] == 4

            # 模拟网络重试：同一分片上传不同内容（5 字节）
            resp2 = upload_client.put(
                "/api/upload/chunk",
                content=b"BBBBB",
                headers={**auth_headers, "upload_id": upload_id, "chunk_index": "0"}
            )
            assert resp2.status_code == 200
            assert resp2.json()["data"]["chunk_size"] == 5

            # 落盘文件必须是最后一次写入的内容（覆盖而非追加）
            chunk_file = chunk_dir / "chunk_0"
            assert chunk_file.read_bytes() == b"BBBBB"

            # 任务状态已推进为 uploading
            db.refresh(task)
            assert task.status == "uploading"
        finally:
            shutil.rmtree(chunk_dir, ignore_errors=True)

    def test_chunk_rejects_invalid_chunk_index(self, upload_client, auth_headers, test_user, db):
        """非整数 chunk_index → 400（请求头参数校验）"""
        task = UploadTask(
            upload_id="test-idem-bad-index",
            user_id=test_user.id,
            file_name="bad.mp4",
            file_size=4,
            duration=60,
            video_type="short",
            status="initialized"
        )
        db.add(task)
        db.commit()

        response = upload_client.put(
            "/api/upload/chunk",
            content=b"AAAA",
            headers={**auth_headers, "upload_id": "test-idem-bad-index", "chunk_index": "abc"}
        )
        assert response.status_code == 400


@pytest.mark.api
class TestRegistrationConstraint:
    """注册链路的并发防护约束"""

    def test_duplicate_phone_rejected_by_unique_constraint(self, db, test_user):
        """users.phone 唯一约束：并发注册同手机号的最后防线"""
        db.add(User(
            id="99999999-9999-4999-8999-999999999999",
            phone=test_user.phone,  # 与已存在用户相同的手机号
            nickname="重复手机号用户",
            language="zh-CN",
            roles=["learner"]
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
