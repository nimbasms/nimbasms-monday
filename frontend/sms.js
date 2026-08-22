/* Comptage de segments SMS (GSM 03.38 vs UCS-2).
   Un message qui sort du jeu GSM bascule en UCS-2 et tombe a 70 caracteres
   par segment : c'est la principale cause de facture inattendue. */
(function (global) {
  var GSM =
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
  var GSM_EXTENDED = "^{}\\[~]|€";

  function isGsm(text) {
    for (var i = 0; i < text.length; i++) {
      var char = text[i];
      if (GSM.indexOf(char) === -1 && GSM_EXTENDED.indexOf(char) === -1) return false;
    }
    return true;
  }

  function gsmLength(text) {
    var length = 0;
    for (var i = 0; i < text.length; i++) {
      length += GSM_EXTENDED.indexOf(text[i]) !== -1 ? 2 : 1;
    }
    return length;
  }

  function measure(text) {
    text = text || "";
    if (!text.length) {
      return { encoding: "gsm7", units: 0, segments: 0, perSegment: 160, remaining: 160 };
    }
    var gsm = isGsm(text);
    var units = gsm ? gsmLength(text) : text.length;
    var single = gsm ? 160 : 70;
    var multi = gsm ? 153 : 67;
    var segments = units <= single ? 1 : Math.ceil(units / multi);
    var perSegment = segments > 1 ? multi : single;
    return {
      encoding: gsm ? "gsm7" : "ucs2",
      units: units,
      segments: segments,
      perSegment: perSegment,
      remaining: segments * perSegment - units,
    };
  }

  global.NimbaSms = { measure: measure };
})(window);
