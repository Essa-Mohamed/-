from django.db import models


class Juz(models.Model):
    """Represents one of the 30 parts of the Qur’an."""
    number = models.PositiveSmallIntegerField(unique=True)
    name = models.CharField(max_length=50, blank=True)

    def __str__(self) -> str:
        return f"Juz {self.number}"


class Quarter(models.Model):
    """Represents a quarter of a Juz (Rubʿ)."""
    juz = models.ForeignKey('Juz', on_delete=models.CASCADE)
    index_in_juz = models.PositiveSmallIntegerField(help_text="1–8 for each Juz")
    label = models.CharField(max_length=100, help_text="Name of the quarter from the opening words of its first verse")

    class Meta:
        unique_together = ('juz', 'index_in_juz')

    def __str__(self) -> str:
        return f"{self.juz} - Quarter {self.index_in_juz}"


class Ayah(models.Model):
    """Represents a single ayah with its metadata."""
    surah = models.PositiveSmallIntegerField()
    number = models.PositiveSmallIntegerField()
    text = models.TextField()
    page = models.ForeignKey('core.Page', on_delete=models.SET_NULL, null=True, blank=True)
    quarter = models.ForeignKey('Quarter', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ('surah', 'number')

    def __str__(self) -> str:
        return f"{self.surah}:{self.number}"
