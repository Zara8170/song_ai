from pydantic import BaseModel, Field
from typing import List, Optional

class UserPreference(BaseModel):
    preferred_genres: List[str] = Field(default_factory=list)
    preferred_moods: List[str] = Field(default_factory=list)
    overall_taste: str = ""
    favorite_artists: List[str] = Field(default_factory=list)

class RecommendedSong(BaseModel):
    title: str
    artist_kr: str
    mood: Optional[str] = ""
    genre: Optional[str] = ""
    reason: Optional[str] = ""

class RecommendationResponse(BaseModel):
    recommended_songs: List[RecommendedSong] = Field(default_factory=list)
