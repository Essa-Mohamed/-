from django.db import models


class TestSession(models.Model):
    """Represents one attempt of a test by a student."""
    TEST_TYPE_CHOICES = [
        ('similar_count', 'عدد مواضع المتشابهات'),
        ('similar_on_pages', 'مواضع المتشابهات في الصفحات'),
        ('page_edges_quarters', 'بداية/نهاية الصفحات مع الأرباع'),
        ('order_juz_quarters', 'ترتيب الأجزاء والأرباع'),
        ('semantic_similarities', 'متشابهات معاني الآيات'),
        ('verse_location_quarters', 'موقع الآية في الربع والصفحة'),
        ('similar_only', 'Similar verses only'),
        ('similar_quarters', 'Similar verses & quarters'),
        ('similar_quarters_location', 'Similar verses & quarters with location'),
        ('mixed', 'Mixed'),
    ]

    student = models.ForeignKey('students.Student', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True, help_text='وقت بداية الاختبار')
    test_type = models.CharField(max_length=50, choices=TEST_TYPE_CHOICES, default='similar_count')
    num_questions = models.PositiveSmallIntegerField(default=10)
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='easy',
    )
    completed = models.BooleanField(default=False)
    position_order = models.CharField(
        max_length=20,
        choices=[('normal', 'عادي'), ('reverse', 'عكسي')],
        default='normal',
        help_text='ترتيب المواضع في الأسئلة'
    )

    juzs = models.ManyToManyField('quran_structure.Juz', blank=True)
    quarters = models.ManyToManyField('quran_structure.Quarter', blank=True)

    completed_at = models.DateTimeField(null=True, blank=True, help_text='وقت انتهاء الاختبار')
    total_questions = models.PositiveSmallIntegerField(null=True, blank=True, help_text='إجمالي عدد الأسئلة')
    correct_answers = models.PositiveSmallIntegerField(null=True, blank=True, help_text='عدد الإجابات الصحيحة')
    wrong_answers = models.PositiveSmallIntegerField(null=True, blank=True, help_text='عدد الإجابات الخاطئة')
    unanswered = models.PositiveSmallIntegerField(null=True, blank=True, help_text='عدد الأسئلة غير المجاب عليها')

    def __str__(self) -> str:
        return f"TestSession {self.id} for {self.student}"


class TestQuestion(models.Model):
    """Single question within a test session."""
    session = models.ForeignKey('TestSession', on_delete=models.CASCADE, related_name='questions')
    similarity_group = models.ForeignKey('core.SimilarityGroup', on_delete=models.SET_NULL, null=True)
    phrase = models.ForeignKey('core.Phrase', on_delete=models.SET_NULL, null=True, blank=True)
    question_type = models.CharField(max_length=50, default='similar_count')
    question_text = models.TextField(blank=True, null=True)
    correct_answer = models.TextField(blank=True, null=True)
    student_response = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(null=True, blank=True, help_text='وقت الإجابة على السؤال')

    def __str__(self) -> str:
        return f"Question {self.id} in {self.session}"
