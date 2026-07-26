// ---------------------------------------------------------------------------
// Tarsila — acertos do YouTube em modo mobile.
//
// 1) CURSOR. Como anunciamos suporte a toque (--touch-events, necessario para
//    os gestos funcionarem), o YouTube assume aparelho de toque e aplica
//    "cursor: none" no player -- num aparelho de toque nao existe ponteiro.
//    Aqui numa TV com mouse isso some com o ponteiro em cima do video.
//    Devolvemos o cursor, MAS so fora de tela cheia: em tela cheia o
//    desaparecimento automatico e desejavel.
//
// 2) SOM. O YouTube mobile comeca MUDO de proposito (e o que permite tocar
//    sozinho sem gesto). Aqui o usuario sempre quer som. Tiramos o mudo assim
//    que a reproducao comeca -- ou seja, DEPOIS do gesto dele, quando a
//    politica de autoplay ja foi satisfeita e desmutar e permitido.
//    Tambem gravamos a preferencia onde o proprio YouTube a le, para ele
//    lembrar sozinho nas proximas vezes.
// ---------------------------------------------------------------------------
(() => {
  "use strict";

  // --- 1) cursor de volta -------------------------------------------------
  const css = document.createElement("style");
  css.textContent =
    ":not(:fullscreen) #movie_player, :not(:fullscreen) #movie_player *," +
    ":not(:fullscreen) .html5-video-player, :not(:fullscreen) .html5-video-player *," +
    ":not(:fullscreen) video { cursor: auto !important; }";
  (document.head || document.documentElement).appendChild(css);

  // --- 2) som ligado ------------------------------------------------------
  const LEMBRAR = () => {
    try {
      localStorage.setItem("yt-player-volume", JSON.stringify({
        data: JSON.stringify({ volume: 100, muted: false }),
        expiration: Date.now() + 30 * 24 * 3600 * 1000,
        creation: Date.now()
      }));
    } catch (e) {}
  };

  // NAO usar disparo unico: medido, o YouTube RE-MUTA o video depois (troca de
  // qualidade, mudanca de faixa, navegacao interna da SPA). Entao insistimos
  // enquanto estiver tocando, e so quando de fato esta mudo -- sem tocar no
  // volume que o usuario tiver escolhido.
  const soltarSom = (v) => {
    if (!v || v.paused) return;        // so depois que comecou a tocar
    if (v.muted) { v.muted = false; LEMBRAR(); }
    if (v.volume === 0) { v.volume = 1; LEMBRAR(); }
  };

  setInterval(() => soltarSom(document.querySelector("video")), 700);
  LEMBRAR();
})();
