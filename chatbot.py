import json
from elasticsearch import Elasticsearch
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage

from config import OPENAI_API_KEY, ELASTICSEARCH_HOSTS, ELASTICSEARCH_INDEX
from prompts import AGENT_PROMPT

# --- Elasticsearch Connection ---
es_client = Elasticsearch(hosts=ELASTICSEARCH_HOSTS)

# --- LangChain Tool Definition ---
@tool
def search_songs(query: str) -> str:
    """Searches for songs in Elasticsearch based on a user's query. 
    The query can be a song title, artist, or a description of a mood."""
    try:
        # Using a multi_match query to search across multiple relevant fields
        search_query = {
            "multi_match": {
                "query": query,
                "fields": ["title_kr", "artist_kr", "title_en", "artist", "lyrics_kr"],
                "fuzziness": "AUTO"
            }
        }
        
        response = es_client.search(
            index=ELASTICSEARCH_INDEX,
            query=search_query,
            size=5 # Limit to 5 results
        )
        
        hits = response["hits"]["hits"]
        if not hits:
            return "검색 결과가 없습니다."

        # Format the results for the AI agent
        results = []
        for hit in hits:
            source = hit["_source"]
            results.append({
                "title_kr": source.get("title_kr"),
                "artist_kr": source.get("artist_kr"),
                "score": hit["_score"]
            })
        
        return json.dumps(results, ensure_ascii=False)

    except Exception as e:
        return f"An error occurred during search: {e}"

# --- LangChain Agent Setup ---
llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY)

tools = [search_songs]

agent = create_openai_tools_agent(llm, tools, AGENT_PROMPT)

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True
)

# We will manage chat history in the main application file
# This is just a placeholder for how it could be structured
def get_chat_executor(chat_history):
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        memory=chat_history
    )
