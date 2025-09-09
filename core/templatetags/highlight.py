import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# إزالة التشكيل فقط
DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED\u06D6-\u06DC\u06DD-\u06E1\u06E2-\u06E4\u06E7\u06E8\u06EA-\u06ED]')

def _remove_diacritics(text: str) -> str:
    """
    إزالة التشكيل فقط من النص
    """
    if not text:
        return text
    return DIAC.sub('', text)

@register.filter(is_safe=True)
def highlight(text, phrase):
    """
    تظليل بسيط - يطابق العبارة بالزبط مع تجاهل التشكيل فقط
    """
    if not phrase or not text:
        return text
    
    # إزالة التشكيل من النص والعبارة
    clean_text = _remove_diacritics(text)
    clean_phrase = _remove_diacritics(phrase)
    
    if not clean_phrase or not clean_text:
        return text
    
    # البحث عن العبارة في النص النظيف
    pos = clean_text.find(clean_phrase)
    if pos == -1:
        return text
    
    # إنشاء خريطة المواضع بين النص النظيف والأصلي
    clean_to_original = []
    clean_pos = 0
    
    for i, char in enumerate(text):
        if not DIAC.search(char):  # إذا لم يكن تشكيل
            clean_to_original.append(i)
            clean_pos += 1
    
    # تحويل المواضع إلى النص الأصلي
    if pos < len(clean_to_original) and pos + len(clean_phrase) <= len(clean_to_original):
        start_pos = clean_to_original[pos]
        end_pos = clean_to_original[pos + len(clean_phrase) - 1] + 1
        
        # تطبيق التظليل
        highlighted = text[:start_pos] + f'<mark class="hl">{text[start_pos:end_pos]}</mark>' + text[end_pos:]
        return mark_safe(highlighted)
    
    return text

@register.filter(is_safe=True)
def highlight_multiple(text, phrase):
    """
    تظليل جميع تكرارات العبارة - يطابق العبارة بالزبط مع تجاهل التشكيل فقط
    """
    if not phrase or not text:
        return text
    
    # إزالة التشكيل من النص والعبارة
    clean_text = _remove_diacritics(text)
    clean_phrase = _remove_diacritics(phrase)
    
    if not clean_phrase or not clean_text:
        return text
    
    # إنشاء خريطة المواضع بين النص النظيف والأصلي
    clean_to_original = []
    for i, char in enumerate(text):
        if not DIAC.search(char):  # إذا لم يكن تشكيل
            clean_to_original.append(i)
    
    # البحث عن جميع التكرارات
    highlighted_text = text
    offset = 0
    
    pos = 0
    while True:
        pos = clean_text.find(clean_phrase, pos)
        if pos == -1:
            break
            
        # تحويل المواضع إلى النص الأصلي
        if pos < len(clean_to_original) and pos + len(clean_phrase) <= len(clean_to_original):
            start_pos = clean_to_original[pos]
            end_pos = clean_to_original[pos + len(clean_phrase) - 1] + 1
            
            # تطبيق التظليل
            highlighted_text = (highlighted_text[:start_pos + offset] + 
                              f'<mark class="hl">{highlighted_text[start_pos + offset:end_pos + offset]}</mark>' + 
                              highlighted_text[end_pos + offset:])
            
            # تحديث الإزاحة بسبب إضافة HTML
            offset += len('<mark class="hl"></mark>')
            
        pos += len(clean_phrase)
    
    return mark_safe(highlighted_text)
