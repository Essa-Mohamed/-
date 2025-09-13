import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')
django.setup()

from core.models import PhraseOccurrence, Phrase
from quran_structure.models import Ayah

print("=== فحص البيانات ===")
print(f"عدد التكرارات: {PhraseOccurrence.objects.count()}")
print(f"عدد العبارات: {Phrase.objects.count()}")
print(f"عدد الآيات: {Ayah.objects.count()}")

# فحص بعض التكرارات
if PhraseOccurrence.objects.exists():
    print("\n=== عينة من التكرارات ===")
    for occ in PhraseOccurrence.objects.select_related('phrase', 'ayah').all()[:5]:
        print(f"العبارة: {occ.phrase.text[:30]}... | الآية: {occ.ayah.surah}:{occ.ayah.number}")

# فحص التكرارات في جزء معين
print("\n=== فحص التكرارات في الجزء 1 ===")
ayat_in_juz1 = Ayah.objects.filter(quarter__juz__number=1)
print(f"عدد الآيات في الجزء 1: {ayat_in_juz1.count()}")

if ayat_in_juz1.exists():
    ayat_ids = list(ayat_in_juz1.values_list('id', flat=True))
    occ_in_juz1 = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
    print(f"عدد التكرارات في الجزء 1: {occ_in_juz1.count()}")
    
    if occ_in_juz1.exists():
        # فحص التكرارات المجمعة
        from django.db.models import Count
        stats = occ_in_juz1.values('phrase_id').annotate(freq=Count('id')).filter(freq__gte=2)
        print(f"عدد العبارات المتشابهة في الجزء 1: {len(stats)}")
        
        if stats:
            print("عينة من العبارات المتشابهة:")
            for stat in stats[:3]:
                phrase = Phrase.objects.get(id=stat['phrase_id'])
                print(f"  - {phrase.text[:40]}... (تكرار: {stat['freq']})")
else:
    print("لا توجد آيات في الجزء 1!")
