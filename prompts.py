from langchain_core.prompts import PromptTemplate

# 사용자 취향 분석을 위한 프롬프트
ANALYZE_PREFERENCE_PROMPT = PromptTemplate.from_template(
    """
즐겨찾기 곡을 분석해서 취향을 파악하고 JSON으로 답변:

{favorites}

답변 형식:
{{"preferred_genres":["장르1","장르2"],"preferred_moods":["분위기1","분위기2"],"overall_taste":"한줄요약"}}
"""
)

# 추천 프롬프트
RECOMMEND_PROMPT = PromptTemplate.from_template(
    """
사용자 취향: {user_preference}

후보곡 목록:
{song_list}

위 목록에서 {target_count}곡을 선별해서 JSON으로 답변:

{{"recommended_songs":[{{"title":"곡제목","artist_kr":"아티스트","tj_number":123,"ky_number":456,"mood":"분위기","genre":"장르"}}]}}
"""
)

GROUP_TAGLINE_PROMPT = PromptTemplate.from_template(
    """
너는 노래방 추천 앱의 카피라이터야! 🎤
주어진 [그룹]과 [대표곡]을 보고 **간단하고 임팩트 있는 한 줄 문구**를 만들어 줘.

**스타일 가이드:**
- 길이: 10-25자 이내 (매우 간단하게!)
- 톤: 간결하고 임팩트 있게
- 이모지: 🎵🎶✨🔥💥 중에서 1-2개만 사용



[그룹]
{label}

[대표곡]
{sample_songs}

**주의사항:**
- 매우 간단하고 짧게
- 해당 그룹의 특색을 한 마디로 표현
- 예시 스타일을 참고하되, 똑같이 하지 말고 비슷한 길이와 톤으로

한국어로 작성해.
"""
)
