"""Tests for bot.fact_formatter (Potter DB item -> one plain sentence)."""

import pytest

from bot.fact_formatter import (
    GENERIC_BOGGARTS,
    character_signature,
    clean_choice_field,
    clean_field,
    format_fact,
)

# Covers the emoji blocks the old facts bot used (🧙 ✨ 🧪 📚 🎬 ⚠️).
EMOJI_RANGES = ((0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0xFE00, 0xFE0F))


def _has_emoji(text: str) -> bool:
    return any(
        low <= ord(ch) <= high for ch in text for low, high in EMOJI_RANGES
    )


class TestHouseStyle:
    """The rules the user asked for: no emoji, no tags, one sentence."""

    @pytest.mark.parametrize(
        "fixture_name,content_type",
        [
            ("sample_spell", "spells"),
            ("sample_potion", "potions"),
            ("sample_character", "characters"),
        ],
    )
    def test_no_emoji_and_no_hashtags(
        self, fixture_name: str, content_type: str, request: pytest.FixtureRequest
    ) -> None:
        item = request.getfixturevalue(fixture_name)
        for _ in range(30):  # character phrasing is randomised
            text = format_fact(item["attributes"], content_type)
            assert text
            assert not _has_emoji(text)
            assert "#" not in text

    def test_ends_as_a_sentence(self, sample_spell: dict) -> None:
        text = format_fact(sample_spell["attributes"], "spells")
        assert text and text.endswith(".")

    def test_unknown_content_type_returns_none(self, sample_spell: dict) -> None:
        assert format_fact(sample_spell["attributes"], "movies") is None


class TestSpellsAndPotions:
    """Formatting of the two highest-volume content types."""

    def test_spell_includes_name_category_and_effect(
        self, sample_spell: dict
    ) -> None:
        text = format_fact(sample_spell["attributes"], "spells")
        assert text == (
            "Alohomora (Charm) — unlocked doors and other locked objects."
        )

    def test_generic_spell_category_is_omitted(self, sample_spell: dict) -> None:
        sample_spell["attributes"]["category"] = "Spell"
        text = format_fact(sample_spell["attributes"], "spells")
        assert text is not None and text.startswith("Alohomora — ")

    def test_spell_without_effect_yields_nothing(
        self, sample_spell: dict
    ) -> None:
        sample_spell["attributes"]["effect"] = ""
        assert format_fact(sample_spell["attributes"], "spells") is None

    def test_wiki_list_capitals_are_lowered(self) -> None:
        """Potter DB capitalises every comma-separated entry."""
        attrs = {
            "name": "Amortentia",
            "characteristics": (
                "Mother-of-pearl sheen, Spiralling steam, Scent was varied"
            ),
        }
        assert format_fact(attrs, "potions") == (
            "Amortentia — mother-of-pearl sheen, spiralling steam, "
            "scent was varied."
        )

    def test_proper_names_keep_their_capitals(self) -> None:
        """A capital followed by another capital is treated as a name."""
        attrs = {
            "name": "Oculus Potion",
            "effect": "Restored sight, Counteracted the Conjunctivitis Curse",
        }
        text = format_fact(attrs, "potions")
        assert text is not None and "Conjunctivitis Curse" in text
        assert "counteracted the" in text

    def test_potion_falls_back_to_characteristics(
        self, sample_potion: dict
    ) -> None:
        sample_potion["attributes"]["effect"] = ""
        text = format_fact(sample_potion["attributes"], "potions")
        assert text is not None and "sheen" in text


