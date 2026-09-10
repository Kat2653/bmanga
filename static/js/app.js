(function(){
  const body=document.body;
  const menuToggle=document.querySelector('[data-menu-toggle]');
  const menuPanel=document.querySelector('[data-menu-panel]');
  const overlay=document.querySelector('[data-menu-overlay]');
  const searchToggle=document.querySelector('[data-search-toggle]');
  const searchPanel=document.querySelector('[data-search-panel]');
  const loginModal=document.querySelector('[data-login-modal]');

  function setMenu(open){
    if(!menuPanel)return;
    menuPanel.classList.toggle('open',open);
    overlay?.classList.toggle('show',open);
    body.classList.toggle('menu-open',open);
    if(open) setSearch(false);
    const icon=menuToggle?.querySelector('span');
    if(icon) icon.textContent=open?'×':'☰';
  }
  function setSearch(open){
    if(!searchPanel)return;
    searchPanel.classList.toggle('open',open);
    searchToggle?.classList.toggle('active',open);
    if(open){
      setMenu(false);
      setTimeout(()=>searchPanel.querySelector('input')?.focus(),60);
    }
  }
  function setLogin(open){
    if(!loginModal)return;
    loginModal.classList.toggle('open',open);
    loginModal.setAttribute('aria-hidden',open?'false':'true');
    body.classList.toggle('modal-open',open);
    if(open){
      setMenu(false); setSearch(false);
      setTimeout(()=>loginModal.querySelector('input[name="username"]')?.focus(),80);
    }
  }

  menuToggle?.addEventListener('click',()=>setMenu(!menuPanel.classList.contains('open')));
  overlay?.addEventListener('click',()=>setMenu(false));
  menuPanel?.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>setMenu(false)));
  searchToggle?.addEventListener('click',()=>setSearch(!searchPanel.classList.contains('open')));
  document.querySelectorAll('[data-login-toggle]').forEach(el=>el.addEventListener('click',()=>setLogin(true)));
  document.querySelectorAll('[data-login-close]').forEach(el=>el.addEventListener('click',()=>setLogin(false)));
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){setMenu(false);setSearch(false);setLogin(false)}});

  function initCollapsible(box){
    const content=box.querySelector('.desc-content');
    const btn=box.parentElement.querySelector('[data-collapsible-toggle]');
    if(!content||!btn)return;
    const collapsedHeight=window.innerWidth<=700?120:150;
    box.classList.remove('expanded'); box.style.maxHeight='none';
    if(content.scrollHeight<=collapsedHeight+8){btn.hidden=true;box.classList.remove('collapsed');return;}
    btn.hidden=false;box.classList.add('collapsed');box.style.maxHeight=collapsedHeight+'px';btn.textContent='Xem thêm';
    btn.onclick=function(){const expanded=box.classList.toggle('expanded');box.style.maxHeight=expanded?content.scrollHeight+'px':collapsedHeight+'px';btn.textContent=expanded?'Ẩn bớt':'Xem thêm';};
  }
  function bootCollapsibles(){document.querySelectorAll('[data-collapsible]').forEach(initCollapsible)}
  let resizeTimer; window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(bootCollapsibles,120)});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',bootCollapsibles);else bootCollapsibles();
})();