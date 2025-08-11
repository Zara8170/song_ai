from langchain_core.prompts import PromptTemplate

# 사용자 취향 분석 프롬프트
ANALYZE_PREFERENCE_PROMPT = PromptTemplate.from_template(
    """당신은 음악 큐레이션을 위한 분석가입니다.
사용자의 즐겨찾기 목록을 기반으로 취향을 구조화된 JSON으로만 출력하세요.

제약:
- 반드시 JSON만 출력. 문자열 설명이나 마크다운 금지.
- genre/mood는 제공된 후보들에서 가능한 값으로 제한하는 것을 우선 고려.

입력 즐겨찾기:
{favorites}

아웃풋 스키마:
{{
  "preferred_genres": ["string"],
  "preferred_moods": ["string"],
  "overall_taste": "string",
  "favorite_artists": ["string"]
}}
"""
)

# 추천 프롬프트
RECOMMEND_PROMPT = PromptTemplate.from_template(
    """역할: 당신은 주어진 후보 곡들 중에서 사용자에게 맞는 곡을 골라주는 추천 엔진입니다.

제약:
- 오직 제공된 곡목록에서만 선택하세요. 새로운 곡 생성 금지.
- 반드시 JSON만 출력. 문자열 설명/마크다운 금지.
- genre/mood는 아래 허용 목록만 사용.
- title, artist_kr는 곡목록과 동일한 표기를 그대로 사용.

취향 요약:
{user_preference}

허용 장르: {allowed_genres}
허용 분위기: {allowed_moods}

곡목록:
{song_list}

다음 수를 정확히 선별: {target_count}
아웃풋 스키마:
{{
  "recommended_songs": [
    {{"title": "string", "artist_kr": "string", "tj_number": 0, "ky_number": 0, "mood": "string", "genre": "string"}}
  ]
}}
"""
)

GROUP_TAGLINE_PROMPT = PromptTemplate.from_template(
    """
{label} 그룹의 특성을 10~25자 한 줄 태그라인으로 생성.
대표곡: {sample_songs}.
제약:
- 아래 문구 금지: "감성을 자극", "강렬한 멜로디"
- 이전 문구와 중복 회피, 어휘 다양화
- 동사/장면 묘사 1개 포함(예: 스며들다/튀어오르다/달리다/번지다 등)
- 이모지 1~2개

출력: 따옴표 없이 문장 1개만.
"""
)
