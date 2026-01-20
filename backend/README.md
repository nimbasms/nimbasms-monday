# Backend FastAPI (Nimba SMS + monday.com)

## Variables d'environnement

- `NIMBA_BASE_URL` : URL de base de l'API Nimba SMS.
- `NIMBA_SID` : identifiant SID Nimba.
- `NIMBA_SECRET` : secret token Nimba.
- `NIMBA_SENDER_ID` : (optionnel) sender par défaut.
- `NIMBA_SEND_PATH` : (optionnel) chemin d'envoi, défaut `/v1/messages`.
- `NIMBA_SENDERS_PATH` : (optionnel) chemin pour la liste des senders, défaut `/v1/sendernames`.
- `MONDAY_API_TOKEN` : (optionnel) pour écrire sur les boards (updates/colonnes).
- `MONDAY_SIGNING_SECRET` : (optionnel) pour valider les signatures webhook.
- `REQUEST_TIMEOUT_SECONDS` : (optionnel) timeout HTTP en secondes.

## Endpoints

- `GET /health` : check simple.
- `POST /monday/automation` : endpoint pour recettes d'automatisation.
- `POST /monday/action` : endpoint pour action one-click.
- `POST /nimba/dlr` : réception des statuts Nimba (DLR).
- `POST /nimba/senders` : retourne la liste des senders.
- `POST /sendernames` : alias pour la liste des senders.

## Format attendu (exemple)

```json
{
  "payload": {
    "phone_number": "+2246XXXXXXX",
    "message": "Bonjour depuis monday",
    "sender_id": "Nimba",
    "nimba_sid": "sid_utilisateur",
    "nimba_secret": "secret_utilisateur",
    "board_id": 123456789,
    "item_id": 987654321,
    "status_column_id": "status",
    "status_label": "SMS envoyé",
    "update_body": "SMS envoyé par l'app",
    "dry_run": false
  }
}
```

Le backend accepte aussi `phone`, `to`, `body`, `text`, `sender` si tes clés sont différentes.
