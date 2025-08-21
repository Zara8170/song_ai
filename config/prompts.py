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

참고사항:
- favorite_artists는 사용자가 좋아하는 아티스트들의 이름을 정확히 추출하여 배열로 반환
- 아티스트 이름은 한글명(artist_kr) 또는 원어명(artist) 중 더 정확한 것을 선택
- 최대 5명의 아티스트까지 추출하되, 빈도가 높은 순으로 정렬
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
당신은 노래방 추천 앱의 카피라이터입니다.
{label} 그룹의 특성을 기반으로, 노래방에서 이 분위기의 곡을 부를 때 어울리는 한 줄 태그라인을 만드세요.

대표곡 예시: {sample_songs}

제약:
- 문학적/추상적 표현(예: "감성을 자극", "강렬한 멜로디") 금지
- 노래방 상황에 맞는 실용적이고 직관적인 문구로 작성
- 장르/분위기를 직접 강조 (예: 발라드, 댄스, 록 등)
- "이럴 때 부르면 좋은 노래!" 같은 톤을 사용할 것
- 이모지 🎤🎶🤘🕺 등은 1개 사용 가능
- 출력은 15자 이내, 1줄, 따옴표 없이

아티스트 기반 추천의 경우:
- 해당 아티스트의 특징적인 음악 스타일을 강조
- "OO의 대표곡 모음" 형태보다는 구체적인 특성 언급
- 예: "감성적인 김범수 발라드 🎶", "신나는 BTS 히트곡 🎤"

출력 예시:
- 친구랑 떼창하기 좋은 신나는 록 🎤
- 감성 터지는 발라드 추천 🎶
- 분위기 띄우는 댄스곡 🕺
- 조용히 부르기 좋은 어쿠스틱 🎸
- 감성적인 김범수 발라드 🎶
- 신나는 BTS 히트곡 🎤
"""
)
