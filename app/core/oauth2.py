from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends
from app.core.security import oauth2_scheme

async def get_token(token: str = Depends(oauth2_scheme)) -> str:
    return token
