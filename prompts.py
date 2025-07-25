from langchain_core.prompts import PromptTemplate

RECOMMEND_PROMPT = PromptTemplate.from_template(
    """
아래는 사용자의 즐겨찾기 곡 목록입니다:
{favorites}

아래는 추천 후보 곡 목록입니다:
{song_list}

위 후보 목록에서 사용자의 취향에 가장 적합한 5곡을 골라 JSON 형식으로
반환하세요.

**반드시 위 후보 목록(데이터베이스) 안에 있는 곡만 추천하세요.**

JSON 형식(불필요한 텍스트 금지):

{{
  "recommended_songs": [
    {{
      "title": "...",
      "artist": "...",
      "tj_number": "...",
      "ky_number": "..."
    }}
  ]
}}

배열에는 정확히 5곡만 포함해야 합니다.
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

**그룹별 스타일 예시:**
- 감성적: "감성 한 스푼, 마음 한 스푼 🎶✨"
- 에너지: "에너지 폭발! 💥 치유의 노래"
- 강렬: "심장을 두드리는 강렬함! 🔥"

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
