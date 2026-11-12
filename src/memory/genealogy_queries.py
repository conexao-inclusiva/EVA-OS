"""Consultas genealogicas deterministicas sobre relacoes confirmadas."""

import re
import unicodedata


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(
        char for char in value
        if not unicodedata.combining(char)
    )


def answer_parent(question, speaker_id, family):
    """Consulta parentesco confirmado por identificador de pessoa."""
    question = normalize(question).strip(" ?!.")
    speaker_id = str(speaker_id).strip().casefold()

    relation = None
    subject_id = None

    own_match = re.fullmatch(
        r"(?:quem e|qual e o nome d[oa]) "
        r"(meu pai|minha mae)",
        question,
    )

    if own_match:
        relation = "pai" if own_match.group(1) == "meu pai" else "mae"
        subject_id = speaker_id
    else:
        other_match = re.fullmatch(
            r"(?:quem e|qual e o nome d[oa]) "
            r"(?:o |a )?(pai|mae) (?:do|da) ([a-z0-9_]+)",
            question,
        )

        if other_match:
            relation = other_match.group(1)
            subject_id = other_match.group(2)

    if not relation or not subject_id:
        return None

    # Nunca deduz a identidade a partir de um nome semelhante.
    person = family.get_person(subject_id)
    if person is None:
        return None

    rows = family.relations(
        subject_id,
        relation,
        confirmed_only=True,
    )

    if len(rows) != 1:
        return None

    parent = rows[0].get("object_name")
    if not isinstance(parent, str) or not parent.strip():
        return None

    if relation == "pai":
        return "O pai registrado e " + parent + "."

    return "A mae registrada e " + parent + "."
