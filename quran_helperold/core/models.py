"""
Database models for the Quran memorization assistant.

These models define the fundamental data structures required
to support users (students), complaints, Quranic metadata, and
test sessions. They are simplified placeholders; relationships
can be expanded to cover more advanced features.
"""
from django.db import models  # type: ignore
from django.contrib.auth.models import User  # type: ignore


class Student(models.Model):
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    def avatar_url(self):
        try:
            if self.avatar and hasattr(self.avatar, "url"):
                return self.avatar.url
        except Exception:
            pass
        return ""  # هنستخدم شكل افتراضي بالـCSS لو فاضي
    """A simple student profile linked to the built-in User model."""

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    display_name = models.CharField(max_length=100)

    def __str__(self) -> str:
        return self.display_name


class Complaint(models.Model):
    """A complaint or suggestion submitted by a student."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    resolved = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Complaint by {self.student}: {self.text[:30]}"


class Juz(models.Model):
    """Represents one of the 30 parts of the Qur’an."""

    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=50, blank=True)

    def __str__(self) -> str:
        return f"Juz {self.number}"


class Quarter(models.Model):
    """Represents a quarter of a Juz (Rubʿ)."""

    juz = models.ForeignKey(Juz, on_delete=models.CASCADE)
    index_in_juz = models.PositiveSmallIntegerField(help_text="1–8 for each Juz")
    label = models.CharField(max_length=100, help_text="Name of the quarter from the opening words of its first verse")

    class Meta:
        unique_together = ('juz', 'index_in_juz')

    def __str__(self) -> str:
        return f"{self.juz} - Quarter {self.index_in_juz}"


class Page(models.Model):
    """Represents a page of the Mushaf with its image."""

    number = models.PositiveSmallIntegerField(unique=True)
    image = models.ImageField(upload_to='pages/')

    def __str__(self) -> str:
        return f"Page {self.number}"


class Ayah(models.Model):
    """Represents a single ayah with its metadata."""

    surah = models.PositiveSmallIntegerField()
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    page = models.ForeignKey(Page, on_delete=models.SET_NULL, null=True, blank=True)
    quarter = models.ForeignKey(Quarter, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('surah', 'number')

    def __str__(self) -> str:
        return f"{self.surah}:{self.number}"


class SimilarityGroup(models.Model):
    """Group of similar verses (mutashabehat)."""

    name = models.CharField(max_length=200, help_text="Key phrase that identifies the group")
    ayat = models.ManyToManyField(Ayah, related_name='similarity_groups')

    def __str__(self) -> str:
        return self.name


class Phrase(models.Model):
    text = models.CharField(max_length=200)
    normalized = models.CharField(max_length=200, db_index=True)
    length_words = models.PositiveSmallIntegerField()
    global_freq = models.PositiveIntegerField(default=0)
    confusability = models.FloatField(default=0.0)

    def __str__(self):
        return self.text


class PhraseOccurrence(models.Model):
    phrase = models.ForeignKey(Phrase, related_name='occurrences', on_delete=models.CASCADE)
    ayah = models.ForeignKey(Ayah, on_delete=models.CASCADE)
    start_word = models.PositiveSmallIntegerField()
    end_word = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('phrase', 'ayah', 'start_word', 'end_word')
        indexes = [
            models.Index(fields=['ayah']),
            models.Index(fields=['phrase']),
        ]


class TestSession(models.Model):
    """Represents one attempt of a test by a student."""

    # NEW: أنواع الاختبارات (الجديدة + القديمة حفاظًا على التوافق)
    TEST_TYPE_CHOICES = [
        ('similar_count', 'عدد مواضع المتشابهات'),                 # المتاح حاليًا
        ('similar_on_pages', 'مواضع المتشابهات في الصفحات'),        # قريبًا
        ('page_edges_quarters', 'بداية/نهاية الصفحات مع الأرباع'),   # قريبًا
        ('order_juz_quarters', 'ترتيب الأجزاء والأرباع'),            # قريبًا
        ('semantic_similarities', 'متشابهات معاني الآيات'),          # قريبًا

        # القيم القديمة إن كانت موجودة في بيانات سابقة:
        ('similar_only', 'Similar verses only'),
        ('similar_quarters', 'Similar verses & quarters'),
        ('similar_quarters_location', 'Similar verses & quarters with location'),
        ('mixed', 'Mixed'),
    ]

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    test_type = models.CharField(
        max_length=50,
        choices=TEST_TYPE_CHOICES,
        default='similar_count',
    )
    num_questions = models.PositiveSmallIntegerField(default=10)
    difficulty = models.CharField(
        max_length=10,
        choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')],
        default='easy',
    )
    completed = models.BooleanField(default=False)

    # ManyToMany to Juz and Quarter representing scope
    juzs = models.ManyToManyField(Juz, blank=True)
    quarters = models.ManyToManyField(Quarter, blank=True)

    def __str__(self) -> str:
        return f"TestSession {self.id} for {self.student}"


class TestQuestion(models.Model):
    """Single question within a test session."""

    session = models.ForeignKey(TestSession, on_delete=models.CASCADE, related_name='questions')
    similarity_group = models.ForeignKey(SimilarityGroup, on_delete=models.SET_NULL, null=True)
    # store JSON or text representing the student's answer. In a complete implementation
    # this could be structured data (quarter ID, page number, half, etc.).
    student_response = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Question {self.id} in {self.session}"
