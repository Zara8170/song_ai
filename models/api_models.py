from pydantic import BaseModel, Field, field_validator
from typing import List

class RecommendationRequest(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

    @field_validator("favorite_song_ids", mode="before")
    @classmethod
    def _normalize_ids(cls, v):
        if v is None:
            return []
        return list(dict.fromkeys(int(x) for x in v))

class RecommendationResponse(BaseModel):
    status: str = "completed"
    message: str = "추천 분석 및 생성이 완료되었습니다."
    generated_date: str = ""

class FavoriteUpdate(BaseModel):
    memberId: str
    favorite_song_ids: List[int] = Field(default_factory=list)

class CachedRecommendationRequest(BaseModel):
    memberId: str

class CachedRecommendationResponse(BaseModel):
    favorite_song_ids: List[int] = Field(default_factory=list)
    groups: list = Field(default_factory=list)
    candidates: list = Field(default_factory=list)
    generated_date: str = ""
    cached: bool = True
