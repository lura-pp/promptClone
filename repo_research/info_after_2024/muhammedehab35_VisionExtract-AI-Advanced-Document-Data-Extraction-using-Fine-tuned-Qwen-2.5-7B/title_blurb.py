# ruff: noqa: E501

from google import genai
from google.genai.types import GenerateContentConfig

PROMPT = """Tu es un assistant de rédaction pour un journal local français.

Ta tâche est de générer un **titre** et un **chapeau** (blurb) à partir du **premier paragraphe uniquement**.

Règles :

1. Titre :
   - Court, clair et journalistique (max. 12 mots).
   - Inclure le lieu si mentionné dans le paragraphe.
   - Inclure la date si mentionnée dans le paragraphe.
   - Doit annoncer le fait principal.

2. Chapeau :
   - Résume quoi, qui, où, quand.
   - Mentionner la date et le lieu s'ils sont dans le paragraphe.
   - Max. 30 mots, ton neutre.

Utilise uniquement le contenu du paragraphe fourni, sans rien ajouter.

Format de réponse :
Titre : [titre généré]
Chapeau : [chapeau généré]
"""


def gen_title_and_blurb_gemini(
    paragraph: str, client: genai.Client, model: str = "gemini-2.0-flash"
) -> tuple[str, int | None, int | None]:
    response = client.models.generate_content(
        model=model,
        contents=paragraph,
        config=GenerateContentConfig(system_instruction=PROMPT),
    )
    res_text = response.text
    if res_text is None:
        raise ValueError("Response text is None")
    content = res_text.strip()

    usage_metadata = response.usage_metadata
    if usage_metadata is None:
        raise ValueError("Usage metadata is None")
    prompt_tokens = usage_metadata.prompt_token_count
    completion_tokens = usage_metadata.candidates_token_count

    return content, prompt_tokens, completion_tokens


def gen_title_and_blurb_gemma(
    paragraph: str, client: genai.Client, model: str = "gemma-3-27b-it"
) -> tuple[str, int | None, int | None]:
    response = client.models.generate_content(
        model=model, contents=f"{PROMPT}\n\n{paragraph}"
    )
    res_text = response.text
    if res_text is None:
        raise ValueError("Response text is None")
    content = res_text.strip()

    usage_metadata = response.usage_metadata
    if usage_metadata is None:
        raise ValueError("Usage metadata is None")
    prompt_tokens = usage_metadata.prompt_token_count
    completion_tokens = usage_metadata.candidates_token_count

    return content, prompt_tokens, completion_tokens
