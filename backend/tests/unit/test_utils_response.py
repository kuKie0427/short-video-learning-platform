"""
响应工具函数单元测试
"""
import pytest
from fastapi.responses import JSONResponse

from common.utils.response import (
    success_response,
    error_response,
    not_found_response,
    unauthorized_response,
    forbidden_response
)


class TestSuccessResponse:
    """测试成功响应"""
    
    def test_success_response_with_data(self):
        """测试带数据的成功响应"""
        data = {"id": "123", "name": "test"}
        response = success_response(data=data)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200
        
        content = response.body.decode()
        assert "code" in content
        assert "200" in content
        assert "message" in content
        assert "data" in content
    
    def test_success_response_without_data(self):
        """测试不带数据的成功响应"""
        response = success_response()
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200
    
    def test_success_response_with_custom_message(self):
        """测试自定义消息的成功响应"""
        response = success_response(message="操作成功")
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200
    
    def test_success_response_with_custom_code(self):
        """测试自定义状态码的成功响应"""
        response = success_response(code=201)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 200  # HTTP状态码始终是200


class TestErrorResponse:
    """测试错误响应"""
    
    def test_error_response_default(self):
        """测试默认错误响应"""
        response = error_response("操作失败")
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
    
    def test_error_response_with_code(self):
        """测试带状态码的错误响应"""
        response = error_response("未找到", code=404)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
    
    def test_error_response_with_data(self):
        """测试带数据的错误响应"""
        data = {"field": "error details"}
        response = error_response("验证失败", code=422, data=data)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 422
    
    def test_error_response_invalid_code(self):
        """测试无效状态码的错误响应"""
        # 无效状态码应该被限制在400-599范围内
        response = error_response("错误", code=200)
        assert response.status_code == 400  # 应该被限制为400


class TestSpecialResponses:
    """测试特殊响应函数"""
    
    def test_not_found_response(self):
        """测试404响应"""
        response = not_found_response()
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
    
    def test_not_found_response_custom_message(self):
        """测试自定义消息的404响应"""
        response = not_found_response("资源不存在")
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 404
    
    def test_unauthorized_response(self):
        """测试401响应"""
        response = unauthorized_response()
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
    
    def test_forbidden_response(self):
        """测试403响应"""
        response = forbidden_response()
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 403

