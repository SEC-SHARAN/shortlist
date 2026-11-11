from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_validator

Role = Literal["admin", "recruiter", "hiring_manager", "viewer"]
Stage = Literal["applied", "screening", "interview", "offer", "hired", "rejected"]
Edu = Literal["high_school", "diploma", "bachelor", "master", "phd"]


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    role: Role = "recruiter"
    password: str


class UserUpdate(BaseModel):
    name: str | None = None
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = None


class UserOut(BaseModel):
    id: int; email: str; name: str; role: str; is_active: bool
    model_config = {"from_attributes": True}


class Weights(BaseModel):
    required_skills: float = Field(40, ge=0, le=100)
    preferred_skills: float = Field(15, ge=0, le=100)
    experience: float = Field(20, ge=0, le=100)
    education: float = Field(10, ge=0, le=100)
    certifications: float = Field(5, ge=0, le=100)
    semantic: float = Field(10, ge=0, le=100)


class JobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    department: str | None = None
    description: str = ""
    required_skills: list[str] = []
    preferred_skills: list[str] = []
    certifications: list[str] = []
    min_years: float = Field(0, ge=0, le=50)
    min_education: Edu | None = None
    weights: Weights = Weights()
    status: Literal["open", "closed", "draft"] = "open"

    @field_validator("required_skills", "preferred_skills", "certifications")
    @classmethod
    def clean(cls, v):
        seen, out = set(), []
        for s in v:
            s = " ".join(s.split())[:80]
            if s and s.lower() not in seen:
                seen.add(s.lower()); out.append(s)
        return out[:40]


class JobOut(JobIn):
    id: int
    created_at: datetime
    candidate_count: int = 0
    model_config = {"from_attributes": True}


class StageChange(BaseModel):
    stage: Stage
    reason: str | None = Field(default=None, max_length=2000)


class ShortlistIn(BaseModel):
    shortlisted: bool


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
