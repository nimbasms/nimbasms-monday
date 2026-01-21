const monday = window.mondaySdk();

const messageInput = document.getElementById("messageInput");
const senderSelect = document.getElementById("senderSelect");
const phoneInput = document.getElementById("phoneInput");
const sendButton = document.getElementById("sendButton");
const statusLabel = document.getElementById("status");
const selectedCount = document.getElementById("selectedCount");
const numbersCount = document.getElementById("numbersCount");

let context = {};
let settings = {
  backendUrl: "",
  phoneColumnId: "",
  messageColumnId: "",
  senderId: "",
  nimbaSid: "",
  nimbaSecret: "",
};

const showStatus = (message, type = "info") => {
  statusLabel.textContent = message;
  statusLabel.dataset.type = type;
};

const populateSenderOptions = (senders) => {
  senderSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Sélectionner un expéditeur";
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

const resolveSelectedItemIds = () => {
  return (
    context.selectedItemsIds ||
    context.selectedItemIds ||
    context.selectedItems ||
    []
  );
};

const fetchSelectedItems = async (itemIds) => {
  if (!itemIds.length) return [];
  const query = `query ($itemIds: [Int]) {
    items(ids: $itemIds) {
      id
      name
      column_values { id text }
    }
  }`;
  const result = await monday.api(query, { variables: { itemIds } });
  return result?.data?.items || [];
};

const extractNumbers = (items) => {
  if (!settings.phoneColumnId) return [];
  const numbers = [];
  items.forEach((item) => {
    const column = item.column_values.find(
      (entry) => entry.id === settings.phoneColumnId
    );
    if (column?.text) {
      column.text
        .split(/[\n,]+/)
        .map((value) => value.trim())
        .filter((value) => value.length > 0)
        .forEach((value) => numbers.push(value));
    }
  });
  return [...new Set(numbers)];
};

const updateCounters = (itemsCount, numbers) => {
  selectedCount.textContent = `Items sélectionnés: ${itemsCount}`;
  numbersCount.textContent = `Numéros détectés: ${numbers.length}`;
};

const hydrateFromSelection = async () => {
  const itemIds = resolveSelectedItemIds();
  if (!itemIds.length) {
    updateCounters(0, []);
    return;
  }
  const items = await fetchSelectedItems(itemIds);
  const numbers = extractNumbers(items);
  phoneInput.value = numbers.join("\n");
  updateCounters(items.length, numbers);
};

const buildPayload = () => {
  const phone = phoneInput.value
    .split(/\n+/)
    .map((value) => value.trim())
    .filter((value) => value.length > 0);

  return {
    phone_number: phone,
    message: messageInput.value.trim(),
    sender_id: senderSelect.value || settings.senderId || undefined,
    nimba_sid: settings.nimbaSid || undefined,
    nimba_secret: settings.nimbaSecret || undefined,
    board_id: context.boardId,
  };
};

monday.listen("context", (res) => {
  context = res.data || {};
  hydrateFromSelection();
});

monday.listen("settings", (res) => {
  settings = { ...settings, ...(res.data || {}) };
  loadSenders();
  hydrateFromSelection();
});

sendButton.addEventListener("click", async () => {
  try {
    if (!settings.backendUrl) {
      showStatus("Configurez l'URL du backend dans les settings.", "error");
      return;
    }

    const payload = buildPayload();
    if (!payload.phone_number.length || !payload.message) {
      showStatus("Numéros ou message manquant.", "error");
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
