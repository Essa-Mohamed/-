class SimilarOnPagesQuestionGenerator:
    """Strategy for generating similar-on-pages questions."""

    def generate(self, session, num_questions: int, difficulty: str):
        return [
            {
                "question_type": "similar_on_pages",
                "difficulty": difficulty,
                "index": i + 1,
            }
            for i in range(num_questions)
        ]
