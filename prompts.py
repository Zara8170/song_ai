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
너는 노래방 추천 어플의 추천 설명 문구를 쓰는 도우미야.
- 주어진 [그룹]의 특징과 [대표곡]을 참고해 **한 줄**(50자 이내)로 임팩트 있게 써 줘.
- 말투: 밝고 간결 • 불필요한 수식 X
- 허용 이모지: 🎤✨🔥 중 0~1개

[그룹]
{label}

[대표곡]
{sample_songs}

한국어로 작성해.
"""
)
