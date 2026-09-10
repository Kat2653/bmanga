let mode=localStorage.getItem("bmanga_reader_mode")||"vertical";
let index=0;
const r=document.getElementById("reader");
const pages=[...r.querySelectorAll(".reader-page")];

function apply(){
  r.className="reader "+mode;
  pages.forEach((page,i)=>page.classList.toggle("active",mode==="single"&&i===index));
  document.querySelectorAll("[data-reader-mode]").forEach(btn=>{
    btn.classList.toggle("active",btn.dataset.readerMode===mode);
  });
  if(mode==="single"&&pages[index]){
    pages[index].scrollIntoView({block:"center"});
  }
}
window.setReader=m=>{
  mode=m;
  localStorage.setItem("bmanga_reader_mode",m);
  apply();
};
window.toggleFull=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();

document.addEventListener("keydown",e=>{
  if(mode!=="single"||!pages.length)return;
  if(["ArrowRight","ArrowDown","PageDown"].includes(e.key)){
    e.preventDefault();
    index=Math.min(index+1,pages.length-1);
    apply();
  }
  if(["ArrowLeft","ArrowUp","PageUp"].includes(e.key)){
    e.preventDefault();
    index=Math.max(index-1,0);
    apply();
  }
});

r.querySelectorAll("img").forEach(img=>{
  img.addEventListener("error",()=>{
    img.removeAttribute("src");
    img.alt="Ảnh không tải được";
    img.classList.add("reader-image-error");
  });
});

const topBtn=document.getElementById("readerTopBtn");
if(topBtn){
  topBtn.addEventListener("click",()=>window.scrollTo({top:0,behavior:"smooth"}));
  window.addEventListener("scroll",()=>topBtn.classList.toggle("show",window.scrollY>600));
}

apply();

if(window.BMANGA_CHAPTER){
  let t;
  window.addEventListener("scroll",()=>{
    clearTimeout(t);
    t=setTimeout(()=>{
      if(!pages.length)return;
      let best=0;
      pages.forEach((page,i)=>{
        if(page.getBoundingClientRect().top<innerHeight*.6)best=i;
      });
      fetch("/api/progress/"+window.BMANGA_CHAPTER,{
        method:"POST",
        headers:{"Content-Type":"application/json","X-CSRFToken":window.BMANGA_CSRF},
        body:JSON.stringify({page_index:best})
      }).catch(()=>{});
    },700);
  });
}
