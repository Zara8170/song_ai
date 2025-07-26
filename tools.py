import os
import json
import pymysql
from typing import Optional
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
from prompts import RECOMMEND_PROMPT, ANALYZE_PREFERENCE_PROMPT
from collections import Counter
from collections import defaultdict
from random import sample, uniform, choice
import time

def _get_title_artist(song: dict) -> tuple[str, str]:
    title  = song.get("title")  or song.get("title_kr")  or ""
    artist = song.get("artist_kr") or ""
    return title.strip(), artist.strip()

def _analyze_user_preference(favorite_songs: list[dict]) -> dict:
    if not favorite_songs:
        return None
    
    favorites_text = "\n".join([
        f"- {song.get('title_kr', 'Unknown')} by {song.get('artist_kr', 'Unknown')} "
        f"(장르: {song.get('genre', 'Unknown')}, 분위기: {song.get('mood', 'Unknown')})"
        for song in favorite_songs
    ])
    
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0.3,
        max_tokens=500,
        openai_api_key=OPENAI_API_KEY
    )
    
    analyze_chain = ANALYZE_PREFERENCE_PROMPT | llm
    json_response = ""
    
    try:
        response = analyze_chain.invoke({"favorites": favorites_text}).content.strip()
        json_response = response
        
        if json_response.lower().strip() == "null":
            return None
            
        if "```json" in json_response:
            json_start = json_response.find("```json") + 7
            json_end = json_response.find("```", json_start)
            if json_end == -1:
                json_end = len(json_response)
            json_response = json_response[json_start:json_end].strip()
        elif "```" in json_response:
            json_start = json_response.find("```") + 3
            json_end = json_response.find("```", json_start)
            if json_end == -1:
                json_end = len(json_response)
            json_response = json_response[json_start:json_end].strip()
        
        json_response = json_response.replace("```", "").strip()
        
        start_idx = json_response.find('{')
        end_idx = json_response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_response = json_response[start_idx:end_idx+1]
        
        result = json.loads(json_response)
        return result
        
    except json.JSONDecodeError as e:
        return None
    except Exception as e:
        return None

def _ai_recommend_songs(candidate_songs: list[dict], user_preference: dict, target_count: int = 20) -> list[dict]:
    if not candidate_songs:
        return []
    
    song_list_text = "\n".join([
        f"{i+1}. {song.get('title_kr', 'Unknown')} - {song.get('artist_kr', 'Unknown')} "
        f"(장르: {song.get('genre', 'Unknown')}, 분위기: {song.get('mood', 'Unknown')}, "
        f"TJ: {song.get('tj_number', 'N/A')}, KY: {song.get('ky_number', 'N/A')})"
        for i, song in enumerate(candidate_songs)
    ])
    
    preference_text = "없음"
    if user_preference:
        preference_text = f"""
        - 선호 장르: {', '.join(user_preference.get('preferred_genres', []))}
        - 선호 분위기: {', '.join(user_preference.get('preferred_moods', []))}
        - 전체 취향: {user_preference.get('overall_taste', '')}
        """
    
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=0.7,
        max_tokens=2000,
        openai_api_key=OPENAI_API_KEY
    )
    
    recommend_chain = RECOMMEND_PROMPT | llm
    json_response = ""
    
    try:
        response = recommend_chain.invoke({
            "user_preference": preference_text,
            "song_list": song_list_text,
            "target_count": target_count
        }).content.strip()
        
        json_response = response
        
        if "```json" in response:
            json_start = response.find("```json") + 7
            json_end = response.find("```", json_start)
            if json_end == -1:
                json_end = len(response)
            json_response = response[json_start:json_end].strip()
        elif "```" in response:
            json_start = response.find("```") + 3
            json_end = response.find("```", json_start)
            if json_end == -1:
                json_end = len(response)
            json_response = response[json_start:json_end].strip()
        
        json_response = json_response.replace("```", "").strip()
        
        start_idx = json_response.find('{')
        end_idx = json_response.rfind('}')
        if start_idx != -1 and end_idx != -1:
            json_response = json_response[start_idx:end_idx+1]
        
        result = json.loads(json_response)
        recommended_songs = result.get("recommended_songs", [])
        return recommended_songs
        
    except json.JSONDecodeError as e:
        fallback_count = min(target_count, len(candidate_songs))
        fallback_result = sample(candidate_songs, fallback_count)
        return fallback_result
    except Exception as e:
        fallback_count = min(target_count, len(candidate_songs))
        fallback_result = sample(candidate_songs, fallback_count)
        return fallback_result

