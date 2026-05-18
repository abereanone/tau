document.addEventListener('DOMContentLoaded', function() {
  var nav = document.querySelector('#et-mobile-navigation nav');
  var btn = document.querySelector('#et-mobile-navigation .show-menu');
  if (!nav || !btn) return;
  var src = document.querySelector('#et-navigation ul.nav');
  if (src) {
    var clone = src.cloneNode(true);
    clone.id = 'et-extra-mobile-menu';
    clone.className = 'et_extra_mobile_menu';
    nav.appendChild(clone);
  }
  nav.querySelectorAll('.menu-item-has-children > a').forEach(function(a) {
    a.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var sub = a.parentElement.querySelector('ul');
      if (sub) sub.style.display = sub.style.display === 'block' ? 'none' : 'block';
    });
  });
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var icon = btn.querySelector('.show-menu-button');
    if (icon) icon.classList.toggle('toggled');
    nav.style.display = nav.style.display === 'block' ? 'none' : 'block';
  });
});
