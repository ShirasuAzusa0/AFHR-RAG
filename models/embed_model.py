from typing import List, Dict, Optional
from pydantic import BaseModel, Field

class DataItem(BaseModel):
    """
        单个数据项单元
    """
    kb_id: int = Field(..., description="知识库ID")
    document_id: int = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    parent_chain: list[str] | None = Field(..., description="递进链")
    collection_name: str = Field(..., description="Collection 名称")
    context: str = Field(..., description="需要进行向量化的文本内容")

    # 数据项单元参考示例
    class Config:
        json_schema_extra = {
            "example": {
                "kb_id": 1,
                "document_id": 1,
                "collection_name": "这是 collection 的名称",
                "context": "这是需要向量化的文本内容......"
            }
        }

class Request(BaseModel):
    """
        请求数据格式
    """
    status: str = Field(..., description="状态")
    msg: str = Field(..., description="消息说明")
    data: List[DataItem] = Field(..., description="数据列表")

    # 请求数据参考示例
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "msg": "数据处理成功",
                "data": [
                    {
                        "kb_id": 1,
                        "document_id": 1,
                        "collection_name": "这是第一个 collection 的名称",
                        "context": "这是第一个文档内容......"
                    },
                    {
                        "kb_id": 2,
                        "document_id": 2,
                        "collection_name": "这是第二个 collection 的名称",
                        "context": "这是第二个文档内容......"
                    }
                ]
            }
        }

class VectorizationResponse(BaseModel):
    """
        向量化接口响应格式
    """
    status: str = Field(..., description="状态：success/error")
    msg: str = Field(..., description="响应消息")
    code: Optional[int] = Field(200, description="状态码")
    total_processed: Optional[int] = Field(0, description="处理总数")
    failed_items: Optional[List[Dict]] = Field([], description="失败项")