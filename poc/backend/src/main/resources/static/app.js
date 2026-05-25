// Hafnarvaktin live-feed view — crossfade between the two cameras, driven by
// the uiverse flip-switch. Both MJPEG streams stay loaded; we fade opacity.
// Auto-advances every 6 s; flicking the switch overrides and resets the timer.
(function () {
  const imgs = Array.from(document.querySelectorAll('.frame__img'));
  const toggle = document.getElementById('cam-toggle');
  const nameEl = document.getElementById('cam-name');
  const NAMES = ['Sundahöfn N', 'Sundahöfn S'];
  const INTERVAL = 6000;
  let i = 0;
  let timer;

  function show(n) {
    i = (n + imgs.length) % imgs.length;
    imgs.forEach((im, k) => im.classList.toggle('is-active', k === i));
    if (toggle) toggle.checked = (i === 1);          // S = checked
    if (nameEl) nameEl.textContent = NAMES[i] || '';
  }
  function start() { timer = setInterval(() => show(i + 1), INTERVAL); }
  function reset() { clearInterval(timer); start(); }

  if (toggle) toggle.addEventListener('change', () => { show(toggle.checked ? 1 : 0); reset(); });

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) clearInterval(timer); else reset();
  });

  show(0);
  start();
})();
