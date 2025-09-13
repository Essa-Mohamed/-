from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from students.models import Student
from quran_structure.models import Ayah, Quarter
from core.models import Page


@login_required
def quarter_pages_api(request, qid: int):
    """API endpoint to get pages for a specific quarter"""
    qs = Ayah.objects.filter(quarter_id=qid, page__isnull=False).values_list('page__number', flat=True).distinct()
    pages = sorted(set(p for p in qs if p is not None))
    pmin = min(pages) if pages else None
    
    return JsonResponse({
        "pages": [
            {
                "page_number": p,
                "index_in_quarter": (p - pmin + 1) if pmin else None
            } for p in pages
        ]
    })


@login_required
def page_ayat_api(request, pno: int):
    """API endpoint to get ayat for a specific page"""
    ay = Ayah.objects.filter(page__number=pno).order_by('surah', 'number').values(
        'id', 'surah', 'number', 'text', 'quarter_id'
    )
    return JsonResponse({
        "page": pno,
        "ayat": [
            {
                "id": a["id"],
                "vk": f"{a['surah']}:{a['number']}",
                "text": a["text"],
                "quarter_id": a["quarter_id"]
            } for a in ay
        ]
    })


@login_required
@require_POST
def api_pages_select_first(request):
    """API endpoint to select first ayah for pages test"""
    sid = request.session.get('student_id')
    get_object_or_404(Student, id=sid)
    
    try:
        ayah_id = int(request.POST.get('ayah_id', '0'))
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'ayah_id_invalid'}, status=400)
    
    if not Ayah.objects.filter(id=ayah_id).exists():
        return JsonResponse({'ok': False, 'error': 'ayah_not_found'}, status=404)
    
    flow = request.session.get('pages_flow', {}) or {}
    flow['first_ayah_id'] = ayah_id
    request.session['pages_flow'] = flow
    
    return JsonResponse({'ok': True, 'next': 'pick_page_position'})

