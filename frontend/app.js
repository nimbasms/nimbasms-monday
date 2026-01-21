const monday = window.mondaySdk();

const phoneInput = document.getElementById("phoneInput");
const messageInput = document.getElementById("messageInput");
const senderSelect = document.getElementById("senderSelect");
const sendButton = document.getElementById("sendButton");
const statusLabel = document.getElementById("status");

let context = {};
let settings = {
  backendUrl: "",
  phoneColumnId: "",
  messageColumnId: "",
  senderId: "",
  statusColumnId: "",
  statusLabel: "SMS envoyé",
  nimbaSid: "",
  nimbaSecret: "",
};

monday.listen("context", (res) => {
  context = res.data || {};
});

monday.listen("settings", (res) => {
  settings = { ...settings, ...(res.data || {}) };
  loadSenders();
});

const showStatus = (message, type = "info") => {
  statusLabel.textContent = message;
  statusLabel.dataset.type = type;
};

const fetchItemData = async () => {
  if (!context.itemId) return {};
  const query = `query ($itemId: [Int]) {
    items(ids: $itemId) {
      id
      name
      column_values { id text }
    }
  }`;
  const result = await monday.api(query, { variables: { itemId: [context.itemId] } });
  const item = result?.data?.items?.[0];
  return item || {};
};

const resolveColumnValue = (columns, columnId) => {
  if (!columnId) return "";
  const column = columns.find((entry) => entry.id === columnId);
  return column?.text || "";
};

const buildPayload = async () => {
  const item = await fetchItemData();
  const columns = item.column_values || [];

  const rawPhone =
    phoneInput.value.trim() ||
    resolveColumnValue(columns, settings.phoneColumnId);
  const phone = rawPhone
    .split(/\n+/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
  const message =
    messageInput.value.trim() ||
    resolveColumnValue(columns, settings.messageColumnId);
  const senderId = senderSelect.value || settings.senderId;

  return {
    phone_number: phone,
    message,
    sender_id: senderId || undefined,
    nimba_sid: settings.nimbaSid || undefined,
    nimba_secret: settings.nimbaSecret || undefined,
    board_id: context.boardId,
    item_id: context.itemId,
    status_column_id: settings.statusColumnId || undefined,
    status_label: settings.statusLabel || undefined,
  };
};

const populateSenderOptions = (senders) => {
  senderSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Sélectionner un sender";
  senderSelect.appendChild(placeholder);

  senders.forEach((sender) => {
    const option = document.createElement("option");
    option.value = sender;
    option.textContent = sender;
    senderSelect.appendChild(option);
  });

  if (settings.senderId) {
    senderSelect.value = settings.senderId;
  }
};

const loadSenders = async () => {
  if (!settings.backendUrl) return;
  try {
    const response = await fetch(`${settings.backendUrl}/sendernames`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        nimba_sid: settings.nimbaSid || undefined,
        nimba_secret: settings.nimbaSecret || undefined,
      }),
    });

    if (!response.ok) {
      return;
    }
    const result = await response.json();
    if (result.status === "ok") {
      populateSenderOptions(result.senders || []);
    }
  } catch (error) {
    showStatus(`Erreur senders: ${error.message}`, "error");
  }
};

sendButton.addEventListener("click", async () => {
  try {
    if (!settings.backendUrl) {
      showStatus("Configurez l'URL du backend dans les settings.", "error");
      return;
    }

    const payload = await buildPayload();
    if (!payload.phone_number || !payload.message) {
      showStatus("Numéro ou message manquant.", "error");
      return;
    }

    showStatus("Envoi en cours...", "info");

    const response = await fetch(`${settings.backendUrl}/monday/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });

    if (!response.ok) {
      const text = await response.text();
      showStatus(`Erreur: ${text}`, "error");
      return;
    }

    const result = await response.json();
    if (result.status === "sent") {
      showStatus("SMS envoyé.", "success");
    } else {
      showStatus(`Statut: ${result.status}`, "error");
    }
  } catch (error) {
    showStatus(`Erreur: ${error.message}`, "error");
  }
});
