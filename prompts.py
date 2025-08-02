from langchain_core.prompts import PromptTemplate

# 사용자 취향 분석을 위한 프롬프트
ANALYZE_PREFERENCE_PROMPT = PromptTemplate.from_template(
    """즐겨찾기: {favorites}
JSON: {{"preferred_genres":[],"preferred_moods":[],"overall_taste":""}}
"""
)

# 추천 프롬프트
RECOMMEND_PROMPT = PromptTemplate.from_template(
    """취향: {user_preference}
곡목록: {song_list}
{target_count}곡 선별 JSON: {{"recommended_songs":[{{"title":"","artist_kr":"","tj_number":0,"ky_number":0,"mood":"","genre":""}}]}}
"""
)

GROUP_TAGLINE_PROMPT = PromptTemplate.from_template(
    """{label} 그룹의 10-25자 태그라인 생성. 대표곡: {sample_songs}. 이모지 1-2개 포함, 간결하게."""
)
