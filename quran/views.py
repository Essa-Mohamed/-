from django.http import JsonResponse, Http404
from django.shortcuts import render
from core.models import Ayah

def page_meta_api(request, num: int):
    """API لإرجاع بيانات آيات صفحة معينة"""
    qs = Ayah.objects.filter(page__number=num).order_by('line', 'surah', 'number')
    if not qs.exists(): 
        raise Http404()
    
    data = []
    for a in qs:
        data.append({
            "surah": a.surah,
            "ayah": a.number,
            "line": a.line,
            "text": a.text_imlaei or a.text_uthmani
        })
    
    return JsonResponse({"page": num, "items": data})

def mushaf_page(request, num: int):
    """عرض صفحة المصحف"""
    # التحقق من وجود الصفحة
    try:
        from core.models import Page
        page = Page.objects.get(number=num)
    except Page.DoesNotExist:
        raise Http404("الصفحة غير موجودة")
    
    return render(request, "mushaf_page.html", {"page": num})

def mushaf_demo(request):
    """صفحة تجريبية للمصحف"""
    return render(request, "mushaf_demo.html", {})

