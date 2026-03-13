from openai import OpenAI

from .config import MODEL, OPENAI_API_KEY, SEED, TEMPERATURE
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from .schema import IntakeClassification

_client = OpenAI(api_key=OPENAI_API_KEY)


def classify(source: str, message: str) -> IntakeClassification:
    """Call OpenAI with Structured Outputs to classify a customer message."""
    user_content = USER_PROMPT_TEMPLATE.format(source=source, message=message)

    completion = _client.beta.chat.completions.parse(
        model=MODEL,
        temperature=TEMPERATURE,
        seed=SEED,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        response_format=IntakeClassification,
    )

    choice = completion.choices[0]

    if choice.finish_reason == "length":
        raise ValueError(
            "Response truncated (finish_reason='length'). "
            "Increase max_tokens or simplify the schema."
        )

    result = choice.message

    if result.refusal:
        raise ValueError(f"Model refused to classify: {result.refusal}")

    if result.parsed is None:
        raise ValueError("Model returned empty parsed output")

    return result.parsed
