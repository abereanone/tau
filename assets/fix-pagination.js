// Replace any .pagination lists with static links to page/N/index.html
(function(){
  const totalPages = 18;
  function buildPaginationHtml(){
    let html = '';
    html += '<li class="prev static-arrow"><a class="prev static-arrow" href="../page/1/index.html"></a></li>';
    for(let i=1;i<=totalPages;i++){
      html += '<li>';
      html += '<a href="../page/'+i+'/index.html" class="static-pagination-page pagination-page-'+i+'" data-page="'+i+'">'+i+'</a>';
      html += '</li>';
    }
    html += '<li class="next static-arrow"><a class="next static-arrow" href="../page/2/index.html"></a></li>';
    return html;
  }

  function replaceAll(){
    const lists = document.querySelectorAll('ul.pagination');
    lists.forEach(function(ul){
      try{
        // only replace if not already our static pagination
        if(ul.dataset.fixed === '1') return;
        ul.innerHTML = buildPaginationHtml();
        ul.dataset.fixed = '1';
      }catch(e){console.error(e)}
    });
  }

  // run on load and a few times after to catch late rewrites
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ replaceAll(); setTimeout(replaceAll, 300); setTimeout(replaceAll, 1200); });
  } else { replaceAll(); setTimeout(replaceAll,300); setTimeout(replaceAll,1200); }

  // observe DOM changes and reapply
  const mo = new MutationObserver(function(muts){ replaceAll(); });
  mo.observe(document.body, { childList:true, subtree:true });
})();
