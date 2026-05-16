<div align="center">

# ◈ Shimeji Desk

**Clone Python/PyQt6 de Shimeji-ee avec intégration IA**

*Des personnages Arknights qui vivent sur ton bureau — et qui peuvent te parler.*

[![Python](https://img.shields.io/badge/Python-3.10%2B-4a9eff?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.4%2B-41cd52?style=flat-square)](https://pypi.org/project/PyQt6/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-a855f7?style=flat-square)](LICENSE)

</div>

---

## 📖 Présentation

**Shimeji Desk** est un clone complet de [Shimeji-ee](https://kilkakon.com/shimeji/) écrit entièrement en Python avec PyQt6.

Les personnages se promènent sur ton bureau, grimpent aux murs, s'accrochent au plafond, sautent sur tes fenêtres ouvertes — et peuvent discuter avec toi grâce à une intégration IA complète (modèles locaux ou cloud).

**24 personnages Arknights** inclus dès l'installation.

---

## ✨ Fonctionnalités

### 🎭 Comportements (fidèles à Shimeji-ee)

| Comportement | Description |
|---|---|
| Walk / Run / Sit / Sleep | Déplacements et états de repos |
| Grab Wall / Climb Wall | Grimpe et marche sur les murs |
| Grab Ceiling / Climb Ceiling | S'accroche et marche au plafond |
| Jump To Wall | Saute vers le mur le plus proche |
| Jump To Top | Saute sur le dessus d'une fenêtre ouverte |
| Walk Along IE Ceiling | Marche sous les fenêtres |
| **Walk With IE** | Porte une fenêtre en marchant |
| **Throw IE** | Lance une fenêtre à travers l'écran |
| Chase Mouse | Suit le curseur de la souris |
| Pinched / Resisting | Réaction quand on attrape le perso |
| Interactions multi-persos | Les persos se regardent et marchent l'un vers l'autre |

### 🤖 Intelligence Artificielle

- **Chat en streaming** avec chaque personnage (double-clic)
- **7 backends supportés** — local et cloud
- **Personnalité individuelle** configurable par personnage
- **Mémoire conversationnelle** persistante (SQLite)
- Résumé automatique de l'historique toutes les 40 messages

### ⚙️ Technique

- Physique Shimeji-ee fidèle (formules Java exactes)
- Détection surfaces Win32 en temps réel (`GetWindowRect`)
- Anti-tunnel horizontal et vertical
- DPI 200% supporté
- Timer mutualisé `PreciseTimer` — 30 persos simultanés sans lag
- Cache de transparence et flip sprites optimisé
- Session sauvegardée entre les lancements

---

## 🤖 Backends IA supportés

| Backend | Type | Modèles suggérés |
|---|---|---|
| **Ollama** | Local gratuit | `llama3`, `mistral-nemo`, `gemma3` |
| **LM Studio** | Local gratuit | Tous les modèles GGUF |
| **OpenRouter** | Cloud 200+ modèles | `openai/gpt-4o-mini`, `mistralai/mistral-7b` |
| **Claude / Anthropic** | Cloud | `claude-sonnet-4-5`, `claude-haiku-4-5` |
| **Google Gemini** | Cloud | `gemini-2.0-flash`, `gemini-1.5-pro` |
| **xAI / Grok** | Cloud | `grok-3-mini`, `grok-3` |
| **Custom** | Tout endpoint OpenAI-compatible | LocalAI, vLLM, Jan… |

---

## 🖥️ Prérequis

- **Windows 10 / 11** *(utilise les APIs Win32)*
- **Python 3.10+** — [Télécharger](https://www.python.org/downloads/) *(cocher "Add Python to PATH")*
- **Ollama** *(optionnel, pour l'IA locale)* — [Télécharger](https://ollama.com/)

---

## 🚀 Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/TON_USERNAME/shimeji-desk.git
cd shimeji-desk

# 2. Installer les dépendances
double-clic sur  install.bat
```

Ou manuellement :
```bash
pip install -r requirements.txt
```

---

## ▶️ Lancement

```
double-clic sur  launch.bat
```

> Pour voir les logs d'erreur : `launch_debug.bat`

Une icône **◈** apparaît dans la barre des tâches. **Clic droit** pour ouvrir le menu.

---

## 🎮 Utilisation

| Action | Résultat |
|---|---|
| **Clic droit** sur l'icône tray | Ouvre le menu principal |
| **Double-clic** sur un personnage | Ouvre le chat IA |
| **Glisser** un personnage | Le soulever et lancer |
| **Maintenir > 5s** | Le personnage se débat |

### Menu principal

```
◈ SHIMEJI DESK
  2 personnages actifs

🎭  Choisir les personnages…
✦   Ajouter un personnage aléatoire
✦✦  Ajouter tous les personnages
─────────────────────────────
✖   Retirer tous les personnages
❄   Figer / Reprendre les animations
─────────────────────────────
💬  Ouvrir un chat IA…
─────────────────────────────
⚙   Paramètres
ℹ   À propos
─────────────────────────────
⏻   Quitter
```

---

## ➕ Ajouter des personnages

Shimeji Desk est compatible avec tous les packs **Shimeji-ee** standard.

### 📂 Structure requise

```
assets/default/img/
└── NomDuPerso/          ← nom affiché dans le sélecteur
    ├── conf/
    │   └── actions.xml  ← obligatoire
    ├── idle1.png
    ├── walk1.png
    └── ...              ← tous les sprites PNG
```

### 📥 Comment ajouter un perso

1. Télécharger un pack Shimeji (voir les sources ci-dessous)
2. Extraire l'archive
3. Copier le **dossier du personnage** dans `assets/default/img/`
4. Vérifier que `conf/actions.xml` est bien présent dans le dossier
5. Relancer Shimeji Desk → le personnage apparaît automatiquement dans le sélecteur

> ⚠️ Certains packs ont les sprites directement dans le dossier du perso,
> d'autres dans un sous-dossier `img/`. Les deux formats sont supportés.

---

### 🌐 Où trouver des packs Shimeji

#### Sites officiels / communautaires

| Site | Lien | Contenu |
|---|---|---|
| **Shimeji-ee** (site officiel) | [kilkakon.com/shimeji](https://kilkakon.com/shimeji/) | Packs vérifiés, très nombreux |
| **DeviantArt** | [deviantart.com/tag/shimeji](https://www.deviantart.com/tag/shimeji) | Milliers de persos, tous styles |
| **Itch.io** | [itch.io/search?q=shimeji](https://itch.io/search?q=shimeji) | Packs indie et originaux |
| **GitHub** | [github.com/search?q=shimeji+sprites](https://github.com/search?q=shimeji+sprites) | Packs open-source |

#### Par franchise / univers

| Franchise | Recherche suggérée |
|---|---|
| **Arknights** | `arknights shimeji deviantart` |
| **Genshin Impact** | `genshin impact shimeji` |
| **Hololive / VTubers** | `hololive shimeji pack` |
| **Anime populaires** | `[nom de l'anime] shimeji` |
| **Jeux Nintendo** | `[nom du jeu/perso] shimeji sprite` |

#### Collections recommandées

- 🔗 [Shimeji-ee Community Packs](https://kilkakon.com/shimeji/#downloads) — packs officiellement compatibles
- 🔗 [Shimeji sur DeviantArt](https://www.deviantart.com/search?q=shimeji+pack) — filtrer par "Newest" pour les plus récents

---

### ✅ Vérifier la compatibilité

Un pack est compatible si :
- Il contient un fichier `conf/actions.xml`
- Les sprites sont en `.png`
- Il est prévu pour **Shimeji-ee** (pas l'ancien Shimeji 1.0)

> 💡 Si un perso ne bouge pas correctement après l'ajout, son `actions.xml`
> utilise peut-être des actions non standard. Ouvre une issue sur ce dépôt
> avec le nom du pack et on regardera ensemble.

---

## 🎭 Personnages inclus

<details>
<summary>Voir les 24 personnages Arknights</summary>

| | | | |
|---|---|---|---|
| Amiya | Ansel | Blue Poison | Ch'en |
| Exusiai | Eyjafjalla | Faust ✨ | FrostNova ✨ |
| Hoshiguma | Ifrit | Lappland | Magallan ✨ |
| Meteorite | Mostima | Projekt Red | Saria |
| Schwarz | Shining | Siege | Silence |
| SilverAsh | Skadi ✨ | Sora ✨ | Texas |

✨ = animations spéciales uniques

</details>

### Animations spéciales

| Personnage | Particularité |
|---|---|
| **FrostNova** | Rebond à l'atterrissage, chute douce, animation de réveil |
| **Faust** | Téléportation depuis les murs, animations de saut et d'accrochage |
| **Skadi** | Sort ses épées (animation Special) |
| **Sora** | Portail à l'atterrissage |
| **Magallan** | Chute lente comme un ballon |

---

## ⚙️ Configuration

Tout se configure depuis **Paramètres** (clic droit → icône tray).

### Onglets disponibles

| Onglet | Contenu |
|---|---|
| 🤖 IA | Backend, clé API, modèle |
| 🎭 Personnage | Personnalité par perso, échelle |
| ⚙ Comportements | Activer/désactiver WalkWithIE, Jump, Special… |
| 🌍 Physique | Vitesse, FPS, gravité, nb max persos |
| 🐞 Debug | Overlay état/position/vélocité |

### IA locale avec Ollama

```bash
# Installer un modèle
ollama pull mistral-nemo

# Ollama se lance automatiquement au démarrage de Windows
```

Puis dans Paramètres → IA → onglet **Ollama** : URL `http://localhost:11434`.

### IA cloud (exemple Claude)

Dans Paramètres → IA → onglet **Claude** :
- Clé API : `sk-ant-...` (depuis [console.anthropic.com](https://console.anthropic.com))
- Modèle : `claude-haiku-4-5` (rapide) ou `claude-sonnet-4-5` (meilleur)

---

## 🗂️ Structure du projet

```
shimeji-desk/
├── launch.bat              ← Lancer l'application
├── launch_debug.bat        ← Lancer avec console de debug
├── install.bat             ← Installer les dépendances
├── main.py
├── config.py
├── config.json
├── requirements.txt
├── assets/
│   └── default/img/        ← Dossiers personnages
│       ├── Amiya/
│       │   ├── conf/actions.xml
│       │   └── *.png
│       └── ...
├── core/
│   ├── behavior.py         ← Moteur comportemental
│   ├── physics.py          ← Physique (gravité, surfaces)
│   ├── sprite_engine.py    ← Chargement XML + animations
│   ├── mascot_controller.py
│   ├── window_detector.py  ← Détection fenêtres Win32
│   └── monitor_manager.py
├── ui/
│   ├── mascot_window.py    ← Fenêtre personnage PyQt6
│   ├── chat_window.py      ← Interface chat IA
│   ├── tray_icon.py        ← Menu tray + Paramètres
│   └── character_selector.py
└── ai/
    ├── client.py           ← Client multi-backend
    └── memory.py           ← Mémoire SQLite
```

---

## 🛠️ Développement

```bash
# Dépendances
pip install -r requirements.txt

# Lancer en mode debug
python main.py

# Activer l'overlay debug
# Paramètres → Debug → cocher "Afficher overlay debug"
```

---

## 📄 Licence

MIT — voir [LICENSE](LICENSE)

---

## 🙏 Crédits

- **Sprites** : Pack Arknights Shimeji v1.1 — auteur original inconnu
- **Shimeji-ee** : [kilkakon](https://kilkakon.com/shimeji/) — projet Java original dont ce projet s'inspire
- **Développé avec** : [Claude](https://claude.ai) (Anthropic)

---

<div align="center">

*Fait avec ❤️ et beaucoup de `GetWindowRect()`*

</div>
