(function(){
  let pages=[], idx=0, chosenHalf=null;
  const img=document.getElementById('pageImg');
  const base=img?.dataset?.base || '/page-svg/';
  const layer=document.getElementById('ayahLayer');
  const halfOverlay=document.getElementById('halfOverlay');
  const prevBtn=document.getElementById('prevBtn');
  const nextBtn=document.getElementById('nextBtn');

  function setPage(i){
    if(!pages.length) return;
    idx=Math.max(0, Math.min(i, pages.length-1));
    const p=pages[idx];
    img.src = base + p + ".svg";
    chosenHalf=null; layer.innerHTML=''; layer.hidden=true; halfOverlay.hidden=false;
    prevBtn.disabled = idx<=0; nextBtn.disabled = idx>=pages.length-1;
  }

  function nav(dir){ setPage(dir==='prev'?idx-1:idx+1); }
  prevBtn?.addEventListener('click', ()=>nav('prev'));
  nextBtn?.addEventListener('click', ()=>nav('next'));
  window.addEventListener('keydown',(e)=>{ if(e.key==='ArrowLeft') nav('next'); if(e.key==='ArrowRight') nav('prev'); });

  halfOverlay?.addEventListener('click',(e)=>{
    const btn=e.target.closest('.half-btn'); if(!btn) return;
    chosenHalf=btn.dataset.half; halfOverlay.hidden=true;
    // TODO: اطلب تظليل/آيات نصف الصفحة من API أخرى عندك إن وُجدت
  });

  async function bootstrap(){
    try{
      const qid = window.QUARTER_ID;
      const res = await fetch(`/api/quarter/${qid}/pages/`);
      const data = await res.json();
      pages = Array.isArray(data.pages) ? data.pages : [];
      setPage(0);
    }catch(_e){ /* ignore */ }
  }
  bootstrap();
})();
