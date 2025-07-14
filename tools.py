import os
import pymysql
from typing import Optional
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
from prompts import RECOMMEND_PROMPT
from collections import Counter

def search_songs(keyword: str, target: str = "ALL", page: int = 0, size: int = 10):
    """
    Searches for songs using the backend API.
    Args:
        keyword (str): The keyword to search for.
        target (str): The search target (e.g., "ALL", "TITLE", "ARTIST"). Defaults to "ALL".
        page (int): The page number for pagination. Defaults to 0.
        size (int): The number of results per page. Defaults to 10.
    """
    import requests
    base_url = os.getenv("BACKEND_API_BASE_URL")
    url = f"{base_url}/api/es/song/search"
    params = {
        "keyword": keyword,
        "target": target,
        "page": page + 1,
        "size": size
    }
    print(f"Requesting URL: {url} with params: {params}")
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        print(f"Backend API Response Status: {response.status_code}")
        print(f"Backend API Response Body: {response.text}")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return {"error": str(e)}

def get_candidate_songs(favorite_song_ids: list[int], limit: int = 30) -> list[dict]:
    """
    favorite_song_ids: 사용자가 즐겨찾기한 곡의 song_id 리스트
    limit: 후보군 최대 개수
    """
    import pymysql
    import os
    from collections import Counter

    db_host = os.getenv("DB_HOST")
    db_port = int(os.getenv("DB_PORT"))
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_password, db=db_name, charset='utf8')
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    candidates = []

    if favorite_song_ids:
        favorite_song_ids_str = ','.join(map(str, favorite_song_ids))
        cursor.execute(f"SELECT * FROM song WHERE song_id IN ({favorite_song_ids_str})")
        favorite_songs_info = cursor.fetchall()
        print(f"[get_candidate_songs] favorite_songs_info: {favorite_songs_info}")
        print(favorite_song_ids_str)
        print(favorite_songs_info)

        genres = [song['genre'] for song in favorite_songs_info if song.get('genre')]
        artists = [song['artist_kr'] for song in favorite_songs_info if song.get('artist_kr')]
        top_genre = Counter(genres).most_common(1)[0][0] if genres else None
        top_artist = Counter(artists).most_common(1)[0][0] if artists else None

        where_clauses = []
        if top_genre:
            where_clauses.append(f"genre = '{top_genre}'")
        if top_artist:
            where_clauses.append(f"artist_kr = '{top_artist}'")
        where_sql = " OR ".join(where_clauses) if where_clauses else "1=1"
        sql_query = f"SELECT * FROM song WHERE ({where_sql}) AND song_id NOT IN ({favorite_song_ids_str}) ORDER BY RAND() LIMIT {limit}"
        cursor.execute(sql_query)
        candidates = cursor.fetchall()

        if len(candidates) < limit:
            sql_query = f"SELECT * FROM song WHERE song_id NOT IN ({favorite_song_ids_str}) ORDER BY RAND() LIMIT {limit - len(candidates)}"
            cursor.execute(sql_query)
            candidates.extend(cursor.fetchall())
    else:
        sql_query = f"SELECT * FROM song ORDER BY RAND() LIMIT {limit}"
        cursor.execute(sql_query)
        candidates = cursor.fetchall()

    cursor.close()
    conn.close()
    return candidates


def recommend_songs(favorite_song_ids: list[int], user_message: Optional[str] = None) -> str:
    
    candidate_songs = get_candidate_songs(favorite_song_ids, limit=30)
    if not candidate_songs:
        return "추천할 노래를 찾지 못했습니다."

    song_list_str = "\n".join(
        f"{song['title_kr']} - {song['artist_kr']} - {song.get('genre', '')} - {song.get('tj_number', '')} - {song.get('ky_number', '')}"
        for song in candidate_songs
    )

    prompt = RECOMMEND_PROMPT.format(
        song_list=song_list_str,
        user_message=user_message or '',
        favorites=favorite_song_ids
    )

    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY)
    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, 'content') else str(response)
    
    return answer