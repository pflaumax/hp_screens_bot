"""Turn a Potter DB item into one short, plain sentence.

House style for these facts, per the bot's voice:
  * no emoji
  * no hashtags (``bluesky_client`` owns the single #HarryPotter tag)
  * one sentence, short enough to sit above the movie title
  * no hedging — a disputed wiki value is skipped, not asserted

Every formatter returns ``None`` when the item has nothing worth saying,
which tells :mod:`bot.fact_fetcher` to move on to the next candidate.
"""

import random
import re
from datetime import date

# Potter DB fields are free text from a wiki. Anything longer than this
# is a paragraph, not a fact.
MAX_FIELD_LENGTH = 160

# Potter DB puts a pronunciation guide inside the incantation field,
# e.g. "Alarte Ascendare(a-LAR-tay a-SEN-der-ay)".
_PRONUNCIATION = re.compile(r"\s*\([^)]*\)\s*$")

# Any parenthetical aside, wherever it sits: "Dragon (formerly)".
_PARENTHETICAL = re.compile(r"\s*\([^)]*\)")

_VOWELS = "aeioAEIO"

# The wiki hedges when a detail is disputed ("pure-blood or half-blood",
# "possibly a Squib"). Such a value makes a bad flat statement, so the
# field is dropped and another attribute is phrased instead.
_HEDGES = (" or ", "possibly", "unknown", "unconfirmed", "presumably", "either ")

# Placeholders the wiki uses for "there isn't one". Stating these as a
# fact produces nonsense ("Patronus took the form of a Non-corporeal").
_EMPTY_VALUES = frozenset(
    {"none", "n/a", "na", "unavailable", "non-corporeal", "noncorporeal", "-"}
)

# The wiki names Voldemort as the boggart of 68 of the ~100 characters
# who have one at all. Posting that would read as the same sentence over
# and over, so it does not count as a distinctive fact.
GENERIC_BOGGARTS = frozenset({"lord voldemort", "voldemort"})

# Rare, individual fields. A character needs one of these to be worth a
# post; house and blood status alone make for filler.
SIGNATURE_FIELDS = ("boggart", "patronus", "animagus")


def clean_choice_field(value: object) -> str:
    """Clean a field where the wiki lists several alternatives at once.

    Boggart, Patronus and Animagus entries are frequently a
    comma-separated list carrying wiki asides — "Dragon (formerly), His
    mother being a criminal", "Rat, Rattlesnake, Bloody eyeball". Only
    the first alternative is worth stating, and the asides are noise.

    Args:
        value: Raw field value from the API.

    Returns:
        The first alternative, or "" if the value is unusable.
    """
    text = clean_field(value)
    if not text:
        return ""
    text = _PARENTHETICAL.sub("", text)
    return text.split(",", 1)[0].strip()


def character_signature(attrs: dict) -> str:
    """Return the first distinctive field a character actually has.

    Applies the same cleaning the formatter will, so the notability gate
    in :mod:`bot.fact_fetcher` cannot admit a character whose only
    Patronus entry is the placeholder "Non-corporeal".

    Args:
        attrs: The character's ``attributes`` dict.

    Returns:
        A field name from ``SIGNATURE_FIELDS``, or "" if none qualifies.
    """
    for field in SIGNATURE_FIELDS:
        value = clean_choice_field(attrs.get(field))
        if not value:
            continue
        if field == "boggart" and value.lower() in GENERIC_BOGGARTS:
            continue
        return field
    return ""


def format_fact(attrs: dict, content_type: str) -> str | None:
    """Format a Potter DB item as a single sentence.

    Args:
        attrs: The item's ``attributes`` dict.
        content_type: One of characters, spells, potions.

    Returns:
        A one-sentence fact, or None if the item yields nothing usable.
    """
    formatters = {
        "characters": _format_character,
        "spells": _format_spell,
        "potions": _format_potion,
    }
    formatter = formatters.get(content_type)
    if formatter is None:
        return None
    return formatter(attrs)