def _match_ai_recommendations_with_db(ai_recs: list[dict], candidate_songs: list[dict]) -> list[dict]:
    matched_songs = []
    
    for i, ai_rec in enumerate(ai_recs):
        ai_title = ai_rec.get("title", "").strip()
        ai_artist = ai_rec.get("artist_kr", "").strip()
        
        found_match = False
        for db_song in candidate_songs:
            db_title = db_song.get("title_kr", "").strip()
            db_artist = db_song.get("artist_kr", "").strip()
            
            if ai_title == db_title and ai_artist == db_artist:
                matched_song = db_song.copy()
                matched_song["mood"] = ai_rec.get("mood", db_song.get("mood", ""))
                matched_song["genre"] = ai_rec.get("genre", db_song.get("genre", ""))
                matched_songs.append(matched_song)
                found_match = True
                break
    
    if len(matched_songs) < len(ai_recs):
        remaining_count = len(ai_recs) - len(matched_songs)
        remaining_songs = sample(candidate_songs, min(remaining_count, len(candidate_songs)))
        matched_songs.extend(remaining_songs)
    
    return matched_songs

def _group_songs(recs: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for s in recs:
        key = s.get("mood") or s.get("genre") or "기타"
        groups[key].append(s)
    return groups

def _make_tagline(label: str, songs: list[dict]) -> str:
    from prompts import GROUP_TAGLINE_PROMPT
    
    reps = sample(songs, k=min(3, len(songs)))
    sample_txt = " / ".join(
        f"{_get_title_artist(s)[0]} - {_get_title_artist(s)[1]}" for s in reps
    )
    
    random_temp = uniform(0.8, 1.2)
    random_tokens = choice([30, 40, 50])
    
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=random_temp,
        max_tokens=random_tokens,
        openai_api_key=OPENAI_API_KEY
    )
    
    responses = []
    
    for attempt in range(2):
        try:
            response = llm.invoke(
                GROUP_TAGLINE_PROMPT.format(label=label, sample_songs=sample_txt)
            ).content.strip()
            
            response = response.strip('"').strip("'").strip()
            responses.append(response)
        except Exception as e:
            continue
    
    if not responses:
        fallback_tagline = f"{label}의 매력적인 선곡 🎵"
        return fallback_tagline
    
    final_tagline = min(responses, key=len) if len(responses) > 1 else responses[0]
    return final_tagline

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
            tagline = _make_tagline(label, norm_songs)
            payload.append({
                "label": label,
                "songs": norm_songs,
                "tagline": tagline,
            })
    
    return payload

def get_candidate_songs(favorite_song_ids: list[int], limit: int = 100) -> list[dict]:
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
        
        similar_songs = []
        if genres or artists:
            genre_list = "','".join(set(genres)) if genres else ""
            artist_list = "','".join(set(artists)) if artists else ""
            genre_clause = f"genre IN ('{genre_list}')" if genres else "1=0"
            artist_clause = f"artist_kr IN ('{artist_list}')" if artists else "1=0"
            
            sql = (f"SELECT * FROM song WHERE ({genre_clause} OR {artist_clause}) "
                   f"AND song_id NOT IN ({fav_ids_str}) ORDER BY RAND() LIMIT {limit//2}")
            cur.execute(sql)
            similar_songs = cur.fetchall()
        
        remaining_limit = limit - len(similar_songs)
        if remaining_limit > 0:
            sql = (f"SELECT * FROM song WHERE song_id NOT IN ({fav_ids_str}) "
                   f"ORDER BY RAND() LIMIT {remaining_limit}")
            cur.execute(sql)
            random_songs = cur.fetchall()
            similar_songs.extend(random_songs)
        
        candidates = similar_songs
    else:
        cur.execute(f"SELECT * FROM song ORDER BY RAND() LIMIT {limit}")
        candidates = cur.fetchall()

    cur.close()
    conn.close()
    return candidates

def get_favorite_songs_info(favorite_song_ids: list[int]) -> list[dict]:
    if not favorite_song_ids:
        return []
        
    db_host = os.getenv("DB_HOST")
    db_port = int(os.getenv("DB_PORT"))
    db_user = os.getenv("DB_USER")
    db_pw = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")

    conn = pymysql.connect(host=db_host, port=db_port, user=db_user,
                           password=db_pw, db=db_name, charset="utf8")
    cur = conn.cursor(pymysql.cursors.DictCursor)

    fav_ids_str = ",".join(map(str, favorite_song_ids))
    cur.execute(f"SELECT * FROM song WHERE song_id IN ({fav_ids_str})")
    favorites = cur.fetchall()

    cur.close()
    conn.close()
    return favorites

def recommend_songs(favorite_song_ids: list[int]) -> dict:
    favorite_songs = get_favorite_songs_info(favorite_song_ids)
    user_preference = _analyze_user_preference(favorite_songs)
    
    candidate_songs = get_candidate_songs(favorite_song_ids, limit=100)
    if not candidate_songs:
        return {"error": "추천할 노래를 찾지 못했습니다."}

    ai_recommended = _ai_recommend_songs(candidate_songs, user_preference, target_count=20)
    
    if not ai_recommended:
        ai_recommended = sample(candidate_songs, min(20, len(candidate_songs)))
    else:
        ai_recommended = _match_ai_recommendations_with_db(ai_recommended, candidate_songs)
    
    groups_payload = _build_grouped_payload(ai_recommended, favorite_song_ids)

    return {
        "groups": groups_payload
    }
