# ruff: noqa: E501
import random
import secrets

import spacy
import streamlit as st
from google import genai
from google.genai import types

from utils.io import TransitionExample


@st.cache_resource
def load_language_model() -> spacy.language.Language:
    return spacy.load("fr_core_news_sm")


# Shared closing transitions
_CLOSING_TRANSITIONS = [
    "Enfin",
    "Et pour finir",
    "Pour terminer",
    "Pour finir",
    "En guise de conclusion",
    "En conclusion",
    "En guise de mot de la fin",
    "Pour clore cette revue",
    "Pour conclure cette sélection",
    "Dernier point à noter",
    "Pour refermer ce tour d'horizon",
]


def _is_valid_closing_transition(text: str) -> bool:
    return any(
        text.strip().lower().startswith(valid.lower()) for valid in _CLOSING_TRANSITIONS
    )


def _get_transition_keywords(transition: str) -> list[str]:
    nlp = load_language_model()
    doc = nlp(transition)
    keywords = [
        token.lemma_
        for token in doc
        if (token.pos_ in {"NOUN", "ADJ", "ADV", "VERB"})
        or (token.pos_ == "ADP" and token.lemma_ == "dans")
    ]
    return list(set(keywords))  # Remove duplicates


def _build_base_prompt(
    *,
    is_last: bool,
    spent_keywords: set[str],
) -> str:
    base_prompt = (
        "Tu es un assistant de presse francophone.\n"
        "Ta tâche est d'insérer une transition brève et naturelle (5 mots maximum)\n"
        "entre deux paragraphes d'actualité régionale.\n"
        "La transition doit être journalistique, fluide, neutre et ne pas répéter les débuts comme 'Par ailleurs', 'Parallèlement', ou 'Sujet'.\n"
        "Si tu veux utiliser 'Par ailleurs', préfère des variantes enrichies comme : 'Par ailleurs, on annonce que', ou 'Par ailleurs, sachez que'.\n"
        "Évite complètement l'usage de 'En parallèle'.\n"
    )

    if is_last:
        base_prompt += (
            "Cette transition est la toute dernière de l'article. "
            "Tu dois obligatoirement choisir une transition de fin dans cette liste :\n"
            f"[{', '.join(_CLOSING_TRANSITIONS)}]. "
        )
    else:
        if spent_keywords:
            base_prompt += f"Il est strictement interdit d'inclure les mots suivants dans les transitions générées : [{', '.join(spent_keywords)}].\n"
        base_prompt += (
            "Cette transition n'est pas la dernière. "
            f"N'utilise aucune des transitions suivantes : [{', '.join(_CLOSING_TRANSITIONS)}]. "
        )

    return base_prompt


def _select_examples(
    examples: list[TransitionExample], max_examples: int, spent_keywords: set[str]
) -> list[TransitionExample]:
    filtered_examples = [
        ex
        for ex in examples
        if not any(keyword in spent_keywords for keyword in ex.keywords)
    ]
    return random.sample(filtered_examples, min(max_examples, len(filtered_examples)))


def gen_transition_gemini(  # noqa: PLR0913
    *,
    para_a: str,
    para_b: str,
    examples: list[TransitionExample],
    client: genai.Client,
    is_last: bool = False,
    model: str = "gemini-2.0-flash",
    max_examples: int = 100,
    spent_keywords: set[str],
) -> tuple[str, list[str], int | None, int | None]:
    selected_examples = _select_examples(examples, max_examples, spent_keywords)
    base_prompt = _build_base_prompt(is_last=is_last, spent_keywords=spent_keywords)
    prompt = ""
    for ex in selected_examples:
        prompt += "<EXAMPLE>\n"
        ex_input = ex.input.split("\n")
        ex_input = "\nTRANSITION\n".join(ex_input)
        prompt += f"INPUT: {ex_input}\nOUTPUT: {ex.output}\n"
        prompt += "</EXAMPLE>\n\n"
    prompt += f"{para_a.strip()}\nTRANSITION\n{para_b.strip()}"
    max_attempts = 5
    for attempt in range(max_attempts):
        last_attempt = attempt == max_attempts - 1
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=base_prompt,
            ),
        )
        res_text = response.text
        if res_text is None:
            raise ValueError("Response text is None")
        transition = res_text.strip()

        # TODO: check if transition has [XXX] and replace it with relevant info  # noqa: FIX002, TD002, TD003

        usage_metadata = response.usage_metadata
        if usage_metadata is None:
            raise ValueError("Usage metadata is None")

        prompt_tokens = usage_metadata.prompt_token_count
        completion_tokens = usage_metadata.candidates_token_count

        transition_keywords = _get_transition_keywords(transition)
        spent_transition = any(
            keyword in spent_keywords for keyword in transition_keywords
        )
        if (
            (not is_last and last_attempt)
            or (not is_last and not spent_transition)
            or _is_valid_closing_transition(transition)
        ):
            return transition, transition_keywords, prompt_tokens, completion_tokens
    transition = secrets.choice(_CLOSING_TRANSITIONS) + ","
    transition_keywords = _get_transition_keywords(transition)
    return transition, transition_keywords, 0, 0


