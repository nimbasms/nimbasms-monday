# Frontend monday (JS)

Cette vue utilise `monday-sdk-js` en CDN. Les valeurs suivantes peuvent être
définies dans les **Settings** de l'app monday :

- `backendUrl` : URL de ton backend FastAPI.
- `phoneColumnId` : ID de la colonne téléphone.
- `messageColumnId` : ID de la colonne message.
- `senderId` : Sender ID par défaut (pré-sélectionné si présent).
- `statusColumnId` : ID de la colonne statut (optionnel).
- `statusLabel` : libellé de statut (optionnel).
- `nimbaSid` : SID Nimba pour l'utilisateur.
- `nimbaSecret` : secret token Nimba pour l'utilisateur.

Sans settings, tu peux saisir manuellement le numéro et le message.
Le Sender ID est choisi dans la liste renvoyée par `/nimba/senders`.
