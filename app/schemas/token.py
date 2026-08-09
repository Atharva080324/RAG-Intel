from typing import Literal, Optional
from pydantic import BaseModel, Field

class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(..., ge=1)

class TokenData(BaseModel):
    email: Optional[str] = None
