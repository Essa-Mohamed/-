from pathlib import Path
import json
from django.http import Http404
from django.shortcuts import render, redirect


_CACHE = {
    "data": None,
    "by_page": {},
}


def _load_elec_mushaf_data():
    if _CACHE["data"] is not None:
        return _CACHE["data"]
    base_dir = Path(__file__).resolve().parents[1]
    json_path = base_dir / "elec_mushaf" / "kfgqpc_hafs_smart_data" / "hafs_smart_v8.json"
    if not json_path.exists():
        _CACHE["data"] = []
        return _CACHE["data"]
    with open(json_path, "r", encoding="utf-8") as f:
        _CACHE["data"] = json.load(f)
    return _CACHE["data"]


def _get_page_ayahs(page_no: int):
    if page_no in _CACHE["by_page"]:
        return _CACHE["by_page"][page_no]
    data = _load_elec_mushaf_data()
    page_items = [row for row in data if int(row.get("page", 0)) == int(page_no)]
    # Normalize and sort by (line_start, aya_no)
    page_items.sort(key=lambda r: (int(r.get("line_start", 0)), int(r.get("aya_no", 0))))
    _CACHE["by_page"][page_no] = page_items
    return page_items


def demo_index(request):
    """Simple index to jump to a page number."""
    # Show a small set for quick testing
    sample_pages = list(range(1, 11))
    return render(request, "mushaf_app/demo_index.html", {"pages": sample_pages})


def demo_page(request, pno: int):
    """Render a demo page with 15 horizontal lines and clickable ayah overlays.

    Note: The dataset provides page and line ranges, not polygon coordinates.
    We approximate each Quran page as 15 equal-height lines and overlay ayah
    bands from line_start to line_end. Clicking an ayah band will POST back
    and we display what was clicked.
    """
    if pno <= 0:
        raise Http404()

    ayahs = _get_page_ayahs(pno)
    if request.method == "POST":
        clicked_id = request.POST.get("id")
        # find ayah by id for feedback
        selected = None
        for it in ayahs:
            if str(it.get("id")) == str(clicked_id):
                selected = it
                break
        return render(
            request,
            "mushaf_app/demo_page.html",
            {
                "pno": pno,
                "ayahs": ayahs,
                "clicked": selected,
                "total_lines": 15,
            },
        )

    return render(
        request,
        "mushaf_app/demo_page.html",
        {
            "pno": pno,
            "ayahs": ayahs,
            "clicked": None,
            "total_lines": 15,
            # Support zero-padded filenames like 003.svg
            "bg_filename_padded": f"{pno:03}.svg",
            "bg_filename_plain": f"{pno}.svg",
        },
    )


def ayat_embed(request):
    """Embed Ayat (KSU) official interface via iframe as-is."""
    return render(request, "mushaf_app/ayat_embed.html")


def interactive_mushaf_index(request):
    """الصفحة الرئيسية للمصحف التفاعلي"""
    return render(request, "mushaf_app/index.html")


