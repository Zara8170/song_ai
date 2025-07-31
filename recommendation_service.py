from collections import defaultdict
from random import sample
from database_service import get_favorite_songs_info, get_candidate_songs
from ai_service import _analyze_user_preference, _ai_recommend_songs, _make_tagline
from utils import _get_title_artist

def _match_ai_recommendations_with_db(ai_recs: list[dict], candidate_songs: list[dict]) -> list[dict]:
    """AI 추천 결과와 DB의 실제 노래 정보를 매칭합니다."""
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

def _group_songs_fixed(recs: list[dict]) -> dict[str, list[dict]]:
    """
    고정된 4개 그룹으로 분류: 분위기 2개, 장르 2개
    각 그룹은 최소 3개의 노래를 포함하도록 함
    """
    mood_groups = defaultdict(list)
    genre_groups = defaultdict(list)
    
    for song in recs:
        mood = song.get("mood")
        genre = song.get("genre")
        
        if mood:
            mood_groups[mood].append(song)
        if genre:
            genre_groups[genre].append(song)
    
    top_moods = sorted(mood_groups.items(), key=lambda x: len(x[1]), reverse=True)
    top_genres = sorted(genre_groups.items(), key=lambda x: len(x[1]), reverse=True)
    
    final_groups = {}
    used_songs = set()
    
    mood_count = 0
    for mood, songs in top_moods:
        if mood_count >= 2:
            break
        if len(songs) >= 3:
            available_songs = [s for s in songs if s.get("song_id") not in used_songs]
            if len(available_songs) >= 3:
                selected_songs = available_songs[:6]
                final_groups[mood] = selected_songs
                used_songs.update(s.get("song_id") for s in selected_songs if s.get("song_id"))
                mood_count += 1
    
    genre_count = 0
    for genre, songs in top_genres:
        if genre_count >= 2:
            break
        if len(songs) >= 3:
            available_songs = [s for s in songs if s.get("song_id") not in used_songs]
            if len(available_songs) >= 3:
                selected_songs = available_songs[:6]
                final_groups[genre] = selected_songs
                used_songs.update(s.get("song_id") for s in selected_songs if s.get("song_id"))
                genre_count += 1
    
    remaining_songs = [s for s in recs if s.get("song_id") not in used_songs]
    
    while mood_count < 2 and len(remaining_songs) >= 3:
        unused_moods = [mood for mood, songs in mood_groups.items() 
                       if mood not in final_groups and len(songs) >= 1]
        
        if unused_moods:
            mood_name = unused_moods[0]
            final_groups[mood_name] = remaining_songs[:6]
            remaining_songs = remaining_songs[6:]
            mood_count += 1
        else:
            fallback_moods = ["차분한", "신나는", "따뜻한", "시원한"]
            mood_name = fallback_moods[mood_count]
            final_groups[mood_name] = remaining_songs[:6]
            remaining_songs = remaining_songs[6:]
            mood_count += 1
    
    while genre_count < 2 and len(remaining_songs) >= 3:
        unused_genres = [genre for genre, songs in genre_groups.items() 
                        if genre not in final_groups and len(songs) >= 1]
        
        if unused_genres:
            genre_name = unused_genres[0]
            final_groups[genre_name] = remaining_songs[:6]
            remaining_songs = remaining_songs[6:]
            genre_count += 1
        else:
            fallback_genres = ["팝", "록", "발라드", "댄스"]
            genre_name = fallback_genres[genre_count]
            final_groups[genre_name] = remaining_songs[:6]
            remaining_songs = remaining_songs[6:]
            genre_count += 1
    
    return final_groups

def _build_grouped_payload(recs: list[dict], favorite_song_ids: list[int] = None) -> list[dict]:
    """추천된 노래들을 그룹화하여 최종 payload를 구성합니다."""
    grouped = _group_songs_fixed(recs)
    payload = []
    
    if favorite_song_ids is None:
        favorite_song_ids = []
    
    for label, songs in grouped.items():
        norm_songs = []
        
        for s in songs:
            song_id = s.get("song_id")
            if song_id and song_id in favorite_song_ids:
                continue
                
            title_jp, title_kr, title_en, artist, artist_kr = _get_title_artist(s)
            
            norm_songs.append({
                "title_jp": title_jp,
                "title_kr": title_kr,
                "title_en": title_en,
                "artist": artist,
                "artist_kr": artist_kr,
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

def _normalize_candidates_for_cache(candidates: list[dict]) -> list[dict]:
    """후보곡을 캐시용으로 정규화합니다."""
    normalized = []
    for song in candidates:
        title_jp, title_kr, title_en, artist, artist_kr = _get_title_artist(song)
        normalized.append({
            "song_id": song.get("song_id"),
            "title_jp": title_jp,
            "title_kr": title_kr,
            "title_en": title_en,
            "artist": artist,
            "artist_kr": artist_kr,
            "genre": song.get("genre"),
            "mood": song.get("mood"),
            "tj_number": song.get("tj_number"),
            "ky_number": song.get("ky_number"),
            "recommendation_type": song.get("recommendation_type"),
            "matched_criteria": song.get("matched_criteria", [])
        })
    return normalized

def recommend_songs(favorite_song_ids: list[int]) -> dict:
    """메인 추천 함수 - 사용자의 선호 노래를 기반으로 추천 결과와 후보곡을 생성합니다."""
    if not favorite_song_ids:
        candidate_songs = get_candidate_songs([], limit=100)
        if not candidate_songs:
            return {"error": "추천할 노래를 찾지 못했습니다."}
        
        recommended = sample(candidate_songs, min(20, len(candidate_songs)))
        groups_payload = _build_grouped_payload(recommended, [])
        normalized_candidates = _normalize_candidates_for_cache(candidate_songs)
        
        return {
            "groups": groups_payload,
            "candidates": normalized_candidates
        }
    
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
    
    normalized_candidates = _normalize_candidates_for_cache(candidate_songs)

    return {
        "groups": groups_payload,
        "candidates": normalized_candidates
    } 