import os
import json
import pymysql
from typing import Optional
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
from prompts import RECOMMEND_PROMPT
from collections import Counter
from collections import defaultdict
from random import sample

def _get_title_artist(song: dict) -> tuple[str, str]:
    """
    DB 레코드(title_kr/artist_kr)와 LLM 결과(title/artist)를
    모두 지원하기 위한 통일 함수.
    """
    title  = song.get("title")  or song.get("title_kr")  or ""
    artist = song.get("artist_kr") or ""
    return title.strip(), artist.strip()

def _group_songs(recs: list[dict]) -> dict[str, list[dict]]:
    """
    분위기(mood) → 없으면 장르(genre) → 기타 로 그룹핑
    """
    groups = defaultdict(list)
    for s in recs:
        key = s.get("mood") or s.get("genre") or "기타"
        groups[key].append(s)
    return groups

def _make_tagline(label: str, songs: list[dict]) -> str:
    from prompts import GROUP_TAGLINE_PROMPT
    reps = sample(songs, k=min(5, len(songs)))

    sample_txt = " / ".join(
        f"{_get_title_artist(s)[0]} - {_get_title_artist(s)[1]}" for s in reps
    )
    llm = ChatOpenAI(model_name="gpt-4o-mini",
                     temperature=0.7,
                     max_tokens=70,
                     openai_api_key=OPENAI_API_KEY)
    return llm.invoke(
        GROUP_TAGLINE_PROMPT.format(label=label, sample_songs=sample_txt)
    ).content.strip()

def _build_grouped_payload(recs: list[dict], favorite_song_ids: list[int] = None) -> list[dict]:
    grouped = _group_songs(recs)
    sorted_groups = sorted(grouped.items(), key=lambda kv: -len(kv[1]))[:4]
    payload = []
    
    used_songs = set()
    if favorite_song_ids is None:
        favorite_song_ids = []
    
    for label, songs in sorted_groups:
        norm_songs = []
        
        for s in songs:
            song_id = s.get("song_id")
            if song_id and song_id in favorite_song_ids:
                continue
                
            title, artist = _get_title_artist(s)
            song_key = f"{title}|{artist}"
            
            if song_key in used_songs:
                continue
                
            used_songs.add(song_key)
            
            norm_songs.append({
                "title": title,
                "artist_kr": artist,
                "tj_number": s.get("tj_number"),
                "ky_number": s.get("ky_number"),
            })
        
        if norm_songs:
            payload.append({
                "label": label,
                "songs": norm_songs,
                "tagline": _make_tagline(label, norm_songs),
            })
    return payload

def get_candidate_songs(favorite_song_ids: list[int], limit: int = 60) -> list[dict]:
    db_host = os.getenv("DB_HOST")
    db_port = int(os.getenv("DB_PORT"))
    db_user = os.getenv("DB_USER")
    db_pw = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    conn = pymysql.connect(host=db_host, port=db_port, user=db_user,
                           password=db_pw, db=db_name, charset="utf8")
    cur = conn.cursor(pymysql.cursors.DictCursor)

    if favorite_song_ids:
        fav_ids_str = ",".join(map(str, favorite_song_ids))
        cur.execute(f"SELECT * FROM song WHERE song_id IN ({fav_ids_str})")
        fav_info = cur.fetchall()

        genres = [s['genre'] for s in fav_info if s.get('genre')]
        artists = [s['artist_kr'] for s in fav_info if s.get('artist_kr')]
        top_genre = Counter(genres).most_common(1)[0][0] if genres else None
        top_artist = Counter(artists).most_common(1)[0][0] if artists else None

        clauses = []
        if top_genre:
            clauses.append(f"genre = '{top_genre}'")
        if top_artist:
            clauses.append(f"artist_kr = '{top_artist}'")

        where_sql = " OR ".join(clauses) if clauses else "1=1"
        sql = (f"SELECT * FROM song WHERE ({where_sql}) "
               f"AND song_id NOT IN ({fav_ids_str}) ORDER BY RAND() LIMIT {limit}")
        cur.execute(sql)
        candidates = cur.fetchall()

        if len(candidates) < limit:
            sql = (f"SELECT * FROM song WHERE song_id NOT IN ({fav_ids_str}) "
                   f"ORDER BY RAND() LIMIT {limit - len(candidates)}")
            cur.execute(sql)
            candidates.extend(cur.fetchall())
    else:
        cur.execute(f"SELECT * FROM song ORDER BY RAND() LIMIT {limit}")
        candidates = cur.fetchall()

    cur.close()
    conn.close()
    return candidates

def recommend_songs(favorite_song_ids: list[int]) -> dict:
    candidate_songs = get_candidate_songs(favorite_song_ids, limit=30)
    if not candidate_songs:
        return {"error": "추천할 노래를 찾지 못했습니다."}

    groups_payload = _build_grouped_payload(candidate_songs, favorite_song_ids)

    return {"groups": groups_payload}
