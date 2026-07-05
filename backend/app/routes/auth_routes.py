"""Authentication routes: login (issue JWT) and token verification."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth.security import (
    auth_settings,
    authenticate_user,
    create_access_token,
    get_current_user,
)
from ..config.config import load_config, logger
from ..service.llms import get_active_model_names

router = APIRouter()


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Username")
    password: str = Field(..., min_length=1, description="Password")
    llamaparse_api_key: Optional[str] = Field(
        default=None, description="LlamaParse API key (used for multimodal table/diagram parsing)"
    )

    class Config:
        json_schema_extra = {"example": {"username": "admin", "password": "admin123"}}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds")
    provider: str = Field(description="Active model provider ('gemini' or 'azure')")
    llm_model: Optional[str] = Field(default=None, description="Active LLM model name")
    embed_model: Optional[str] = Field(default=None, description="Active embedding model name")


class UserResponse(BaseModel):
    username: str


class ModelsResponse(BaseModel):
    provider: str
    llm_model: Optional[str] = None
    embed_model: Optional[str] = None
    embed_dim: int


class ProviderResponse(BaseModel):
    provider: str = Field(description="Active model provider ('gemini' or 'azure')")


@router.get("/provider", response_model=ProviderResponse, tags=["Auth"])
async def read_provider():
    models = get_active_model_names(load_config())
    return ProviderResponse(provider=models["provider"])


@router.post("/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest):
    if not authenticate_user(request.username, request.password):
        logger.warning("Failed login attempt for user '%s'", request.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    extra_claims = {}
    if request.llamaparse_api_key:
        extra_claims["llamaparse_api_key"] = request.llamaparse_api_key

    token = create_access_token(
        subject=request.username,
        extra_claims=extra_claims or None,
    )
    logger.info("User '%s' logged in successfully", request.username)

    models = get_active_model_names(load_config())

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=auth_settings.expiry_minutes * 60,
        provider=models["provider"],
        llm_model=models.get("llm_model"),
        embed_model=models.get("embed_model"),
    )


@router.get("/me", response_model=UserResponse, tags=["Auth"])
async def read_me(current_user: str = Depends(get_current_user)):
    return UserResponse(username=current_user)


@router.get("/models", response_model=ModelsResponse, tags=["Auth"])
async def read_models(current_user: str = Depends(get_current_user)):
    models = get_active_model_names(load_config())
    return ModelsResponse(**models)
