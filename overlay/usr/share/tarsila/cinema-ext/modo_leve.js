(() => {
  "use strict";
  const NIVEL = 2; // 1 = só backdrop-filter | 2 = + animações e sombras

  let css =
    "*{backdrop-filter:none!important;-webkit-backdrop-filter:none!important;}";

  if (NIVEL >= 2) {
    css +=
      "*,*::before,*::after{" +
      "animation-duration:.01ms!important;" +
      "animation-iteration-count:1!important;" +
      "transition-duration:.01ms!important;" +
      "scroll-behavior:auto!important;" +
      "box-shadow:none!important;" +
      "text-shadow:none!important;}";
  }

  const style = document.createElement("style");
  style.id = "tarsila-modo-leve";
  style.textContent = css;
  (document.head || document.documentElement).appendChild(style);
})();
