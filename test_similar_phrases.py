import os
import django
import math

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quran_helper.settings')
django.setup()

from core.models import PhraseOccurrence, Phrase, Ayah
from django.db.models import Count

print("=== اختبار منطق البحث عن العبارات المتشابهة ===")

# محاكاة اختيار جزئين 1 و 2
juz_ids = [1, 2]
ayat_qs = Ayah.objects.filter(quarter__juz__number__in=juz_ids)
ayat_ids = list(ayat_qs.values_list('id', flat=True))
MAX_OCC_SCOPE = 60

print(f"🔍 البحث عن العبارات المتشابهة:")
print(f"   - عدد الآيات في النطاق: {len(ayat_ids)}")
print(f"   - النطاق: {juz_ids}")
print(f"   - أول 5 معرفات آيات: {ayat_ids[:5]}")

# فحص التكرارات قبل التجميع
all_occ = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids)
print(f"   - إجمالي التكرارات في النطاق: {all_occ.count()}")

stats = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
        .annotate(freq=Count('id')).filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))

print(f"   - عدد العبارات المتشابهة الموجودة: {len(stats)}")
print(f"   - MAX_OCC_SCOPE: {MAX_OCC_SCOPE}")

if not stats:
    print("   ⚠️ لم يتم العثور على عبارات، جاري البحث بمعايير أقل صرامة...")
    stats_loose = (PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids).values('phrase_id')
                   .annotate(freq=Count('id')).filter(freq__gte=2))
    print(f"   - عدد العبارات مع معايير أقل صرامة: {len(stats_loose)}")
    
    if not stats_loose:
        print("❌ لا توجد عبارات متشابهة في النطاق المحدد!")
    else:
        print("✅ تم العثور على عبارات بمعايير أقل صرامة")
        stats = stats_loose
else:
    print("✅ تم العثور على عبارات بالمعايير العادية")

if stats:
    phrase_ids = [s['phrase_id'] for s in stats]
    freq_map = {s['phrase_id']: s['freq'] for s in stats}
    
    print(f"   - العبارات المختارة: {len(phrase_ids)}")
    
    # فحص التكرارات
    occ_rows = PhraseOccurrence.objects.filter(ayah_id__in=ayat_ids, phrase_id__in=phrase_ids).values('phrase_id', 'ayah_id')
    occ_by_phrase = {}
    for r in occ_rows:
        occ_by_phrase.setdefault(r['phrase_id'], set()).add(r['ayah_id'])
    
    phrases = {p.id: p for p in Phrase.objects.filter(id__in=phrase_ids)}
    sorted_pids = sorted(phrase_ids, key=lambda pid: (-phrases[pid].length_words, -freq_map[pid], phrases[pid].text))
    
    print(f"   - العبارات بعد الترتيب: {len(sorted_pids)}")
    
    kept, kept_sets = [], []
    for pid in sorted_pids:
        aset = occ_by_phrase[pid]
        if any(aset.issubset(S) for S in kept_sets):
            continue
        kept.append(pid)
        kept_sets.append(aset)
    
    print(f"   - العبارات النهائية بعد إزالة التكرار: {len(kept)}")
    
    # فحص المرشحين
    candidates = []
    for pid in kept:
        ph = phrases[pid]
        freq = freq_map[pid]
        
        # فحص مستوى الصعوبة
        def bucket(ph_len, freq):
            if ph_len >= 5 and 2 <= freq <= 3:
                return 'easy'
            if ph_len >= 4 and 2 <= freq <= 6:
                return 'medium'
            if ph_len >= 3 and 7 <= freq <= 60:
                return 'hard'
            return 'other'
        
        b = bucket(ph.length_words, freq)
        if b == 'other':
            continue
            
        ayahs = (Ayah.objects
                 .filter(id__in=occ_by_phrase[pid])
                 .select_related('quarter__juz')
                 .order_by('surah', 'number'))
        literal = [{
            'surah': a.surah, 'number': a.number,
            'juz_number': a.quarter.juz.number if a.quarter else None,
            'quarter_label': a.quarter.label if a.quarter else None,
            'text': a.text,
        } for a in ayahs]
        candidates.append({
            'phrase_id': pid,
            'phrase_text': ph.text,
            'correct_count': freq,
            'occurrence_ayah_ids': list(occ_by_phrase[pid]),
            'literal_ayahs': literal,
            'bucket': b,
            'score': freq * __import__('math').log(1 + ph.length_words),
        })
    
    print(f"   - المرشحون للأسئلة: {len(candidates)}")
    
    if not candidates:
        print("❌ لا توجد مرشحين بعد تطبيق مستوى الصعوبة!")
    else:
        print("✅ تم العثور على مرشحين للأسئلة!")
        print("عينة من المرشحين:")
        for i, c in enumerate(candidates[:3]):
            print(f"  {i+1}. {c['phrase_text'][:50]}... (مستوى: {c['bucket']}, تكرار: {c['correct_count']})")
else:
    print("❌ لا توجد عبارات متشابهة في النطاق!")