def gen_transition_tgemini(  # noqa: PLR0913
    *,
    para_a: str,
    para_b: str,
    client: genai.Client,
    is_last: bool = False,
    model: str,
    spent_keywords: set[str],
) -> tuple[str, list[str], int | None, int | None]:
    print(f"Spent keywords: {spent_keywords}")
    base_prompt = _build_base_prompt(is_last=is_last, spent_keywords=spent_keywords)
    prompt = ""
    prompt += f"{para_a.strip()}\nTRANSITION\n{para_b.strip()}"
    max_attempts = 5
    for attempt in range(max_attempts):
        last_attempt = attempt == max_attempts - 1
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=base_prompt,
                thinking_config=types.ThinkingConfig(
                    thinking_budget=0,
                ),
                temperature=1,
                top_p=1,
                # seed=0,
                # max_output_tokens=65535,
            ),
        )
        res_text = response.text
        if res_text is None:
            raise ValueError("Response text is None")
        transition = res_text.strip()

        # TODO: check if transition has [XXX] and replace it with relevant info  # noqa: FIX002, TD002, TD003

        usage_metadata = response.usage_metadata
        if usage_metadata is None:
            raise ValueError("Usage metadata is None")

        prompt_tokens = usage_metadata.prompt_token_count
        completion_tokens = usage_metadata.candidates_token_count

        transition_keywords = _get_transition_keywords(transition)
        spent_transition = any(
            keyword in spent_keywords for keyword in transition_keywords
        )
        if (
            (not is_last and last_attempt)
            or (not is_last and not spent_transition)
            or _is_valid_closing_transition(transition)
        ):
            return transition, transition_keywords, prompt_tokens, completion_tokens
    transition = secrets.choice(_CLOSING_TRANSITIONS) + ","
    transition_keywords = _get_transition_keywords(transition)
    return transition, transition_keywords, 0, 0


def gen_transition_gemma(  # noqa: PLR0913
    *,
    para_a: str,
    para_b: str,
    examples: list[TransitionExample],
    client: genai.Client,
    is_last: bool = False,
    model: str = "gemma-3-27b-it",
    max_examples: int = 100,
    spent_keywords: set[str],
) -> tuple[str, list[str], int | None, int | None]:
    selected_examples = _select_examples(examples, max_examples, spent_keywords)
    base_prompt = _build_base_prompt(
        is_last=is_last,
        spent_keywords=spent_keywords,
    )
    prompt = base_prompt + "\n\n"
    for ex in selected_examples:
        prompt += "<EXAMPLE>\n"
        ex_input = ex.input.split("\n")
        ex_input = "\nTRANSITION\n".join(ex_input)
        prompt += f"INPUT: {ex_input}\nOUTPUT: {ex.output}\n"
        prompt += "</EXAMPLE>\n\n"
    prompt += f"{para_a.strip()}\nTRANSITION\n{para_b.strip()}"
    max_attempts = 5
    for attempt in range(max_attempts):
        last_attempt = attempt == max_attempts - 1
        response = client.models.generate_content(model=model, contents=prompt)
        res_text = response.text
        if res_text is None:
            raise ValueError("Response text is None")
        transition = res_text.strip()

        usage_metadata = response.usage_metadata
        if usage_metadata is None:
            raise ValueError("Usage metadata is None")
        prompt_tokens = usage_metadata.prompt_token_count
        completion_tokens = usage_metadata.candidates_token_count

        transition_keywords = _get_transition_keywords(transition)
        spent_transition = any(
            keyword in spent_keywords for keyword in transition_keywords
        )
        if (
            (not is_last and last_attempt)
            or (not is_last and not spent_transition)
            or _is_valid_closing_transition(transition)
        ):
            return transition, transition_keywords, prompt_tokens, completion_tokens
    transition = secrets.choice(_CLOSING_TRANSITIONS) + ","
    transition_keywords = _get_transition_keywords(transition)
    return transition, transition_keywords, 0, 0
