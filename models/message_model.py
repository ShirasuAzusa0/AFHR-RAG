from pydantic import BaseModel, Field


class MMDataItem(BaseModel):
    """
        单个数据项单元
    """
    session_id: int = Field(..., description="会话ID")
    message_id: int = Field(..., description="消息ID")
    content: str = Field(..., description="消息内容")
    role: str = Field(..., description="角色")

    # 数据项单元参考示例
    class Config:
        json_schema_extra = {
            "example": {
                "session_id": 1,
                "message_id": 1,
                "content": "这是消息的具体内容",
                "role": "这是消息对应的角色身份"
            }
        }