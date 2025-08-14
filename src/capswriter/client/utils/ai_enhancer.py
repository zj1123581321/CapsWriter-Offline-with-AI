"""
AI转录结果校对和润色模块
支持使用OpenAI API对转录文本进行校对和润色处理
"""

import os
import asyncio
import time
import json
import logging
from typing import List, Optional, Dict, Any
from collections import deque
import aiohttp
from aiohttp import ClientSession, ClientTimeout, ClientResponseError

from ...config import AIConfig, ClientConfig


logger = logging.getLogger(__name__)


class AIEnhancer:
    """AI文本校对和润色器"""
    
    def __init__(self):
        """初始化AI增强器"""
        self.context_history = deque(maxlen=ClientConfig.ai_context_segments)
        self.session: Optional[ClientSession] = None
        
        # 验证配置
        if not AIConfig.api_key:
            logger.warning("AI增强功能未配置API密钥，功能将被禁用")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"AI增强功能已启用，使用模型: {AIConfig.model}")
    
    async def _get_session(self) -> ClientSession:
        """获取或创建HTTP会话"""
        if self.session is None or self.session.closed:
            timeout = ClientTimeout(total=AIConfig.timeout)
            self.session = ClientSession(timeout=timeout)
        return self.session
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def add_to_context(self, text: str):
        """添加转录结果到上下文历史"""
        if text.strip():
            self.context_history.append(text.strip())
            logger.debug(f"添加到上下文: {text[:50]}...")
    
    def _build_context_text(self) -> str:
        """构建上下文文本"""
        if not self.context_history:
            return ""
        
        context_lines = []
        for i, text in enumerate(self.context_history, 1):
            context_lines.append(f"段落{i}: {text}")
        
        return "\n".join(context_lines)
    
    def _build_prompt(self, text: str, context: str = "") -> str:
        """构建AI请求的提示词"""
        base_prompt = '''你是一个专业的语音转录文本校对助手。你的任务是对语音转录生成的文本进行校对和润色，使其更加流畅、准确和易读。

主要规则：
0. 输出文本应与原始转录文本保持相同的语言（中文或英文）。
1. 保持原始意图和含义，不要添加新信息或改变所说内容的实质。
2. 确保校对后的文本流畅自然，语法正确。
3. 当说话者自我纠正时，只保留纠正后的版本。
   示例：
   输入："我觉得我们应该，嗯，你知道的，现在开始这个项目，现在开始项目。"
   输出："我觉得我们应该现在开始这个项目。"
   
   输入："会议安排在，嗯，安排在明天下午3点吧。"
   输出："会议安排在明天下午3点。"
   
   输入："我们需要在周一前完成...实际上不...是周三前"
   输出："我们需要在周三前完成"

4. 移除语音转录中的填词、重复和犹豫词（如"嗯"、"呃"、"那个"等）,但一些单个的语气词要保留，尤其是句尾。
5. 纠正语音转录错误，基于上下文进行合理推断,合理断句，补充标点符号。中英文之间应该保留空格。
6. 保持列表和数字格式清晰（使用阿拉伯数字而非中文数字）
7. 不要添加任何介绍性文本如"校对后的文本："等
8. 永远不要回答文本中出现的问题，只对格式进行整理

校对完成后，只返回校对后的文本，不要任何额外的说明或标签。'''

        if context:
            prompt = f"""{base_prompt}

参考上下文（前面的转录内容）：
{context}

当前需要校对的文本：
{text}"""
        else:
            prompt = f"""{base_prompt}

当前需要校对的文本：
{text}"""
        
        return prompt
    
    async def _make_api_request(self, prompt: str, retry_count: int = 0) -> Optional[str]:
        """发送API请求，包含重试和错误处理"""
        if retry_count >= AIConfig.max_retries:
            logger.error(f"API请求重试次数已达上限 ({AIConfig.max_retries})，放弃请求")
            return None
        
        try:
            session = await self._get_session()
            
            headers = {
                'Authorization': f'Bearer {AIConfig.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': AIConfig.model,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': AIConfig.max_tokens,
                'temperature': 0.3,
                'top_p': 0.9
            }
            
            url = f"{AIConfig.base_url.rstrip('/')}/chat/completions"
            
            logger.debug(f"发送AI请求到: {url}")
            logger.debug(f"使用模型: {AIConfig.model}")
            
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result['choices'][0]['message']['content'].strip()
                    logger.debug(f"AI响应成功，内容长度: {len(content)}")
                    return content
                elif response.status == 429:
                    # 速率限制
                    logger.warning(f"API速率限制，状态码: {response.status}")
                    delay = self._calculate_backoff_delay(retry_count)
                    logger.info(f"等待 {delay:.2f} 秒后重试...")
                    await asyncio.sleep(delay)
                    return await self._make_api_request(prompt, retry_count + 1)
                elif response.status in [500, 502, 503, 504]:
                    # 服务器错误，可重试
                    logger.warning(f"服务器错误，状态码: {response.status}")
                    delay = self._calculate_backoff_delay(retry_count)
                    logger.info(f"等待 {delay:.2f} 秒后重试...")
                    await asyncio.sleep(delay)
                    return await self._make_api_request(prompt, retry_count + 1)
                else:
                    # 其他错误
                    error_text = await response.text()
                    logger.error(f"API请求失败，状态码: {response.status}, 错误: {error_text}")
                    return None
                    
        except asyncio.TimeoutError:
            logger.warning(f"API请求超时 (尝试 {retry_count + 1}/{AIConfig.max_retries})")
            if retry_count < AIConfig.max_retries - 1:
                delay = self._calculate_backoff_delay(retry_count)
                logger.info(f"等待 {delay:.2f} 秒后重试...")
                await asyncio.sleep(delay)
                return await self._make_api_request(prompt, retry_count + 1)
            return None
            
        except Exception as e:
            logger.error(f"API请求发生异常: {str(e)} (尝试 {retry_count + 1}/{AIConfig.max_retries})")
            if retry_count < AIConfig.max_retries - 1:
                delay = self._calculate_backoff_delay(retry_count)
                logger.info(f"等待 {delay:.2f} 秒后重试...")
                await asyncio.sleep(delay)
                return await self._make_api_request(prompt, retry_count + 1)
            return None
    
    def _calculate_backoff_delay(self, retry_count: int) -> float:
        """计算指数退避延迟时间"""
        delay = AIConfig.base_delay * (2 ** retry_count)
        return min(delay, AIConfig.max_delay)
    
    async def enhance_text(self, text: str) -> str:
        """对转录文本进行AI校对和润色
        
        Args:
            text: 原始转录文本
            
        Returns:
            str: 校对后的文本，如果AI处理失败则返回原文
        """
        if not self.enabled:
            logger.debug("AI增强功能未启用，返回原文")
            return text
        
        if not text.strip():
            return text
        
        original_text = text.strip()
        logger.info(f"开始AI校对处理，原文: {original_text}")
        
        try:
            # 构建上下文
            context = self._build_context_text()
            prompt = self._build_prompt(original_text, context)
            
            # 发送API请求
            enhanced_text = await self._make_api_request(prompt)
            
            if enhanced_text:
                logger.info(f"AI校对完成")
                logger.info(f"原文: {original_text}")
                logger.info(f"校对后: {enhanced_text}")
                
                # 将原文添加到上下文历史
                self.add_to_context(original_text)
                
                return enhanced_text
            else:
                logger.warning("AI校对失败，返回原文")
                self.add_to_context(original_text)
                return original_text
                
        except Exception as e:
            logger.error(f"AI校对过程发生异常: {str(e)}")
            self.add_to_context(original_text)
            return original_text


# 全局实例
_ai_enhancer: Optional[AIEnhancer] = None


async def get_ai_enhancer() -> AIEnhancer:
    """获取全局AI增强器实例"""
    global _ai_enhancer
    if _ai_enhancer is None:
        _ai_enhancer = AIEnhancer()
    return _ai_enhancer


async def cleanup_ai_enhancer():
    """清理AI增强器资源"""
    global _ai_enhancer
    if _ai_enhancer:
        await _ai_enhancer.close()
        _ai_enhancer = None