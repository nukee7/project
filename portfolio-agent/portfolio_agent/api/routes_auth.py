"""Auth routes — sign-up and sign-in."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from portfolio_agent.auth.tokens import create_token
from portfolio_agent.api.state import app_state

router = APIRouter()


class SignUpRequest(BaseModel):
    email: str = Field(..., description="User email", examples=["investor@example.com"])
    name: str = Field(..., description="User name", examples=["Rahul Sharma"])
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")


class SignInRequest(BaseModel):
    email: str = Field(..., examples=["investor@example.com"])
    password: str = Field(...)


class AuthResponse(BaseModel):
    user_id: str
    email: str
    name: str
    token: str


@router.post("/signup", response_model=AuthResponse, summary="Register a new user")
async def sign_up(body: SignUpRequest) -> AuthResponse:
    try:
        user = app_state.user_store.sign_up(
            email=body.email,
            name=body.name,
            password=body.password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    token = create_token(user.user_id, user.email)

    return AuthResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        token=token,
    )


@router.post("/signin", response_model=AuthResponse, summary="Sign in and get a token")
async def sign_in(body: SignInRequest) -> AuthResponse:
    user = app_state.user_store.sign_in(email=body.email, password=body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_token(user.user_id, user.email)

    return AuthResponse(
        user_id=user.user_id,
        email=user.email,
        name=user.name,
        token=token,
    )
