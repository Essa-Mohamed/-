import pytest
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from tests_app.question_generators.similar_count import SimilarCountQuestionGenerator
from tests_app.question_generators.similar_on_pages import SimilarOnPagesQuestionGenerator
from tests_app.question_generators.verse_location_quarters import VerseLocationQuestionGenerator
from tests_app.services.question_generator_factory import QuestionGeneratorFactory


class DummySession:
    def __init__(self, test_type: str):
        self.test_type = test_type


def test_similar_count_strategy_generates_expected_questions():
    gen = SimilarCountQuestionGenerator()
    session = DummySession('similar_count')
    questions = gen.generate(session, 3, 'easy')
    assert len(questions) == 3
    assert all(q['question_type'] == 'similar_count' for q in questions)


def test_similar_on_pages_strategy_generates_expected_questions():
    gen = SimilarOnPagesQuestionGenerator()
    session = DummySession('similar_on_pages')
    questions = gen.generate(session, 2, 'medium')
    assert len(questions) == 2
    assert all(q['question_type'] == 'similar_on_pages' for q in questions)


def test_verse_location_strategy_generates_expected_questions():
    gen = VerseLocationQuestionGenerator()
    session = DummySession('verse_location_quarters')
    questions = gen.generate(session, 1, 'hard')
    assert len(questions) == 1
    assert questions[0]['question_type'] == 'verse_location_quarters'


def test_factory_returns_correct_strategy():
    assert isinstance(
        QuestionGeneratorFactory.get_generator('similar_count'),
        SimilarCountQuestionGenerator,
    )
    assert isinstance(
        QuestionGeneratorFactory.get_generator('similar_on_pages'),
        SimilarOnPagesQuestionGenerator,
    )
    assert isinstance(
        QuestionGeneratorFactory.get_generator('verse_location_quarters'),
        VerseLocationQuestionGenerator,
    )

    with pytest.raises(ValueError):
        QuestionGeneratorFactory.get_generator('unknown')
