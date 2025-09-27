// Raccourcis clavier globaux : N (suivant), P (précédent), S (sauvegarder)
(function(){
  document.addEventListener('keydown', function(e){
    const id = (e.key === 'n' || e.key === 'N') ? 'next-image'
            : (e.key === 'p' || e.key === 'P') ? 'prev-image'
            : (e.key === 's' || e.key === 'S') ? 'save-annotation'
            : null;
    if(!id) return;
    const el = document.getElementById(id);
    if(el){ e.preventDefault(); el.click(); }
  });
})();
