"""
AI增强功能测试模块
"""

import asyncio
import sys
import os
from pathlib import Path

# 添加src路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from capswriter.client.utils.ai_enhancer import AIEnhancer
from capswriter.config import ClientConfig, AIConfig


async def test_ai_enhancer():
    """测试AI增强功能"""
    print("=== AI增强功能测试 ===")
    
    # 检查配置
    print(f"Base URL: {AIConfig.base_url}")
    print(f"Model: {AIConfig.model}")
    print(f"API Key: {'已配置' if AIConfig.api_key else '未配置'}")
    print()
    
    if not AIConfig.api_key:
        print("未配置API密钥，请在.env文件中配置OPENAI_API_KEY")
        return
    
    # 创建AI增强器
    enhancer = AIEnhancer()
    
    if not enhancer.enabled:
        print("AI增强器未启用")
        return
    
    print("AI增强器已启用")
    
    # 测试用例
    test_cases = [
        "我觉得我们应该，嗯，你知道的，现在开始这个项目，现在开始项目。",
        "会议安排在，嗯，安排在明天下午三点吧。",
        "我需要，呃，需要买一些，一些苹果和香蕉。",
        "Please order ten... I mean twelve units",
        "The meeting is going to be, um, going to be at like maybe 3 PM tomorrow."
    ]
    
    for i, text in enumerate(test_cases, 1):
        print(f"\n--- 测试用例 {i} ---")
        print(f"原文: {text}")
        
        try:
            enhanced_text = await enhancer.enhance_text(text)
            print(f"校对后: {enhanced_text}")
            
            if enhanced_text != text:
                print("AI校对成功")
            else:
                print("文本未发生变化")
                
        except Exception as e:
            print(f"校对失败: {str(e)}")
    
    # 测试上下文功能
    print(f"\n--- 测试上下文功能 ---")
    print("添加一些上下文...")
    
    enhancer.add_to_context("我们正在开会讨论新项目。")
    enhancer.add_to_context("需要确定项目的时间表和预算。")
    
    context_test = "那个，我觉得，嗯，这个预算应该控制在，控制在十万以内吧。"
    print(f"原文: {context_test}")
    
    try:
        enhanced_text = await enhancer.enhance_text(context_test)
        print(f"校对后: {enhanced_text}")
        print("上下文测试完成")
    except Exception as e:
        print(f"上下文测试失败: {str(e)}")
    
    # 清理资源
    await enhancer.close()
    print(f"\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(test_ai_enhancer())