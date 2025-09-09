import re
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

DIAC = re.compile(r'[\u064B-\u0652\u0670\u06DF-\u06ED]')

def _strip_diac(s: str) -> str:
    return DIAC.sub('', s or '')

@register.filter(is_safe=True)
def highlight(text, phrase):
    """
    إبراز العبارة داخل النص مع تجاهل الحركات.
    يبني نمطاً يسمح بظهور الحركات اختيارياً بين الحروف، والمسافات = \s+.
    """
    if not phrase or not text:
        return text
    plain = _strip_diac(phrase)
    if not plain:
        return text

    # ابنِ نمطًا حرف-بحرف يسمح بحركات اختيارية
    parts = []
    for ch in plain:
        if ch.isspace():
            parts.append(r'\s+')
        else:
            # الحرف ثم أي عدد من الحركات بعده
            parts.append(re.escape(ch) + r'[\u064B-\u0652\u0670\u06DF-\u06ED]*')
    pattern = ''.join(parts)

    def repl(m):
        return f"<mark>{m.group(0)}</mark>"

    try:
        highlighted = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    except re.error:
        return text
    return mark_safe(highlighted)
