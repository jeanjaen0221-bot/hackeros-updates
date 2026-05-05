# HackerOS Dev Hub — Service Railway

Interface web de génération de monde pour HackerOS, déployée sur Railway.

## Ce que ça fait

- **Génère le monde** (worldgen pipeline Python complet) directement sur Railway
- **Stocke** `world.dat`, `missions.dat`, `market_seed.json`, `story/story.json` sur un volume persistant
- **Expose** une interface web (3 onglets : MONDE / HISTOIRE / MISSIONS) accessible depuis n'importe quel navigateur
- **Sert** les fichiers générés via HTTP pour que le jeu les synchronise au démarrage

## Déploiement Railway

### 1. Créer le service

Dans ton projet Railway :
1. **New Service → GitHub Repo** (pointer sur ce repo)
2. Dans les paramètres du service → **Settings → Source → Root Directory** : `dev_hub_server`
3. Railway détecte automatiquement `requirements.txt` et `railway.json`

### 2. Ajouter un Volume persistant

1. Dans le service : **Settings → Volumes** → `+ Add Volume`
2. Mount path : `/data`
3. La variable `STORAGE_DIR` sera automatiquement `/data`

### 3. Variables d'environnement

| Variable | Valeur | Description |
|---|---|---|
| `DEV_HUB_TOKEN` | *(ta clé secrète)* | Accès à l'UI web et à la génération |
| `STORAGE_DIR` | `/data` | Chemin du volume persistant |
| `PORT` | *(injecté par Railway)* | Port HTTP |

### 4. Accéder au Dev Hub

Ouvrir `https://<ton-service>.railway.app/?token=<DEV_HUB_TOKEN>`

Ou entrer le token sur la page de login qui s'affiche sans paramètre.

## Synchronisation côté jeu

### Activer la sync

Éditer `hacker_os/world_sync_config.json` :

```json
{
  "enabled": true,
  "dev_hub_url": "https://<ton-service>.railway.app"
}
```

À chaque démarrage du jeu, `OSKernel` vérifiera si Railway a un monde plus récent
(comparaison SHA256). Si oui, il téléchargera automatiquement les fichiers dans
`save/` avant de charger le monde. Aucun impact si Railway est hors-ligne.

### Fichiers synchronisés

- `world.dat`
- `missions.dat`
- `market_seed.json`
- `world.meta.json`
- `missions.meta.json`
- `story/story.json`

## API publique

| Route | Auth | Description |
|---|---|---|
| `GET /health` | — | Healthcheck Railway |
| `GET /api/world/meta` | — | SHA + infos du monde actuel |
| `GET /api/world/file/{name}` | — | Fichier world (téléchargement jeu) |

## API admin (token requis)

| Route | Description |
|---|---|
| `POST /api/generate` | Lance la génération worldgen |
| `GET /api/events/{job_id}` | SSE — progression en temps réel |
| `GET /api/story` | Contenu story.json |
| `GET /api/missions` | Liste des missions décodées |

## Validation locale

```bash
python dev_hub_server/test_dev_hub_server_static.py
```

## Recommandations

- **skip_fs = True** sur Railway (évite de générer des milliers de fichiers `world_fs/`)
- Générer avec une **taille L ou M** en priorité pour un monde équilibré
- `world_sync_config.json` ne doit pas être commité avec `enabled: true` dans le repo public
