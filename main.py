from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
import uvicorn
from typing import List, Optional
from dotenv import load_dotenv
import os

from tools import recommend_songs

load_dotenv()

app = FastAPI()

class RecommendationRequest(BaseModel):
    text: str
    favorite_song_ids: List[int] = Field(
        default_factory=list,
        alias="favorite_song_ids"
    )
    
    @field_validator("favorite_song_ids", mode="before")
    @classmethod
    def _cast_str_to_int(cls, v):
        if isinstance(v, list):
            return [int(x) for x in v if isinstance(x, (int, str)) and str(x).isdigit()]
        return v

@app.get("/")
def read_root():
    return {"message": "AI Song Recommender is running!"}

@app.post("/recommend")
async def recommend(request: RecommendationRequest):
    try:
        user_message = request.text
        favorite_song_ids = request.favorite_song_ids

        answer_text = recommend_songs(favorite_song_ids, user_message)

        return {
            "message": answer_text
        }

    except Exception as e:
        print(f"An error occurred during recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)