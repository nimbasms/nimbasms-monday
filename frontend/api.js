/* Petit client HTTP partage par les deux vues.
   Chaque appel porte le sessionToken monday : le backend ne fait jamais
   confiance a un identifiant venu du navigateur sans cette signature. */
(function (global) {
  var monday = global.mondaySdk();

  function backendUrl() {
    var url = global.NIMBA_BACKEND_URL || "";
    if (!url) throw new Error("L'URL du backend n'est pas configuree (config.js).");
    return url.replace(/\/$/, "");
  }

  async function sessionToken() {
    var result = await monday.get("sessionToken");
    if (!result || !result.data) throw new Error("Session monday indisponible.");
    return result.data;
  }

  async function request(method, path, body) {
    var token = await sessionToken();
    var response = await fetch(backendUrl() + path, {
      method: method,
      headers: { Authorization: token, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (response.status === 204) return null;

    var payload = null;
    try {
      payload = await response.json();
    } catch (error) {
      payload = null;
    }

    if (!response.ok) {
      var detail = payload && payload.detail ? payload.detail : "Erreur " + response.status + ".";
      var failure = new Error(detail);
      failure.status = response.status;
      throw failure;
    }
    return payload;
  }

  global.NimbaApi = {
    monday: monday,
    get: function (path) { return request("GET", path); },
    post: function (path, body) { return request("POST", path, body); },
    put: function (path, body) { return request("PUT", path, body); },
    del: function (path) { return request("DELETE", path); },
  };
})(window);
