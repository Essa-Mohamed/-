from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Complaint, Student, Juz, Quarter, SimilarityGroup, Ayah,
    TestSession, TestQuestion, Phrase, PhraseOccurrence
)

# --------- تخصيص عرض الـUsers في الأدمن ---------
# أخفي Groups (اختياري)
try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

# لازم نفك تسجيل User الافتراضي قبل ما نعيد تسجيله
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class StaffOnlyUserAdmin(BaseUserAdmin):
    """اعرض في الأدمن المستخدمين الـstaff فقط."""
    def get_queryset(self, request):
     qs = super().get_queryset(request)
     return qs.filter(is_staff=True)

# --------- بقية الموديلات ---------
@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('student', 'short_text', 'created_at', 'resolved')
    list_filter = ('resolved', 'created_at', 'student')
    search_fields = ('text', 'student__display_name', 'student__user__username')
    raw_id_fields = ('student',)
    actions = ['mark_resolved']

    def short_text(self, obj):
        return obj.text[:50] + ('…' if len(obj.text) > 50 else '')
    short_text.short_description = 'نص مختصر'

    def mark_resolved(self, request, queryset):
        updated = queryset.update(resolved=True)
        self.message_user(request, f'{updated} شكوى تم تعليمها كمُحلّة.')
    mark_resolved.short_description = 'وضع كمُحلّل'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'user')
    search_fields = ('display_name', 'user__username')

@admin.register(Phrase)
class PhraseAdmin(admin.ModelAdmin):
    list_display = ('text', 'length_words', 'global_freq', 'confusability')
    search_fields = ('text', 'normalized')

@admin.register(PhraseOccurrence)
class PhraseOccurrenceAdmin(admin.ModelAdmin):
    list_display = ('phrase', 'ayah', 'start_word', 'end_word')
    search_fields = ('phrase__text', 'ayah__surah', 'ayah__number')
    list_filter = ('phrase',)

# (لو حابب تضيف تسجيل لباقي الموديلات)
# admin.site.register(Juz)
# admin.site.register(Quarter)
# admin.site.register(SimilarityGroup)
# admin.site.register(Ayah)
# admin.site.register(TestSession)
# admin.site.register(TestQuestion)
