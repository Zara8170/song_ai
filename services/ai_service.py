import json
import logging
from random import sample
from langchain_openai import ChatOpenAI
from config.settings import OPENAI_API_KEY
from config.prompts import RECOMMEND_PROMPT, ANALYZE_PREFERENCE_PROMPT
from pydantic import ValidationError
from models.data_models import UserPreference, RecommendationResponse

logger = logging.getLogger(__name__)

def _get_title_artist_for_tagline(song: dict) -> tuple[str, str]:
    title_kr = song.get("title_kr", "")
    title_en = song.get("title_en", "")
    title_jp = song.get("title_jp", "")
    title_yomi = song.get("title_yomi", "")
    title = title_kr.strip() or title_en.strip() or title_jp.strip() or title_yomi.strip() or "Unknown Title"
    artist_kr = song.get("artist_kr", "")
    artist = song.get("artist", "")
    artist_name = artist_kr.strip() or artist.strip() or "Unknown Artist"
    return title, artist_name

def _analyze_user_preference(favorite_songs: list[dict]) -> dict:
    if not favorite_songs:
        return None

    favorites_text = "\n".join([
        f"- {song.get('title_kr', 'Unknown')}/{song.get('title_en', '')}/{song.get('title_yomi', '')} by {song.get('artist_kr', 'Unknown')}/{song.get('artist', '')} "
        f"(장르: {song.get('genre', 'Unknown')}, 분위기: {song.get('mood', 'Unknown')})"
        for song in favorite_songs
    ])

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.3,
        max_tokens=500,
        openai_api_key=OPENAI_API_KEY
    )

    analyze_chain = ANALYZE_PREFERENCE_PROMPT | llm
    try:
        response = analyze_chain.invoke({"favorites": favorites_text})
        
        if not response or not response.content:
            return None
            
        content = response.content
        if content is None:
            logger.warning("OpenAI API returned response with None content in _analyze_user_preference")
            return None
        response = content.strip()
        if "```" in response:
            response = response.split("```")[1]
        result = json.loads(response)
        validated = UserPreference(**result)
        return validated.dict()
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to parse user preference analysis: {e}")
        return None

def _ai_recommend_songs(candidate_songs: list[dict], user_preference: dict, target_count: int = 20) -> list[dict]:
    if not candidate_songs:
        return []

    song_list_text = "\n".join([
        f"{i+1}.{song.get('title_kr', 'Unknown')}/{song.get('title_en', '')}/{song.get('title_yomi', '')}-{song.get('artist_kr', 'Unknown')}/{song.get('artist', '')}({song.get('genre', 'Unknown')},{song.get('mood', 'Unknown')})"
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
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=2000,
        openai_api_key=OPENAI_API_KEY
    )

    recommend_chain = RECOMMEND_PROMPT | llm
    try:
        allowed_genres = sorted({s.get('genre') for s in candidate_songs if s.get('genre')})
        allowed_moods = sorted({s.get('mood') for s in candidate_songs if s.get('mood')})

        response = recommend_chain.invoke({
            "user_preference": preference_text,
            "song_list": song_list_text,
            "target_count": target_count,
            "allowed_genres": ", ".join(allowed_genres),
            "allowed_moods": ", ".join(allowed_moods),
        })
        
        if not response or not response.content:
            return sample(candidate_songs, min(target_count, len(candidate_songs)))
            
        content = response.content
        if content is None:
            logger.warning("OpenAI API returned response with None content in _ai_recommend_songs")
            return sample(candidate_songs, min(target_count, len(candidate_songs)))
        response = content.strip()
        if "```" in response:
            response = response.split("```")[1]
        result = json.loads(response)
        validated = RecommendationResponse(**result)
        return [song.dict() for song in validated.recommended_songs]
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to parse AI recommendation response: {e}")
        return sample(candidate_songs, min(target_count, len(candidate_songs)))

def _make_tagline(label: str, songs: list[dict], user_preference: dict = None) -> str:
    from config.prompts import GROUP_TAGLINE_PROMPT
    from random import sample as rsample
    reps = rsample(songs, k=min(3, len(songs)))
    sample_txt = " / ".join(
        f"{_get_title_artist_for_tagline(s)[0]} - {_get_title_artist_for_tagline(s)[1]}" for s in reps
    )

    pref_keywords = ""
    if user_preference:
        moods = ", ".join(user_preference.get("preferred_moods", []))
        genres = ", ".join(user_preference.get("preferred_genres", []))
        pref_keywords = f"(취향: {moods} | {genres})"

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=1.0,
        max_tokens=50,
        openai_api_key=OPENAI_API_KEY
    )

    try:
        prompt_text = GROUP_TAGLINE_PROMPT.format(
            label=f"{label} {pref_keywords}",
            sample_songs=sample_txt
        )
        llm_response = llm.invoke(prompt_text)
        if not llm_response or not llm_response.content:
            logger.warning(f"OpenAI API returned empty response for tagline generation (label: {label})")
            return f"{label}의 매력적인 선곡 🎵"
        response = llm_response.content.strip()
        
        tagline = response.strip('"').strip("'").strip()
        if '\n' in tagline:
            tagline = tagline.split('\n')[0].strip()
        
        tagline = tagline.lstrip('- ').lstrip('• ').lstrip('* ').strip()
        
        return tagline if tagline else f"{label}의 매력적인 선곡 🎵"
    except Exception as e:
        logger.error(f"Failed to generate tagline for label '{label}': {e}")
        return f"{label}의 매력적인 선곡 🎵"