def _format_character(attrs: dict) -> str | None:
    """Phrase one attribute of a character, favouring the interesting ones.

    Nearly every documented character has a house, so an unweighted draw
    would make the feed almost entirely "X was sorted into Y". Boggarts,
    Patronuses and Animagus forms are rarer and far better reading, so
    they outweigh the biographical filler ten to one.
    """
    name = clean_field(attrs.get("name"))
    if not name:
        return None

    options: list[tuple[int, str]] = []

    def offer(weight: int, field: str, template: str) -> None:
        """Add a phrasing for ``field`` if the wiki has a usable value."""
        value = clean_field(attrs.get(field))
        if value:
            options.append((weight, template.format(name=name, value=value)))

    boggart = clean_choice_field(attrs.get("boggart"))
    if boggart and boggart.lower() not in GENERIC_BOGGARTS:
        options.append(
            (10, f"{name}'s boggart took the form of {_with_article(boggart)}.")
        )

    patronus = clean_choice_field(attrs.get("patronus"))
    if patronus:
        options.append(
            (10, f"{name}'s Patronus took the form of {_with_article(patronus)}.")
        )

    animagus = clean_choice_field(attrs.get("animagus"))
    if animagus:
        options.append(
            (10, f"{name} was an Animagus who could become {_with_article(animagus)}.")
        )

    offer(3, "wand", "{name}'s wand was {value}.")  # e.g. "Vine, 10¾\""

    species = clean_choice_field(attrs.get("species"))
    if species and species.lower() != "human":
        options.append((3, f"{name} was {_with_article(_decapitalize(species))}."))

    offer(1, "house", "{name} was sorted into {value}.")

    blood = clean_choice_field(attrs.get("blood_status"))
    if blood:
        options.append((1, f"{name} was {_with_article(_decapitalize(blood))}."))

    if not options:
        return None
    weights = [weight for weight, _ in options]
    return random.choices([text for _, text in options], weights=weights)[0]


def _format_spell(attrs: dict) -> str | None:
    """Format a spell as ``Name (Category) — effect.``"""
    name = clean_field(attrs.get("name"))
    effect = clean_field(attrs.get("effect"))
    if not name or not effect:
        return None

    category = clean_field(attrs.get("category"))
    label = name
    if category and category.lower() != "spell":
        label = f"{name} ({category})"

    return f"{label} — {_sentence(effect)}"


def _format_potion(attrs: dict) -> str | None:
    """Format a potion, appending side effects when there is room."""
    name = clean_field(attrs.get("name"))
    effect = clean_field(attrs.get("effect")) or clean_field(attrs.get("characteristics"))
    if not name or not effect:
        return None

    text = f"{name} — {_sentence(effect)}"

    side_effects = clean_field(attrs.get("side_effects"))
    if side_effects and len(text) + len(side_effects) < 140:
        text += f" Side effects: {_sentence(side_effects)}"

    return text


def clean_field(value: object) -> str:
    """Normalise a Potter DB field to a short single-line string.

    Lists are reduced to their first entry, whitespace is collapsed, a
    trailing parenthetical is dropped ("Andromeda Tonks (née Black)"),
    and anything too long or hedged is rejected outright rather than
    truncated or stated as fact.

    Args:
        value: Raw field value from the API.

    Returns:
        Cleaned text, or "" if the value is unusable.
    """
    if isinstance(value, list):
        value = value[0] if value else ""
    if not isinstance(value, str):
        return ""

    text = _PRONUNCIATION.sub("", " ".join(value.split())).strip()
    if not text or len(text) > MAX_FIELD_LENGTH:
        return ""
    lowered = text.lower()
    if lowered in _EMPTY_VALUES:
        return ""
    if any(hedge in lowered for hedge in _HEDGES):
        return ""
    return text


def _sentence(text: str) -> str:
    """Lowercase the lead-in and guarantee a terminating period."""
    text = _decapitalize(text)
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _decapitalize(text: str) -> str:
    """Lowercase the first character unless the leading word is an acronym."""
    if not text:
        return text
    first_word = text.split(" ", 1)[0]
    if first_word.isupper():
        return text
    return text[0].lower() + text[1:]


def _with_article(value: str) -> str:
    """Prefix ``value`` with "a"/"an", or nothing if it is a proper noun.

    Potter DB mixes common nouns ("Dementor") with names ("Lord
    Voldemort") in the same field, and "a Lord Voldemort" reads as a bug.

    Args:
        value: Already-cleaned field value.

    Returns:
        The value, article included when one is warranted.
    """
    if _is_proper_noun(value):
        return value
    lowered = value.lower()
    # Leading "u" is usually consonantal ("a Unicorn", "a Unicorn horn"),
    # except in un-/um- words ("an Umbrella").
    takes_an = value[:1] in _VOWELS or (
        lowered.startswith(("un", "um")) and not lowered.startswith("uni")
    )
    return f"{'an' if takes_an else 'a'} {value}"


def _is_proper_noun(value: str) -> bool:
    """Guess whether a value names someone rather than describing something."""
    words = value.split()
    if not words:
        return False
    if words[0] in ("Lord", "Lady", "The"):
        return True
    return len(words) >= 2 and all(word[:1].isupper() for word in words)
