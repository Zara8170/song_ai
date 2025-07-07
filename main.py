from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

from chatbot import agent_executor

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/")
def read_root():
    return {"message": "AI Song Recommender is running!"}

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Handles chat requests by invoking the LangChain SQL agent.
    """
    try:
        result = agent_executor.invoke({"input": request.message})
        answer = result.get("output", "죄송합니다, 답변을 찾을 수 없습니다.")
        return {"response": answer}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {"response": f"오류가 발생했습니다: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
