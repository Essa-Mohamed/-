from django.urls import path, include
from tests_app.views_cbv.cbv import TestCatalogView

app_name = "tests_app"

urlpatterns = [
    # كتالوج الامتحانات (CBV داخل tests_app)
    path("", TestCatalogView.as_view(), name="tests_root"),

    # أنواع الاختبارات المختلفة
    path("similar-count/", include(("tests_app.similar_count.urls", "similar_count"), namespace="similar_count")),
    path("similar-on-pages/", include(("tests_app.similar_positions_on_pages.urls", "similar_positions_on_pages"), namespace="similar_positions_on_pages")),
    path("verse-location-quarters/", include(("tests_app.verse_location_quarters.urls", "verse_location_quarters"), namespace="verse_location_quarters")),
]