class TestCharacters:
    """Attribute choice, articles, and the notability signature."""

    def test_phrasings_are_all_about_the_character(
        self, sample_character: dict
    ) -> None:
        seen = {
            format_fact(sample_character["attributes"], "characters")
            for _ in range(100)
        }
        assert len(seen) > 1  # weighted random across attributes
        assert all(text.startswith("Harry James Potter") for text in seen)

    def test_signature_fields_dominate_the_draw(
        self, sample_character: dict
    ) -> None:
        """House is 1/10 the weight of a boggart or Patronus."""
        draws = [
            format_fact(sample_character["attributes"], "characters")
            for _ in range(300)
        ]
        sorted_into = sum(1 for text in draws if "sorted into" in text)
        assert sorted_into < len(draws) / 4

    def test_proper_noun_takes_no_article(
        self, sample_character: dict
    ) -> None:
        sample_character["attributes"]["boggart"] = "Bellatrix Lestrange"
        draws = {
            format_fact(sample_character["attributes"], "characters")
            for _ in range(100)
        }
        boggart_lines = [t for t in draws if "boggart" in t]
        assert boggart_lines
        assert all("of Bellatrix Lestrange." in t for t in boggart_lines)

    def test_common_noun_takes_an_article(
        self, sample_character: dict
    ) -> None:
        draws = {
            format_fact(sample_character["attributes"], "characters")
            for _ in range(100)
        }
        boggart_lines = [t for t in draws if "boggart" in t]
        assert boggart_lines
        assert all("of a Dementor." in t for t in boggart_lines)

    @pytest.mark.parametrize(
        "value,expected",
        [("Otter", "an Otter"), ("Unicorn", "a Unicorn"), ("Umbrella", "an Umbrella")],
    )
    def test_article_choice(
        self, sample_character: dict, value: str, expected: str
    ) -> None:
        attrs = {"name": "Someone", "patronus": value}
        assert format_fact(attrs, "characters") == (
            f"Someone's Patronus took the form of {expected}."
        )

    def test_signature_identifies_the_distinctive_field(
        self, sample_character: dict
    ) -> None:
        assert character_signature(sample_character["attributes"]) == "boggart"

    def test_placeholder_patronus_is_not_a_signature(self) -> None:
        assert character_signature({"patronus": "Non-corporeal"}) == ""
        assert character_signature({"patronus": "None"}) == ""

    def test_generic_boggart_is_not_a_signature(self) -> None:
        assert character_signature({"boggart": "Lord Voldemort"}) == ""

    def test_generic_boggart_is_never_phrased(self) -> None:
        attrs = {"name": "Someone", "boggart": "Lord Voldemort", "house": "Slytherin"}
        draws = {format_fact(attrs, "characters") for _ in range(50)}
        assert all("boggart" not in text for text in draws)

    def test_character_with_nothing_to_say(self) -> None:
        assert format_fact({"name": "Someone"}, "characters") is None


class TestCleanField:
    """Field sanitising shared by the gate and the formatters."""

    def test_collapses_whitespace(self) -> None:
        assert clean_field("  a   b \n c ") == "a b c"

    def test_takes_first_entry_of_a_list(self) -> None:
        assert clean_field(["First", "Second"]) == "First"

    def test_strips_trailing_parenthetical(self) -> None:
        assert clean_field("Andromeda Tonks (née Black)") == "Andromeda Tonks"

    def test_rejects_hedged_values(self) -> None:
        assert clean_field("Pure-blood or half-blood") == ""
        assert clean_field("possibly a Squib") == ""

    def test_rejects_placeholders(self) -> None:
        assert clean_field("None") == ""
        assert clean_field("N/A") == ""

    def test_rejects_overlong_values(self) -> None:
        assert clean_field("x" * 200) == ""

    def test_rejects_non_strings(self) -> None:
        assert clean_field(None) == ""
        assert clean_field(42) == ""
        assert clean_field([]) == ""

    def test_generic_boggarts_are_lowercase_for_comparison(self) -> None:
        assert all(value == value.lower() for value in GENERIC_BOGGARTS)


class TestCleanChoiceField:
    """Fields where the wiki crams several alternatives into one value."""

    def test_takes_the_first_alternative(self) -> None:
        assert clean_choice_field("Rat, Rattlesnake, Bloody eyeball") == "Rat"

    def test_drops_a_mid_string_aside(self) -> None:
        assert (
            clean_choice_field("Dragon (formerly), His mother being a criminal")
            == "Dragon"
        )

    def test_leaves_a_plain_value_alone(self) -> None:
        assert clean_choice_field("Dementor") == "Dementor"

    def test_still_rejects_placeholders(self) -> None:
        assert clean_choice_field("Non-corporeal") == ""

    def test_multi_value_boggart_is_phrased_as_one_thing(self) -> None:
        attrs = {
            "name": "Daniel Page",
            "boggart": "Dragon (formerly), His mother being a criminal",
        }
        assert format_fact(attrs, "characters") == (
            "Daniel Page's boggart took the form of a Dragon."
        )
