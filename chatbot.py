import json
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Optional

from config import OPENAI_API_KEY
from prompts import AGENT_PROMPT
from tools import recommend_songs

llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY)

@tool
def recommend_songs_tool(favorites: list[int], message: Optional[str] = None) -> dict:     
    """
    Provides song recommendations based on user's favorites.
    Args:
        favorites (list[int]): A list of song IDs that the user has liked.
        message (str, optional): The user's message or query.
    """
    try:
        recommended_songs_list = recommend_songs(favorites, message)

        return {
            "recommended_songs": recommended_songs_list,
            "favorites": favorites
        }

    except Exception as e:
        return {"error": f"노래 추천 중 오류가 발생했습니다: {str(e)}"}

tools = [recommend_songs_tool]

agent = create_openai_tools_agent(llm, tools, AGENT_PROMPT)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True
)

def get_chat_executor(chat_history):
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        memory=chat_history
    )
