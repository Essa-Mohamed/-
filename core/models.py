"""Core models unrelated to the specialized apps."""
from django.db import models


class Page(models.Model):
    """Represents a page of the Mushaf with its image."""
    number = models.PositiveSmallIntegerField(unique=True)
    image = models.ImageField(upload_to='pages/')

    def __str__(self) -> str:
        return f"Page {self.number}"


class SimilarityGroup(models.Model):
    """Group of similar verses (mutashabehat)."""
    name = models.CharField(max_length=200, help_text="Key phrase that identifies the group")
    ayat = models.ManyToManyField('quran_structure.Ayah', related_name='similarity_groups')

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
    ayah = models.ForeignKey('quran_structure.Ayah', on_delete=models.CASCADE)
    start_word = models.PositiveSmallIntegerField()
    end_word = models.PositiveSmallIntegerField()

    class Meta:
        unique_together = ('phrase', 'ayah', 'start_word', 'end_word')
        indexes = [
            models.Index(fields=['ayah']),
            models.Index(fields=['phrase']),
        ]
