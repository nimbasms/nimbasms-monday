(function () {
  var api = window.NimbaApi;
  var monday = api.monday;

  var messageInput = document.getElementById("messageInput");
  var phoneInput = document.getElementById("phoneInput");
  var senderSelect = document.getElementById("senderSelect");
  var sendButton = document.getElementById("sendButton");
  var reloadButton = document.getElementById("reloadButton");
  var statusLine = document.getElementById("status");
  var recipientHelp = document.getElementById("recipientHelp");
  var setupNotice = document.getElementById("setupNotice");
  var composer = document.getElementById("composer");
  var meter = document.getElementById("meter");
  var meterUnits = document.getElementById("meterUnits");
  var meterSegments = document.getElementById("meterSegments");
  var meterEncoding = document.getElementById("meterEncoding");

  var context = {};
  var settings = { phoneColumnId: "" };

  function setStatus(text, tone) {
    statusLine.textContent = text || "";
    statusLine.dataset.tone = tone || "info";
  }

  function updateMeter() {
    var reading = window.NimbaSms.measure(messageInput.value);
    meterUnits.textContent = reading.units;
    meterSegments.textContent = reading.segments;
    meter.dataset.encoding = reading.encoding;
    meterEncoding.textContent =
      reading.encoding === "ucs2"
        ? "Caracteres speciaux : 70 par segment"
        : "Alphabet standard : 160 par segment";
  }

  function currentRecipients() {
    return phoneInput.value
      .split(/[\n,;]+/)
      .map(function (value) { return value.trim(); })
      .filter(function (value) { return value.length > 0; });
  }

  function updateRecipientCount() {
    var count = currentRecipients().length;
    recipientHelp.textContent =
      count === 0
        ? "Un numero par ligne."
        : count + " destinataire(s) — un numero par ligne.";
  }

  function selectedItemIds() {
    var ids = context.selectedItemsIds || context.selectedItemIds || context.selectedItems || [];
    if (context.itemId && !ids.length) ids = [context.itemId];
    return ids.map(String);
  }

  async function loadSelection() {
    var ids = selectedItemIds();
    if (!ids.length || !settings.phoneColumnId) {
      updateRecipientCount();
      return;
    }

    // `[ID!]` et non `[Int]` : depuis l'API 2023-10 les identifiants sont des ID.
    var query =
      "query ($itemIds: [ID!]) { items(ids: $itemIds) { id column_values { id text } } }";

    try {
      var result = await monday.api(query, { variables: { itemIds: ids } });
      var items = (result && result.data && result.data.items) || [];
      var numbers = [];
      items.forEach(function (item) {
        (item.column_values || []).forEach(function (column) {
          if (column.id !== settings.phoneColumnId || !column.text) return;
          column.text.split(/[\n,;]+/).forEach(function (value) {
            var trimmed = value.trim();
            if (trimmed && numbers.indexOf(trimmed) === -1) numbers.push(trimmed);
          });
        });
      });
      phoneInput.value = numbers.join("\n");
      updateRecipientCount();
    } catch (error) {
      setStatus("Lecture des elements impossible : " + error.message, "error");
    }
  }

  function fillSenders(names, preferred) {
    senderSelect.innerHTML = "";
    if (!names.length) {
      var empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "Aucun expediteur valide sur ce compte";
      senderSelect.appendChild(empty);
      return;
    }
    names.forEach(function (name) {
      var option = document.createElement("option");
      option.value = name;
      option.textContent = name;
      senderSelect.appendChild(option);
    });
    if (preferred && names.indexOf(preferred) !== -1) senderSelect.value = preferred;
  }

  async function loadAccountState() {
    try {
      var state = await api.get("/api/credentials");
      if (!state.configured) {
        setupNotice.classList.remove("hidden");
        composer.classList.add("hidden");
        return;
      }
      setupNotice.classList.add("hidden");
      composer.classList.remove("hidden");
      fillSenders(state.sender_names || [], state.default_sender);
    } catch (error) {
      setStatus(error.message, "error");
    }
  }

  sendButton.addEventListener("click", async function () {
    var message = messageInput.value.trim();
    var recipients = currentRecipients();

    if (!message) return setStatus("Ecrivez le message avant d'envoyer.", "error");
    if (!recipients.length) return setStatus("Ajoutez au moins un destinataire.", "error");

    sendButton.disabled = true;
    setStatus("Envoi en cours…", "info");

    try {
      var result = await api.post("/api/send", {
        message: message,
        recipients: recipients,
        sender_name: senderSelect.value || null,
        board_id: context.boardId ? String(context.boardId) : null,
      });
      var text = "SMS envoye a " + result.sent_count + " destinataire(s).";
      if (result.rejected && result.rejected.length) {
        text += " Numeros ignores : " + result.rejected.join(", ") + ".";
      }
      setStatus(text, "success");
    } catch (error) {
      setStatus(error.message, "error");
    } finally {
      sendButton.disabled = false;
    }
  });

  reloadButton.addEventListener("click", loadSelection);
  messageInput.addEventListener("input", updateMeter);
  phoneInput.addEventListener("input", updateRecipientCount);

  monday.listen("context", function (res) {
    context = res.data || {};
    loadSelection();
  });

  monday.listen("settings", function (res) {
    settings = Object.assign(settings, res.data || {});
    loadSelection();
  });

  updateMeter();
  updateRecipientCount();
  loadAccountState();
})();
