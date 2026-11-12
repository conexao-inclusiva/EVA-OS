# -*- coding: utf-8 -*-
"""Deterministic queries for the shared EVA family graph."""

import re
import unicodedata
from contextlib import closing

from src.memory.shared_family import SharedFamily


def normalize(value):
    value = unicodedata.normalize("NFKD", str(value).casefold())
    return "".join(c for c in value if not unicodedata.combining(c))


def family_answer(text, speaker, family):
    question = normalize(text).strip(" ?!.")
    speaker = normalize(speaker).strip()

    if speaker not in {"alberto", "juliana", "nicolas", "liris"}:
        return None

    names = {
        "alberto": "Alberto",
        "juliana": "Juliana",
        "nicolas": "Nicolas",
        "liris": "Liris",
    }

    def children(parent, gender=None):
        result = []
        with closing(family._connect()) as db:
            rows = db.execute(
                """
                SELECT p.person_id, p.display_name, r.relation
                FROM family_shared_relations r
                JOIN family_people p ON p.person_id=r.subject_id
                WHERE r.object_id=?
                  AND r.relation IN ('pai', 'mae')
                  AND r.confirmed=1
                  AND r.valid_to IS NULL
                ORDER BY r.id
                """,
                (parent,)
            ).fetchall()

        for row in rows:
            person_id = row["person_id"]
            if gender is not None:
                continue
            if row["display_name"] not in result:
                result.append(row["display_name"])
        return result

    def parent(child, relation):
        rows = family.relations(child, relation)
        if len(rows) == 1:
            return rows[0]["object_name"]
        return None

    match = re.fullmatch(
        r"quem (?:e|sao) (?:o |a |os |as )?"
        r"(pai|mae|pais) (?:do|da) (nicolas|nick|liris)",
        question
    )

    if match:
        relation, child = match.groups()
        child = "nicolas" if child == "nick" else child
        if relation == "pais":
            father = parent(child, "pai")
            mother = parent(child, "mae")
            found = [name for name in (father, mother) if name]
            if father and mother:
                return "Os pais de " + names[child] + " sao " + father + " e " + mother + "."
            if father:
                return "Sei que o pai de " + names[child] + " e " + father + ", mas ainda nao sei quem e a mae."
            if mother:
                return "Sei que a mae de " + names[child] + " e " + mother + ", mas ainda nao sei quem e o pai."
        else:
            name = parent(child, relation)
            if name:
                if relation == "pai":
                    return "O pai de " + names[child] + " e " + name + "."
                return "A mae de " + names[child] + " e " + name + "."
        if relation == "pai":
            return "Ainda nao sei quem e o pai de " + names[child] + ". Voce pode me contar?"
        if relation == "mae":
            return "Ainda nao sei quem e a mae de " + names[child] + ". Voce pode me contar?"
        return "Ainda nao sei quem sao os pais de " + names[child] + "."

    match = re.fullmatch(
        r"quem (?:e|sao) (?:o |a |os |as )?"
        r"meu(?:s)? (filho|filhos|filha|filhas)",
        question
    )

    if match:
        requested = match.group(1)
        if requested in ("filha", "filhas"):
            return None

        found = children(speaker)

        if not found:
            return "Ainda nao tenho essa relacao familiar confirmada."

        if len(found) == 1:
            return "E o " + found[0] + "."

        return "Seus filhos sao " + " e ".join(found) + "."

    if re.fullmatch(r"quem e (?:a )?minha esposa", question):
        rows = family.relations(speaker, "conjuge")
        if len(rows) == 1:
            return "Sua esposa e a " + rows[0]["object_name"] + "."
        return "Ainda nao tenho essa relacao familiar confirmada."

    return None
