"""
خدمة إدارة الاختبارات
"""
from typing import Dict, List, Optional, Tuple
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
import math
import random

from core.models import Student, TestSession, TestQuestion, Juz, Quarter, Page, Ayah, SimilarityGroup, Phrase, PhraseOccurrence


class TestService:
    """خدمة إدارة الاختبارات"""
    
    def __init__(self, student: Student):
        self.student = student
    
    def create_test_session(
        self,
        test_type: str,
        selected_juz: List[int],
        selected_quarters: List[int],
        num_questions: int,
        difficulty: str = 'mixed',
        position_order: str = 'normal'
    ) -> TestSession:
        """إنشاء جلسة اختبار جديدة"""
        
        with transaction.atomic():
            # إنشاء جلسة الاختبار
            session = TestSession.objects.create(
                student=self.student,
                test_type=test_type,
                num_questions=num_questions,
                difficulty=difficulty,
                position_order=position_order,
                started_at=timezone.now()
            )
            
            # إضافة الأجزاء المختارة
            if selected_juz:
                session.juzs.set(Juz.objects.filter(number__in=selected_juz))
            
            # إضافة الأرباع المختارة
            if selected_quarters:
                session.quarters.set(Quarter.objects.filter(id__in=selected_quarters))
            
            return session
    
    def generate_questions_for_session(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str
    ) -> List[Dict]:
        """إنشاء أسئلة الاختبار بالمنطق القديم (تخزين في الجلسة)"""
        
        # الحصول على الآيات في النطاق المحدد
        if session.quarters.exists():
            ayat_qs = Ayah.objects.filter(quarter_id__in=session.quarters.values_list('id', flat=True))
        elif session.juzs.exists():
            ayat_qs = Ayah.objects.filter(quarter__juz__number__in=session.juzs.values_list('number', flat=True))
        else:
            return []
        
        if not ayat_qs.exists():
            return []
        
        ayat_ids = list(ayat_qs.values_list('id', flat=True))
        MAX_OCC_SCOPE = 60
        
        # تشخيص: طباعة عدد الآيات
        print(f"DEBUG: عدد الآيات في النطاق: {len(ayat_ids)}")
        
        # إحصائيات التكرار للنطاق
        stats = (PhraseOccurrence.objects
                .filter(ayah_id__in=ayat_ids)
                .values('phrase_id')
                .annotate(freq=Count('id'))
                .filter(freq__gte=2, freq__lte=MAX_OCC_SCOPE))
        
        # تشخيص: طباعة عدد العبارات
        stats_count = stats.count()
        print(f"DEBUG: عدد العبارات المتشابهة: {stats_count}")
        
        if not stats.exists():
            # محاولة البحث مع معايير أقل صرامة
            print("   ⚠️ لم يتم العثور على عبارات، جاري البحث بمعايير أقل صرامة...")
            stats_loose = (PhraseOccurrence.objects
                          .filter(ayah_id__in=ayat_ids)
                          .values('phrase_id')
                          .annotate(freq=Count('id'))
                          .filter(freq__gte=2))
            print(f"   - عدد العبارات مع معايير أقل صرامة: {len(stats_loose)}")
            
            if not stats_loose:
                return []
            else:
                stats = stats_loose
        
        # تحويل إلى قائمة
        stats_list = list(stats)
        phrase_ids = [s['phrase_id'] for s in stats_list]
        freq_map = {s['phrase_id']: s['freq'] for s in stats_list}
        
        # occurrences per phrase
        occ_rows = (PhraseOccurrence.objects
                   .filter(ayah_id__in=ayat_ids, phrase_id__in=phrase_ids)
                   .values('phrase_id', 'ayah_id'))
        
        occ_by_phrase = {}
        for r in occ_rows:
            occ_by_phrase.setdefault(r['phrase_id'], set()).add(r['ayah_id'])
        
        phrases = {p.id: p for p in Phrase.objects.filter(id__in=phrase_ids)}
        
        # إزالة العبارات الفرعية
        sorted_pids = sorted(
            phrase_ids,
            key=lambda pid: (-phrases[pid].length_words, -freq_map[pid], phrases[pid].text)
        )
        kept, kept_sets = [], []
        for pid in sorted_pids:
            aset = occ_by_phrase[pid]
            if any(aset.issubset(S) for S in kept_sets):
                continue
            kept.append(pid)
            kept_sets.append(aset)
        
        # buckets (نفس قواعد القديم لضمان جودة الانتقاء)
        def bucket(ph_len, freq):
            if ph_len >= 5 and 2 <= freq <= 3:
                return 'easy'
            if ph_len >= 4 and 2 <= freq <= 6:
                return 'medium'
            if ph_len >= 3 and 7 <= freq <= 60:
                return 'hard'
            return 'other'
        
        candidates = []
        for pid in kept:
            ph = phrases[pid]
            freq = freq_map[pid]
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
                'score': freq * math.log(1 + ph.length_words),
            })
        
        if not candidates:
            # محاولة البحث بمعايير أقل صرامة
            print("   ⚠️ لا توجد مرشحين، جاري البحث بمعايير أقل صرامة...")
            for pid in kept:
                ph = phrases[pid]
                freq = freq_map[pid]
                # قبول جميع العبارات بغض النظر عن مستوى الصعوبة
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
                    'bucket': 'easy',  # افتراضي
                    'score': freq * math.log(1 + ph.length_words),
                })
        
        if not candidates:
            return []
        
        # اختيار نهائي
        if difficulty == 'mixed':
            E = [c for c in candidates if c['bucket'] == 'easy']
            M = [c for c in candidates if c['bucket'] == 'medium']
            H = [c for c in candidates if c['bucket'] == 'hard']
            random.shuffle(E)
            random.shuffle(M)
            random.shuffle(H)
            
            ne = max(0, round(num_questions * 0.40))
            nm = max(0, round(num_questions * 0.45))
            nh = max(0, num_questions - ne - nm)
            
            take = E[:ne] + M[:nm] + H[:nh]
            for pool in [M[nm:], E[ne:], H[nh:]]:
                if len(take) >= num_questions:
                    break
                need = num_questions - len(take)
                take += pool[:need]
            selected = take[:num_questions]
            random.shuffle(selected)
        else:
            filtered = [c for c in candidates if c['bucket'] == difficulty]
            if not filtered:
                # إذا لم نجد أسئلة من المستوى المطلوب، نأخذ من أي مستوى
                filtered = candidates
            if not filtered:
                return []
            filtered.sort(key=lambda x: (-x['score'], x['phrase_text']))
            selected = filtered[:num_questions]
        
        # إضافة given_answer لكل سؤال
        for question in selected:
            question['given_answer'] = None
        
        print(f"DEBUG: تم إنشاء {len(selected)} سؤال")
        return selected
    
    def generate_verse_location_questions(
        self,
        session: TestSession,
        num_questions: int,
        difficulty: str
    ) -> List[Dict]:
        """إنشاء أسئلة موقع الآيات في الأرباع"""
        
        # الحصول على الآيات في النطاق المحدد
        if session.quarters.exists():
            ayahs = Ayah.objects.filter(quarter_id__in=session.quarters.values_list('id', flat=True))
        elif session.juzs.exists():
            ayahs = Ayah.objects.filter(quarter__juz__number__in=session.juzs.values_list('number', flat=True))
        else:
            return []
        
        if not ayahs.exists():
            return []
        
        # تحويل إلى قائمة
        ayah_list = list(ayahs.select_related('quarter__juz').order_by('surah', 'number'))
        
        # تطبيق مستوى الصعوبة
        if difficulty == 'easy':
            # آيات من الأجزاء الأولى
            ayah_list = [a for a in ayah_list if a.quarter and a.quarter.juz.number <= 10]
        elif difficulty == 'medium':
            # آيات من الأجزاء الوسطى
            ayah_list = [a for a in ayah_list if a.quarter and 10 < a.quarter.juz.number <= 20]
        elif difficulty == 'hard':
            # آيات من الأجزاء الأخيرة
            ayah_list = [a for a in ayah_list if a.quarter and a.quarter.juz.number > 20]
        
        if not ayah_list:
            return []
        
        # اختيار عشوائي للأسئلة
        import random
        selected_ayahs = random.sample(ayah_list, min(num_questions, len(ayah_list)))
        
        questions = []
        for ayah in selected_ayahs:
            if ayah.quarter:
                questions.append({
                    'ayah_id': ayah.id,
                    'ayah_text': ayah.text,
                    'surah': ayah.surah,
                    'number': ayah.number,
                    'correct_quarter_id': ayah.quarter.id,
                    'correct_quarter_label': ayah.quarter.label,
                    'correct_juz_number': ayah.quarter.juz.number,
                    'given_answer': None,
                })
        
        return questions
    
    def make_options(self, correct_count: int) -> List[int]:
        """اختيارات مرتّبة تصاعديًا بدون تدوير، حول الإجابة الصحيحة."""
        pool = {correct_count}
        for off in (-3, -2, -1, 1, 2, 3, 4, 5):
            v = correct_count + off
            if v >= 1:
                pool.add(v)
            if len(pool) >= 4:
                break
        return sorted(pool)[:4]
    
    def build_scope_label(self, selected_juz_ids: List[int], selected_quarter_ids: List[int]) -> str:
        """بناء تسمية النطاق المختار"""
        if selected_quarter_ids:
            quarters = Quarter.objects.filter(id__in=selected_quarter_ids).select_related('juz')
            by_juz = {}
            for q in quarters:
                by_juz.setdefault(q.juz.number, []).append(q)
            parts = []
            for j in sorted(by_juz):
                qs = by_juz[j]
                if len(qs) == 8:
                    parts.append(f"الجزء {j}")
                else:
                    idx = ', '.join(f"الربع {q.index_in_juz}" for q in sorted(qs, key=lambda x: x.index_in_juz))
                    parts.append(f"الجزء {j} - {idx}")
            return "اختبار على: " + "؛ ".join(parts)
        elif selected_juz_ids:
            lbl = '؛ '.join(f"الجزء {j}" for j in sorted(selected_juz_ids))
            return f"اختبار على: {lbl}"
        return "اختبار على: نطاق غير محدد"
