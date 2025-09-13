class SimilarCountQuestionGenerator:
    """Strategy for generating similar count questions."""

    def generate(self, session, num_questions: int, difficulty: str):
        return [
            {
                "question_type": "similar_count",
                "difficulty": difficulty,
                "index": i + 1,
            }
            for i in range(num_questions)
        ]
