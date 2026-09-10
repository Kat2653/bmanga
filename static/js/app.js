(function(){
  const body = document.body;
  const toggle = document.querySelector('[data-menu-toggle]');
  const panel = document.querySelector('[data-menu-panel]');
  const overlay = document.querySelector('[data-menu-overlay]');

  function setMenu(open){
    if(!panel) return;
    panel.classList.toggle('open', open);
    if(overlay) overlay.classList.toggle('show', open);
    body.classList.toggle('menu-open', open);
  }

  if(toggle && panel){
    toggle.addEventListener('click', ()=> setMenu(!panel.classList.contains('open')));
    if(overlay) overlay.addEventListener('click', ()=> setMenu(false));
    panel.querySelectorAll('a').forEach(a=>a.addEventListener('click', ()=> setMenu(false)));
  }

  function initCollapsible(box){
    const content = box.querySelector('.desc-content');
    const btn = box.parentElement.querySelector('[data-collapsible-toggle]');
    if(!content || !btn) return;

    const mobile = window.innerWidth <= 700;
    const collapsedHeight = mobile ? 120 : 150;
    box.classList.remove('expanded');
    box.style.maxHeight = 'none';

    if(content.scrollHeight <= collapsedHeight + 8){
      btn.hidden = true;
      box.classList.remove('collapsed');
      box.style.maxHeight = 'none';
      return;
    }

    btn.hidden = false;
    box.classList.add('collapsed');
    box.style.maxHeight = collapsedHeight + 'px';
    btn.textContent = 'Xem thêm';

    btn.onclick = function(){
      const expanded = box.classList.toggle('expanded');
      if(expanded){
        box.style.maxHeight = content.scrollHeight + 'px';
        btn.textContent = 'Ẩn bớt';
      }else{
        box.style.maxHeight = collapsedHeight + 'px';
        btn.textContent = 'Xem thêm';
      }
    };
  }

  function bootCollapsibles(){
    document.querySelectorAll('[data-collapsible]').forEach(initCollapsible);
  }

  window.addEventListener('resize', ()=> bootCollapsibles());
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', bootCollapsibles);
  }else{
    bootCollapsibles();
  }
})();