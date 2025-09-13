from tests_app.question_generators.similar_count import SimilarCountQuestionGenerator
from tests_app.question_generators.similar_on_pages import SimilarOnPagesQuestionGenerator
from tests_app.question_generators.verse_location_quarters import VerseLocationQuestionGenerator


class QuestionGeneratorFactory:
    """Return appropriate question generator based on test type."""

    _mapping = {
        "similar_count": SimilarCountQuestionGenerator,
        "similar_on_pages": SimilarOnPagesQuestionGenerator,
        "verse_location_quarters": VerseLocationQuestionGenerator,
    }

    @classmethod
    def get_generator(cls, test_type: str):
        generator_cls = cls._mapping.get(test_type)
        if not generator_cls:
            raise ValueError(f"Unknown test type: {test_type}")
        return generator_cls()
