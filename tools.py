import os
import pymysql
from typing import Optional
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
from prompts import AGENT_PROMPT, RECOMMEND_PROMPT
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

def get_candidate_songs(liked_song_ids: list[int], limit: int = 30) -> list[dict]:
    """
    liked_song_ids: 사용자가 즐겨찾기한 곡의 songId 리스트
    limit: 후보군 최대 개수
    """
    import pymysql
    import os
    from collections import Counter

    db_host = os.getenv("MYSQL_HOST")
    db_port = int(os.getenv("MYSQL_PORT", 3306))
    db_user = os.getenv("MYSQL_USER")
    db_password = os.getenv("MYSQL_PASSWORD")
    db_name = os.getenv("MYSQL_DB_NAME")

    conn = pymysql.connect(host=db_host, port=db_port, user=db_user, password=db_password, db=db_name, charset='utf8')
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    candidates = []

    if liked_song_ids:
        # 1. 즐겨찾기 곡 정보 조회 (songId 기준)
        liked_song_ids_str = ','.join(map(str, liked_song_ids))
        cursor.execute(f"SELECT * FROM song WHERE songId IN ({liked_song_ids_str})")
        liked_songs_info = cursor.fetchall()

        # 2. 성향 추론 (장르/아티스트)
        genres = [song['genre'] for song in liked_songs_info if song.get('genre')]
        artists = [song['artist_kr'] for song in liked_songs_info if song.get('artist_kr')]
        top_genre = Counter(genres).most_common(1)[0][0] if genres else None
        top_artist = Counter(artists).most_common(1)[0][0] if artists else None

        # 3. 성향과 유사한 곡 후보 추출 (장르/아티스트 기반, songId 제외)
        where_clauses = []
        if top_genre:
            where_clauses.append(f"genre = '{top_genre}'")
        if top_artist:
            where_clauses.append(f"artist_kr = '{top_artist}'")
        where_sql = " OR ".join(where_clauses) if where_clauses else "1=1"
        sql_query = f"SELECT * FROM song WHERE ({where_sql}) AND songId NOT IN ({liked_song_ids_str}) ORDER BY RAND() LIMIT {limit}"
        cursor.execute(sql_query)
        candidates = cursor.fetchall()

        # 후보가 부족하면 랜덤 곡 추가 (songId 제외)
        if len(candidates) < limit:
            sql_query = f"SELECT * FROM song WHERE songId NOT IN ({liked_song_ids_str}) ORDER BY RAND() LIMIT {limit - len(candidates)}"
            cursor.execute(sql_query)
            candidates.extend(cursor.fetchall())
    else:
        # 즐겨찾기 없으면 랜덤 후보군
        sql_query = f"SELECT * FROM song ORDER BY RAND() LIMIT {limit}"
        cursor.execute(sql_query)
        candidates = cursor.fetchall()

    cursor.close()
    conn.close()
    return candidates


def recommend_songs(liked_song_ids: list[int], user_message: Optional[str] = None) -> list[dict]:
    """
    liked_song_ids: 사용자가 즐겨찾기한 곡의 songId 리스트
    user_message: 사용자 입력 메시지
    """
    candidate_songs = get_candidate_songs(liked_song_ids, limit=30)
    if not candidate_songs:
        return []

    song_list_str = "\n".join(
        f"{song['title_kr']} - {song['artist_kr']} - {song.get('genre', '')} - {song.get('tj_number', '')} - {song.get('ky_number', '')}"
        for song in candidate_songs
    )

    prompt = RECOMMEND_PROMPT.format(
        song_list=song_list_str,
        user_message=user_message or '',
        liked_songs=liked_song_ids
    )

    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, openai_api_key=OPENAI_API_KEY)
    response = llm.invoke(prompt)
    answer = response.content if hasattr(response, 'content') else str(response)

    # 파싱 로직 (장르 포함)
    recommended_songs = []
    for line in answer.splitlines():
        if '-' in line:
            parts = [p.strip() for p in line.split('-')]
            if len(parts) >= 2:
                song = {
                    'title_kr': parts[0],
                    'artist_kr': parts[1],
                }
                if len(parts) > 2:
                    song['genre'] = parts[2]
                if len(parts) > 3:
                    song['tj_number'] = parts[3]
                if len(parts) > 4:
                    song['ky_number'] = parts[4]
                recommended_songs.append(song)
    return recommended_songs