from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from ..auth import verify_password, get_user, register_user, create_access_token
from ..models import Token, UserCreate
from datetime import timedelta
from ..config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(user: UserCreate):
    if not register_user(user.username, user.password):
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User created"}


@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token(
        {"sub": form_data.username},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return Token(access_token=token)
