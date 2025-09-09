import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')
django.setup()

from core.models import PhraseOccurrence, Phrase, Ayah
from django.db.models import Count

print("=== فحص الجزء 1 بالتفصيل ===")

# فحص الآيات في الجزء 1
ayat_in_juz1 = Ayah.objects.filter(quarter__juz__number=1)
print(f"عدد الآيات في الجزء 1: {ayat_in_juz1.count()}")

if ayat_in_juz1.exists():
    ayat_ids = list(ayat_in_juz1.values_list('id', flat=True))
    print(f"معرفات الآيات: {ayat_ids[:10]}...")  # أول 10 معرفات
    
    # فحص التكرارات
    occ_in_juz1 = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
    print(f"عدد التكرارات في الجزء 1: {occ_in_juz1.count()}")
    
    if occ_in_juz1.exists():
        # فحص التكرارات المجمعة
        stats = occ_in_juz1.values('phrase_id').annotate(freq=Count('id')).filter(freq__gte=2)
        print(f"عدد العبارات المتشابهة في الجزء 1: {len(stats)}")
        
        if stats:
            print("\nعينة من العبارات المتشابهة:")
            for stat in stats[:5]:
                phrase = Phrase.objects.get(id=stat['phrase_id'])
                print(f"  - {phrase.text[:50]}... (تكرار: {stat['freq']})")
        else:
            print("لا توجد عبارات متشابهة في الجزء 1!")
            
            # فحص جميع التكرارات
            all_stats = occ_in_juz1.values('phrase_id').annotate(freq=Count('id'))
            print(f"جميع التكرارات (بما في ذلك التكرار الواحد): {len(all_stats)}")
            
            if all_stats:
                print("عينة من جميع التكرارات:")
                for stat in all_stats[:5]:
                    phrase = Phrase.objects.get(id=stat['phrase_id'])
                    print(f"  - {phrase.text[:50]}... (تكرار: {stat['freq']})")
    else:
        print("لا توجد تكرارات في الجزء 1!")
else:
    print("لا توجد آيات في الجزء 1!")

# فحص الجزء 2 أيضاً
print("\n=== فحص الجزء 2 ===")
ayat_in_juz2 = Ayah.objects.filter(quarter__juz__number=2)
print(f"عدد الآيات في الجزء 2: {ayat_in_juz2.count()}")

if ayat_in_juz2.exists():
    ayat_ids = list(ayat_in_juz2.values_list('id', flat=True))
    occ_in_juz2 = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
    print(f"عدد التكرارات في الجزء 2: {occ_in_juz2.count()}")
    
    if occ_in_juz2.exists():
        stats = occ_in_juz2.values('phrase_id').annotate(freq=Count('id')).filter(freq__gte=2)
        print(f"عدد العبارات المتشابهة في الجزء 2: {len(stats)}")
    else:
        print("لا توجد تكرارات في الجزء 2!")
else:
    print("لا توجد آيات في الجزء 2!")

# فحص الجزءين معاً
print("\n=== فحص الجزءين 1 و 2 معاً ===")
ayat_in_both = Ayah.objects.filter(quarter__juz__number__in=[1, 2])
print(f"عدد الآيات في الجزءين 1 و 2: {ayat_in_both.count()}")

if ayat_in_both.exists():
    ayat_ids = list(ayat_in_both.values_list('id', flat=True))
    occ_in_both = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
    print(f"عدد التكرارات في الجزءين: {occ_in_both.count()}")
    
    if occ_in_both.exists():
        stats = occ_in_both.values('phrase_id').annotate(freq=Count('id')).filter(freq__gte=2)
        print(f"عدد العبارات المتشابهة في الجزءين: {len(stats)}")
        
        if stats:
            print("عينة من العبارات المتشابهة:")
            for stat in stats[:5]:
                phrase = Phrase.objects.get(id=stat['phrase_id'])
                print(f"  - {phrase.text[:50]}... (تكرار: {stat['freq']})")
        else:
            print("لا توجد عبارات متشابهة في الجزءين!")
    else:
        print("لا توجد تكرارات في الجزءين!")
else:
    print("لا توجد آيات في الجزءين!")
