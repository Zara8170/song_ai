from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from typing import List, Optional
from dotenv import load_dotenv
import os

from chatbot import agent_executor
from tools import recommend_songs

load_dotenv()

app = FastAPI()

class RecommendationRequest(BaseModel):
    message: Optional[str] = None
    search_history: List[str]
    liked_songs: List[int]

class ChatRequest(BaseModel):
    message: str
    search_history: Optional[List[str]] = None
    liked_songs: Optional[List[int]] = None

@app.get("/")
def read_root():
    return {"message": "AI Song Recommender is running!"}

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Handles chat requests by invoking the LangChain agent.
    """
    try:
        agent_input = {"input": request.message}
        if request.search_history is not None:
            agent_input["search_history"] = request.search_history
        if request.liked_songs is not None:
            agent_input["liked_songs"] = request.liked_songs

        result = agent_executor.invoke(agent_input)
        answer = result.get("output", "죄송합니다, 답변을 찾을 수 없습니다.")
        return {"response": answer}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"response": f"오류가 발생했습니다: {str(e)}"}

@app.post("/recommend")
async def recommend(request: RecommendationRequest):
    """
    Handles song recommendation requests from the backend server.
    """
    try:
        user_message = request.message or ""
        recommended_songs = recommend_songs(request.search_history, request.liked_songs, user_message)
        
        if not recommended_songs:
            return {"recommendations": [], "message": "추천할 노래를 찾지 못했습니다."}

        formatted_recommendations = []
        for song in recommended_songs:
            formatted_recommendations.append(f"{song.get('title_kr', '제목 없음')} - {song.get('artist_kr', '아티스트 없음')} - {song.get('tj_number', '번호 없음')} - {song.get('ky_number', '번호 없음')}")
        
        recommendation_text = "다음 노래들을 추천합니다: " + ", ".join(formatted_recommendations)
        
        return {"recommendations": recommended_songs, "message": recommendation_text}

    except Exception as e:
        print(f"An error occurred during recommendation: {e}")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)