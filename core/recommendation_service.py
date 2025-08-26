from collections import defaultdict
from random import sample
import re
from services.database_service import get_favorite_songs_info, get_candidate_songs, get_songs_by_artists
from services.ai_service import _analyze_user_preference, _ai_recommend_songs, _make_tagline
from utils.helpers import _get_title_artist

PRIMARY_GENRES = {"J-pop","팝","록","발라드","힙합","인디 팝","일렉트로 팝"}
MOOD_MAP = {"에너지":"신나는","강렬":"강렬","감성적":"서정적","잔잔":"잔잔"}
_PAREN_RE = re.compile(r"\s*[\(\[（【].*?[\)\]）】]\s*")

def _normalize_genre(g: str) -> tuple[str, list[str]]:
    if not g: return "", []
    parts = [p.strip() for p in g.split(",") if p.strip()]
    primary = next((p for p in parts if p in PRIMARY_GENRES), parts[0] if parts else "")
    return primary, parts

def _normalize_mood(m: str) -> str:
    return MOOD_MAP.get(m, m or "")

def _norm(s: str) -> str:
    if not s: return ""
    s = s.lower().strip()
    s = _PAREN_RE.sub(" ", s)
    s = re.sub(r"[^0-9a-z가-힣ぁ-ゔァ-ヴー一-龥\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _soft_match(a: str, b: str) -> bool:
    a, b = _norm(a), _norm(b)
    if not a or not b: return False
    return a == b or a in b or b in a or a.startswith(b) or b.startswith(a)

def _match_ai_recommendations_with_db(ai_recs: list[dict], candidate_songs: list[dict]) -> list[dict]:
    """AI 추천 결과와 DB의 실제 노래 정보를 매칭 (완전/유사 일치)"""
    matched_songs = []
    used_ids = set()

    for ai_rec in ai_recs:
        ai_title = ai_rec.get("title", "").strip() or ai_rec.get("title_kr", "").strip()
        ai_artist = ai_rec.get("artist_kr", "").strip()
        found = None

        for db_song in candidate_songs:
            if db_song.get("song_id") in used_ids: 
                continue
            db_titles = [
                db_song.get("title_kr", "").strip(),
                db_song.get("title_en", "").strip(),
                db_song.get("title_jp", "").strip(),
                db_song.get("title_yomi", "").strip()
            ]
            db_artists = [
                db_song.get("artist_kr", "").strip(),
                db_song.get("artist", "").strip()
            ]
            
            if ai_title in db_titles and ai_artist in db_artists:
                found = db_song
                break
                
        if not found:
            for db_song in candidate_songs:
                if db_song.get("song_id") in used_ids: 
                    continue
                title_match = any(_soft_match(ai_title, db_title) for db_title in [
                    db_song.get("title_kr", ""),
                    db_song.get("title_en", ""),
                    db_song.get("title_jp", ""),
                    db_song.get("title_yomi", "")
                ])
                artist_match = any(_soft_match(ai_artist, db_artist) for db_artist in [
                    db_song.get("artist_kr", ""),
                    db_song.get("artist", "")
                ])
                
                if title_match and artist_match:
                    found = db_song
                    break

        if found:
            used_ids.add(found.get("song_id"))
            matched_song = found.copy()
            matched_song["mood"] = ai_rec.get("mood", found.get("mood", ""))
            matched_song["genre"] = ai_rec.get("genre", found.get("genre", ""))
            matched_song["reason"] = ai_rec.get("reason", "")
            matched_songs.append(matched_song)

    if len(matched_songs) < len(ai_recs):
        need = len(ai_recs) - len(matched_songs)
        leftovers = [c for c in candidate_songs if c.get("song_id") not in used_ids]
        leftovers.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        matched_songs.extend(leftovers[:need])

    return matched_songs

def _group_songs_dynamic(recs: list[dict], total_groups: int = 4, max_per_group: int = 6) -> dict[str, list[dict]]:
    """분위기/장르 분포를 보고 동적 그룹 구성"""
    mood_groups = defaultdict(list)
    genre_groups = defaultdict(list)

    for song in recs:
        if song.get("mood"):  mood_groups[song["mood"]].append(song)
        if song.get("genre"): genre_groups[song["genre"]].append(song)

    top_moods = sorted(mood_groups.items(), key=lambda x: len(x[1]), reverse=True)
    top_genres = sorted(genre_groups.items(), key=lambda x: len(x[1]), reverse=True)

    final_groups, used_ids = {}, set()
    mood_total = sum(len(v) for _, v in top_moods)
    genre_total = sum(len(v) for _, v in top_genres)
    if mood_total + genre_total == 0:
        return final_groups
    mood_share = max(1, min(total_groups-1, round(total_groups * (mood_total / (mood_total+genre_total or 1)))))
    genre_share = total_groups - mood_share

    for mood, songs in top_moods[:mood_share]:
        avail = [s for s in songs if s.get("song_id") not in used_ids]
        if avail:
            chosen = avail[:max_per_group]
            final_groups[mood] = chosen
            used_ids.update(s.get("song_id") for s in chosen if s.get("song_id") is not None)

    for genre, songs in top_genres[:genre_share]:
        avail = [s for s in songs if s.get("song_id") not in used_ids]
        if avail:
            chosen = avail[:max_per_group]
            final_groups[genre] = chosen
            used_ids.update(s.get("song_id") for s in chosen if s.get("song_id") is not None)

    while len(final_groups) < total_groups:
        remain = [s for s in recs if s.get("song_id") not in used_ids]
        if not remain: break
        label = f"추천 #{len(final_groups)+1}"
        chosen = remain[:max_per_group]
        final_groups[label] = chosen
        used_ids.update(s.get("song_id") for s in chosen if s.get("song_id") is not None)
    return final_groups

def _merge_small_groups(grouped: dict[str, list[dict]], min_size: int = 3) -> dict[str, list[dict]]:
    if not grouped: return grouped
    big = {k:v for k,v in grouped.items() if len(v) >= min_size}
    small = {k:v for k,v in grouped.items() if len(v) <  min_size}
    if not small: return grouped
    def _sim(a,b):
        a,b=a.lower(),b.lower()
        return 2 if a==b else (1 if (a in b or b in a) else 0)
    for k, songs in small.items():
        best, best_s = None, -1
        for kk in big.keys():
            s = _sim(k, kk)
            if s > best_s:
                best, best_s = kk, s
        if best is None and big:
            best = next(iter(big.keys()))
        if best:
            big[best] = (big.get(best, []) + songs)[:6]
        else:
            big[k] = songs
    return big

def _dedupe_groups(grouped: dict[str, list[dict]]) -> dict[str, list[dict]]:
    seen = set()
    for label, songs in grouped.items():
        uniq = []
        for s in songs:
            sid = s.get("song_id") or (s.get("title_kr"), s.get("artist_kr"))
            if sid in seen:
                continue
            seen.add(sid)
            uniq.append(s)
        grouped[label] = uniq
    return grouped

def _autogen_reason(song: dict) -> str:
    reasons = []
    mc = song.get("matched_criteria", [])
    if "like_artist" in mc: reasons.append("좋아한 아티스트와 동일")
    if "preferred_genre" in mc or "like_genre" in mc: reasons.append(f"{song.get('genre','')} 장르 선호와 일치")
    if "preferred_mood" in mc: reasons.append(f"{song.get('mood','')} 무드와 잘 맞음")
    if not reasons and song.get("match_score",0) > 0: reasons.append("취향 요소와 부분 일치")
    return " · ".join(reasons) or "분위기와 조화로운 곡"

def _build_grouped_payload(recs: list[dict], favorite_song_ids: list[int] = None, user_preference: dict = None) -> list[dict]:
    """그룹화된 추천곡 payload 생성 (동적+병합+중복 제거)"""
    grouped = _group_songs_dynamic(recs)
    grouped = _merge_small_groups(grouped, min_size=3)
    grouped = _dedupe_groups(grouped)
    payload = []

    favorite_song_ids = favorite_song_ids or []

    for label, songs in grouped.items():
        norm_songs = []
        for s in songs:
            if s.get("song_id") in favorite_song_ids:
                continue
            title_jp, title_kr, title_en, title_yomi, artist, artist_kr = _get_title_artist(s)
            norm_songs.append({
                "title_jp": title_jp,
                "title_kr": title_kr,
                "title_en": title_en,
                "title_yomi": title_yomi,
                "artist": artist,
                "artist_kr": artist_kr,
                "tj_number": s.get("tj_number"),
                "ky_number": s.get("ky_number"),
            })
        if norm_songs:
            tagline = _make_tagline(label, norm_songs, user_preference)
            payload.append({
                "label": label,
                "songs": norm_songs,
                "tagline": tagline
            })
    return payload

def _normalize_candidates_for_cache(candidates: list[dict]) -> list[dict]:
    normalized = []
    for s in candidates:
        title_jp, title_kr, title_en, title_yomi, artist, artist_kr = _get_title_artist(s)
        normalized.append({
            "song_id": s.get("song_id"),
            "title_jp": title_jp,
            "title_kr": title_kr,
            "title_en": title_en,
            "title_yomi": title_yomi,
            "artist": artist,
            "artist_kr": artist_kr,
            "genre": s.get("genre"),
            "mood": s.get("mood"),
            "tj_number": s.get("tj_number"),
            "ky_number": s.get("ky_number"),
            "recommendation_type": s.get("recommendation_type"),
            "matched_criteria": s.get("matched_criteria", []),
            "match_score": s.get("match_score", 0),
            "reason": s.get("reason", "")
        })
    return normalized

def recommend_songs(favorite_song_ids: list[int], cached_preference: dict = None) -> dict:
    """메인 추천 함수"""
    if not favorite_song_ids:
        candidate_songs = get_candidate_songs([], limit=100)
        for s in candidate_songs:
            pg, subs = _normalize_genre(s.get("genre",""))
            s["genre"] = pg
            s["sub_genres"] = subs
            s["mood"] = _normalize_mood(s.get("mood",""))
            if not s.get("reason"): s["reason"] = _autogen_reason(s)
        recommended = sample(candidate_songs, min(20, len(candidate_songs)))
        groups_payload = _build_grouped_payload(recommended, [])
        return {
            "groups": groups_payload,
            "candidates": _normalize_candidates_for_cache(candidate_songs)
        }

    favorite_songs = get_favorite_songs_info(favorite_song_ids)
    user_preference = cached_preference or _analyze_user_preference(favorite_songs)

    candidate_songs = get_candidate_songs(
        favorite_song_ids,
        limit=100,
        preferred_genres=user_preference.get("preferred_genres") if user_preference else None,
        preferred_moods=user_preference.get("preferred_moods") if user_preference else None
    )
    if not candidate_songs:
        return {"error": "추천할 노래를 찾지 못했습니다."}

    for s in candidate_songs:
        pg, subs = _normalize_genre(s.get("genre",""))
        s["genre"] = pg
        s["sub_genres"] = subs
        s["mood"] = _normalize_mood(s.get("mood",""))
        if not s.get("reason"): s["reason"] = _autogen_reason(s)

    ai_recommended = _ai_recommend_songs(candidate_songs, user_preference, target_count=20)
    if ai_recommended:
        ai_recommended = _match_ai_recommendations_with_db(ai_recommended, candidate_songs)
    else:
        candidate_songs.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        ai_recommended = candidate_songs[:20]

    groups_payload = _build_grouped_payload(ai_recommended, favorite_song_ids, user_preference)
    
    if user_preference:
        artist_groups = _build_artist_based_groups(
            user_preference, 
            exclude_song_ids=favorite_song_ids,
            per_artist=5,
            max_artists=2
        )
        for label, group_data in artist_groups.items():
            groups_payload.append({
                "label": label,
                "songs": group_data["songs"],
                "tagline": group_data["tagline"]
            })

    return {
        "groups": groups_payload,
        "candidates": _normalize_candidates_for_cache(candidate_songs),
        "preference": user_preference,
        "favorite_song_ids": favorite_song_ids or []
    }

def _build_artist_based_groups(user_preference: dict, exclude_song_ids: list[int], per_artist:int = 5, max_artists:int = 2) -> dict[str, list[dict]]:
    """
    취향분석 결과의 favorite_artists에서 상위 1~2명 선별 → 각 가수의 대표곡 모음 그룹 생성
    exclude_song_ids: 이미 선택/좋아요 등으로 제외할 곡 ID
    반환 형식: { "아티스트명 추천": [ {...song...}, ... ], ... }
    """
    if not user_preference:
        return {}

    fav_artists = user_preference.get("favorite_artists") or []
    if not fav_artists:
        return {}

    target_artists = [a for a in fav_artists if a][:max_artists]
    if not target_artists:
        return {}

    by_artist = get_songs_by_artists(target_artists, limit_per_artist=per_artist, exclude_song_ids=exclude_song_ids)
    groups: dict[str, list[dict]] = {}

    for artist in target_artists:
        songs = by_artist.get(artist) or []
        if not songs:
            continue

        label = f"{artist} 추천"
        samples = songs[:3]
        try:
            tagline = _make_tagline(artist, samples, user_preference)
        except Exception:
            tagline = f"{artist} 인기곡 추천 🎤"

        normalized_songs = []
        for s in songs:
            title_jp, title_kr, title_en, title_yomi, artist, artist_kr = _get_title_artist(s)
            normalized_songs.append({
                "title_kr": title_kr,
                "title_en": title_en,
                "title_jp": title_jp,
                "title_yomi": title_yomi,
                "artist": artist,
                "artist_kr": artist_kr,
                "genre": s.get("genre") or "",
                "mood": s.get("mood") or "",
                "tj_number": s.get("tj_number"),
                "ky_number": s.get("ky_number")
            })
        
        groups[label] = {
            "songs": normalized_songs,
            "tagline": tagline
        }

    return groups
