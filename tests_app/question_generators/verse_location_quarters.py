class VerseLocationQuestionGenerator:
    """Strategy for generating verse location questions."""

    def generate(self, session, num_questions: int, difficulty: str):
        return [
            {
                "question_type": "verse_location_quarters",
                "difficulty": difficulty,
                "index": i + 1,
            }
            for i in range(num_questions)
        ]
