import os
import instructor
from openai import OpenAI


class LLMClient:
    """
    大模型统一访问客户端。
    
    采用 Instructor 库对标准 OpenAI SDK 进行包装，
    使其能够强制要求大模型按照指定的 Pydantic BaseModels 结构输出 JSON 数据。
    当前默认配置为连接 DeepSeek API，使用的是 deepseek-chat 模型。
    """
    
    def __init__(self):
        """
        初始化 LLM 客户端。
        从环境变量 DEEPSEEK_API_KEY 中获取秘钥，
        并实例化带有 instructor 补丁的 OpenAI Client。
        """
        api_key = os.getenv("DEEPSEEK_API_KEY", "your_api_key_here")
        base_url = "https://api.deepseek.com"
        # 使用 instructor 包装标准 openai 客户端，开启结构化输出能力
        self.client = instructor.from_openai(
            OpenAI(api_key=api_key, base_url=base_url))
        self.model = "deepseek-chat"

    def generate_structured(self, messages: list[dict], response_model):
        """
        调用 LLM 并要求其返回符合 Pydantic 模型结构的数据。
        
        :param messages: 标准 OpenAI Chat 消息列表 [{"role": "user", "content": "..."}]
        :param response_model: 期望的 Pydantic BaseModel 类型
        :return: 经过校验并反序列化后的 Pydantic 模型实例
        """
        try:
            # temperature 设置为 0.1 保证代码/指令生成的确定性
            return self.client.chat.completions.create(
                model=self.model,
                response_model=response_model,
                messages=messages,
                temperature=0.1
            )
        except Exception as e:
            import logging
            logging.error(f"LLM Call Failed: {e}")
            raise e


# 实例化一个全局单例供各个智能体节点使用
llm_client = LLMClient()
