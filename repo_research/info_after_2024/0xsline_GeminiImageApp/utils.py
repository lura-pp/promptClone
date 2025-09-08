# -*- coding: utf-8 -*-
"""
API工具模块
包含API相关的通用工具函数
"""

from flask import request, jsonify, current_app
from . import api_bp


@api_bp.route('/test-api-key', methods=['POST'])
def test_api_key():
    """测试API Key是否有效"""
    try:
        data = request.get_json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API Key 不能为空'
            }), 400

        # 创建临时客户端测试API Key
        try:
            import google.genai as genai
            test_client = genai.Client(api_key=api_key)

            # 尝试调用一个简单的API来测试
            response = test_client.models.generate_content(
                model="gemini-2.0-flash",
                contents="Hello, this is a test message. Please respond with 'API Key is valid'."
            )

            if response and response.text:
                return jsonify({
                    'success': True,
                    'message': 'API Key 有效，连接成功！',
                    'response_preview': response.text[:100] + '...' if len(response.text) > 100 else response.text
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'API 响应异常'
                }), 400

        except Exception as api_error:
            error_msg = str(api_error)
            if '401' in error_msg or 'UNAUTHENTICATED' in error_msg:
                return jsonify({
                    'success': False,
                    'error': 'API Key 无效或已过期'
                }), 400
            elif '429' in error_msg or 'RESOURCE_EXHAUSTED' in error_msg:
                return jsonify({
                    'success': False,
                    'error': 'API 调用次数已达到限制，但 API Key 有效'
                }), 400
            else:
                return jsonify({
                    'success': False,
                    'error': f'API 测试失败: {error_msg}'
                }), 400

    except Exception as e:
        current_app.logger.error(f"API Key测试错误: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'测试失败: {str(e)}'
        }), 500


@api_bp.route('/features', methods=['GET'])
def get_features():
    """API功能列表"""
    features = {
        'image_qa': {
            'name': '图像问答',
            'description': '上传图像并询问相关问题',
            'endpoint': '/api/image-qa',
            'methods': ['POST'],
            'parameters': {
                'image': '图像文件',
                'question': '问题文本',
                'model': '使用的模型'
            }
        },
        'image_generation': {
            'name': '图像生成',
            'description': '根据文本描述生成图像',
            'endpoint': '/api/image-generation',
            'methods': ['POST'],
            'parameters': {
                'prompt': '描述文本',
                'model': '生成模型',
                'aspect_ratio': '宽高比',
                'style': '风格'
            }
        },
        'image_editing': {
            'name': '图像编辑',
            'description': '智能图像编辑和增强',
            'endpoint': '/api/image-editing',
            'methods': ['POST'],
            'parameters': {
                'image': '图像文件',
                'edit_type': '编辑类型',
                'edit_params': '编辑参数'
            }
        },
        'object_detection': {
            'name': '目标检测',
            'description': '检测图像中的指定对象',
            'endpoint': '/api/object-detection',
            'methods': ['POST'],
            'parameters': {
                'image': '图像文件',
                'object_name': '要检测的对象名称'
            }
        },
        'image_segmentation': {
            'name': '图像分割',
            'description': '分割图像中的指定对象',
            'endpoint': '/api/image-segmentation',
            'methods': ['POST'],
            'parameters': {
                'image': '图像文件',
                'object_name': '要分割的对象名称'
            }
        },
        'video_generation': {
            'name': '视频生成',
            'description': '根据文本描述生成视频',
            'endpoint': '/api/video-generation',
            'methods': ['POST'],
            'parameters': {
                'prompt': '视频描述',
                'duration': '视频时长',
                'style': '视频风格',
                'aspect_ratio': '宽高比'
            }
        }
    }
    return jsonify({
        'success': True,
        'features': features
    })


@api_bp.route('/models', methods=['GET'])
def get_models():
    """可用模型列表"""
    models = {
        'vision_models': {
            'gemini-2.0-flash': {
                'name': 'Gemini 2.0 Flash',
                'description': '最新的多模态模型，支持图像、文本、音频和视频',
                'capabilities': ['图像问答', '目标检测', '图像分割'],
                'recommended': True
            },
            'gemini-1.5-flash': {
                'name': 'Gemini 1.5 Flash',
                'description': '快速的多模态模型，适合实时应用',
                'capabilities': ['图像问答', '目标检测', '图像分割']
            },
            'gemini-1.5-pro': {
                'name': 'Gemini 1.5 Pro',
                'description': '高性能的多模态模型，适合复杂任务',
                'capabilities': ['图像问答', '目标检测', '图像分割']
            },
            'gemini-2.5-pro-exp-03-25': {
                'name': 'Gemini 2.5 Pro Experimental',
                'description': '实验性的高级模型，具有最新功能',
                'capabilities': ['图像问答', '目标检测', '图像分割'],
                'experimental': True
            }
        },
        'image_generation_models': {
            'imagen-3.0-generate-002': {
                'name': 'Imagen 3 (官方最新)',
                'description': 'Google最高质量的文本到图像模型',
                'model_key': 'imagen-3.0-generate-002',
                'features': ['最高质量生成', '更好的细节', '更丰富的光照'],
                'official': True,
                'recommended': True
            },
            'gemini-2.0-flash-exp-image-generation': {
                'name': 'Gemini 2.0 Flash 图像生成',
                'description': 'Gemini 2.0 Flash的图像生成功能',
                'model_key': 'gemini-2.0-flash-exp-image-generation',
                'features': ['对话式生成', '图像生成和编辑'],
                'experimental': True
            }
        },
        'video_generation_models': {
            'veo-2.0-generate-001': {
                'name': 'Veo 2.0',
                'description': 'Google最新的视频生成模型',
                'features': ['高质量视频生成', '多种风格支持', '可控时长'],
                'official': True,
                'recommended': True
            }
        },
        'supported_formats': {
            'input_images': ['PNG', 'JPG', 'JPEG', 'GIF', 'BMP', 'WebP'],
            'output_images': ['PNG', 'JPG'],
            'output_videos': ['MP4'],
            'max_file_size': '16MB'
        }
    }
    return jsonify({
        'success': True,
        'models': models
    })
