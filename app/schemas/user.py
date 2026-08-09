from pydantic import BaseModel, ConfigDict, EmailStr, Field, validator

class UserBase(BaseModel):
    email: EmailStr

    @validator("email")
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()

class UserCreate(UserBase):
    # bcrypt only considers the first 72 bytes.  Reject longer values rather
    # than silently accepting a password whose suffix is ignored.
    password: str = Field(..., min_length=12, max_length=72)

    @validator("password")
    def validate_password(cls, value: str, values: dict) -> str:
        if value.strip() != value:
            raise ValueError("password must not start or end with whitespace")
        email = str(values.get("email", "")).partition("@")[0].lower()
        if email and email in value.lower():
            raise ValueError("password must not contain the email address")
        return value

class UserRead(UserBase):
    id: int
    is_active: bool
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)
