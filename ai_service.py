import json
from langchain_openai import ChatOpenAI
from config import OPENAI_API_KEY
from prompts import RECOMMEND_PROMPT, ANALYZE_PREFERENCE_PROMPT
from random import sample, uniform, choice

def _get_title_artist_for_tagline(song: dict) -> tuple[str, str]:
    """태그라인 생성용으로 제목과 아티스트를 추출합니다."""
    title_kr = song.get("title_kr", "")
    title_en = song.get("title_en", "")
    title_jp = song.get("title_jp", "")
    
    # 순서대로 한국어 제목 > 영어 제목 > 일본어 제목 사용
    title = title_kr.strip() or title_en.strip() or title_jp.strip() or "Unknown Title"
    
    artist_kr = song.get("artist_kr", "")
    artist = song.get("artist", "")
    
    # 순서대로 한국어 아티스트 > 원어 아티스트 사용
    artist_name = artist_kr.strip() or artist.strip() or "Unknown Artist"
    
    return title, artist_name

def _analyze_user_preference(favorite_songs: list[dict]) -> dict:
    """사용자의 선호도를 AI로 분석합니다."""
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
    """AI를 사용하여 후보 노래들 중에서 추천할 노래들을 선택합니다."""
    if not candidate_songs:
        return []
    
    song_list_text = "\n".join([
        f"{i+1}.{song.get('title_kr', 'Unknown')}-{song.get('artist_kr', 'Unknown')}({song.get('genre', 'Unknown')},{song.get('mood', 'Unknown')})"
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

def _make_tagline(label: str, songs: list[dict]) -> str:
    """AI를 사용하여 그룹의 태그라인을 생성합니다."""
    from prompts import GROUP_TAGLINE_PROMPT
    
    reps = sample(songs, k=min(3, len(songs)))
    sample_txt = " / ".join(
        f"{_get_title_artist_for_tagline(s)[0]} - {_get_title_artist_for_tagline(s)[1]}" for s in reps
    )
    
    random_temp = uniform(0.8, 1.2)
    random_tokens = choice([30, 40, 50])
    
    llm = ChatOpenAI(
        model_name="gpt-4o-mini",
        temperature=random_temp,
        max_tokens=random_tokens,
        openai_api_key=OPENAI_API_KEY
    )
    
    try:
        response = llm.invoke(
            GROUP_TAGLINE_PROMPT.format(label=label, sample_songs=sample_txt)
        ).content.strip()
        
        response = response.strip('"').strip("'").strip()
        return response
    except Exception as e:
        fallback_tagline = f"{label}의 매력적인 선곡 🎵"
        return fallback_tagline 