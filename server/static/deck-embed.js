/* Inline decks: render each deck in a fixed 1120x630 viewport and scale it to the frame, plus fullscreen. */
(() => {
  const W = 1120;

  document.querySelectorAll('[data-deck-embed]').forEach(fig => {
    const stage = fig.querySelector('.deck-stage');
    const frame = stage.querySelector('iframe');
    const button = fig.querySelector('[data-deck-fullscreen]');

    const fit = () => frame.style.setProperty('--deck-scale', String(stage.clientWidth / W));
    fig.classList.add('scaled');
    fit();
    if ('ResizeObserver' in window) new ResizeObserver(fit).observe(stage);
    else addEventListener('resize', fit);

    const request = stage.requestFullscreen || stage.webkitRequestFullscreen;
    const canFullscreen = request && (document.fullscreenEnabled || document.webkitFullscreenEnabled);
    button.addEventListener('click', () => {
      if (!canFullscreen) {
        window.open(frame.src, '_blank', 'noopener');
        return;
      }
      Promise.resolve(request.call(stage)).then(() => frame.focus(), () => window.open(frame.src, '_blank', 'noopener'));
    });

    let was = false;
    const sync = () => {
      const on = (document.fullscreenElement || document.webkitFullscreenElement) === stage;
      if (on === was) return;
      was = on;
      button.setAttribute('aria-pressed', String(on));
      if (!on) { fit(); button.focus({ preventScroll: true }); }
    };
    document.addEventListener('fullscreenchange', sync);
    document.addEventListener('webkitfullscreenchange', sync);
  });
})();
