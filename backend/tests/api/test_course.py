"""
课程管理接口API测试
"""
import pytest


@pytest.mark.api
class TestCreateCourse:
    """测试创建课程"""
    
    def test_create_course_success(self, course_client, auth_headers):
        """测试成功创建课程"""
        response = course_client.post(
            "/api/courses",
            headers=auth_headers,
            json={
                "title": "测试课程",
                "description": "课程描述",
                "tags": ["Python", "编程"],
                "language": "zh-CN"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert data["data"]["title"] == "测试课程"
    
    def test_create_course_unauthorized(self, course_client):
        """测试未授权创建课程"""
        response = course_client.post(
            "/api/courses",
            json={"title": "测试课程"}
        )
        
        assert response.status_code == 403


@pytest.mark.api
class TestGetCourse:
    """测试获取课程"""
    
    def test_get_course_success(self, course_client, auth_headers, test_course):
        """测试成功获取课程详情"""
        response = course_client.get(
            f"/api/courses/{test_course.course_id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["course_id"] == test_course.course_id
    
    def test_get_nonexistent_course(self, course_client, auth_headers):
        """测试获取不存在的课程"""
        response = course_client.get(
            "/api/courses/nonexistent",
            headers=auth_headers
        )
        
        assert response.status_code == 404
    
    def test_get_courses_list(self, course_client, auth_headers, test_course):
        """测试获取课程列表"""
        response = course_client.get(
            "/api/courses",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert isinstance(data["data"]["items"], list)
        assert "pagination" in data["data"]


@pytest.mark.api
class TestUpdateCourse:
    """测试更新课程"""
    
    def test_update_course_success(self, course_client, auth_headers, test_course, test_user, db):
        """测试成功更新课程"""
        # 确保课程属于当前用户
        test_course.author_id = test_user.id
        db.commit()
        
        response = course_client.put(
            f"/api/courses/{test_course.course_id}",
            headers=auth_headers,
            json={
                "title": "更新后的标题",
                "description": "更新后的描述"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "course_id" in data["data"]
        assert "updated_at" in data["data"]
    
    def test_update_other_user_course(self, course_client, auth_headers, test_course, test_user2, db):
        """测试更新其他用户的课程"""
        # 设置课程属于其他用户
        test_course.author_id = test_user2.id
        db.commit()
        
        response = course_client.put(
            f"/api/courses/{test_course.course_id}",
            headers=auth_headers,
            json={"title": "尝试更新"}
        )
        
        # 应该返回403或404
        assert response.status_code in [403, 404]


@pytest.mark.api
class TestCourseVideos:
    """测试课程视频管理"""
    
    def test_add_video_to_course(self, course_client, auth_headers, test_course, test_video, test_user, db):
        """测试添加视频到课程"""
        # 确保课程和视频都属于当前用户
        test_course.author_id = test_user.id
        test_video.author_id = test_user.id
        db.commit()
        
        response = course_client.post(
            f"/api/courses/{test_course.course_id}/videos",
            headers=auth_headers,
            json={"video_ids": [str(test_video.id)]}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_remove_video_from_course(self, course_client, auth_headers, test_course, test_video, db, test_user):
        """测试从课程移除视频"""
        # 确保课程属于当前用户
        test_course.author_id = test_user.id
        
        # 先添加视频到课程
        from common.models import CourseVideo
        course_video = CourseVideo(
            course_id=test_course.id,
            video_id=test_video.id,
            segment_index=1
        )
        db.add(course_video)
        db.commit()
        
        # 移除视频
        response = course_client.delete(
            f"/api/courses/{test_course.course_id}/videos/{test_video.id}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
    
    def test_update_video_order(self, course_client, auth_headers, test_course, test_video, db, test_user):
        """测试调整视频顺序"""
        # 确保课程属于当前用户
        test_course.author_id = test_user.id
        db.commit()
        
        # 添加视频到课程
        from common.models import CourseVideo
        course_video = CourseVideo(
            course_id=test_course.id,  # 使用UUID而不是course_id字符串
            video_id=test_video.id,
            segment_index=1
        )
        db.add(course_video)
        db.commit()
        
        # 调整顺序
        response = course_client.put(
            f"/api/courses/{test_course.course_id}/videos/order",
            headers=auth_headers,
            json={
                "video_orders": [{
                    "video_id": str(test_video.id),
                    "segment_index": 2
                }]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200

