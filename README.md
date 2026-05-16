<div align="center">

# ◈ Shimeji Desk

**Clone Python/PyQt6 de Shimeji-ee avec intégration IA**

*Des personnages Arknights qui vivent sur ton bureau — parlent entre eux, jouent, dorment, et peuvent discuter avec toi.*

<img width="1038" height="822" alt="image" src="https://github.com/user-attachments/assets/8af3ec95-05f7-489f-98f0-dffa1cb8164f" />

[![PyQt6](https://img.shields.io/badge/PyQt6-6.4%2B-41cd52?style=flat-square)](https://pypi.org/project/PyQt6/)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-a855f7?style=flat-square)](LICENSE)
[![Version](https://img.shields.io/badge/Version-2.0-ff6a3d?style=flat-square)](https://github.com/nolhanjarrige-ctrl/shimeji-desk)

</div>

---

## 📖 Présentation

**Shimeji Desk** est un clone complet de [Shimeji-ee](https://kilkakon.com/shimeji/) écrit entièrement en Python avec PyQt6.

Les personnages se promènent sur ton bureau, grimpent aux murs, s'accrochent au plafond, sautent sur tes fenêtres ouvertes — et ont une **vie sociale** : ils se parlent via l'IA, jouent ensemble, dorment la nuit, et réagissent à l'heure de la journée.

**24 personnages Arknights** inclus avec personnalités canoniques auto-générées par IA.

---

## ✨ Fonctionnalités

### 🎭 Comportements physiques (fidèles à Shimeji-ee)

| Comportement | Description |
|---|---|
| Walk / Run / Sit / Sleep | Déplacements et états de repos |
| Grab Wall / Climb Wall | Grimpe et marche sur les murs |
| Grab Ceiling / Climb Ceiling | S'accroche et marche au plafond |
| Jump To Wall / Top | Saute vers les murs et le dessus des fenêtres |
| **Walk With IE** | Porte une fenêtre en marchant |
| **Throw IE** | Lance une fenêtre à travers l'écran |
| Chase Mouse | Suit le curseur de la souris |
| Pinched / Resisting | Réaction quand on attrape le perso |
| Interactions multi-persos | Les persos se regardent et marchent l'un vers l'autre |

> ⚙️ Physique Shimeji-ee fidèle (formules Java exactes), détection surfaces Win32 en temps réel, anti-tunnel, DPI 200% supporté, 30 persos simultanés sans lag.

---

### 🤖 Intelligence Artificielle

- **Chat en streaming** avec chaque personnage (double-clic)
- **7 backends supportés** — local et cloud
- **Personnalité individuelle** auto-générée au premier spawn via l'IA (canonique pour les persos connus)
- **Bouton Régénérer** dans le profil de chaque perso
- **Mémoire conversationnelle** persistante (SQLite WAL)
- Résumé automatique de l'historique toutes les 40 messages

---

### 🤝 Vie sociale entre personnages *(v2)*

- **Conversations automatiques** — les persos se rapprochent et discutent entre eux via l'IA
- **9 scénarios avec poids** : salutation, discussion, commérage, question, philosophique, dispute, blague, chemin, au revoir
- **Longueur variable** selon le scénario — courte pour les saluts, longue pour les débats philosophiques
- **Règles anti-répétition** — les persos ne se re-présentent pas à chaque échange, répondent vraiment aux questions
- **Relations persistantes SQLite** — score (-100 → +100), nombre de rencontres, dernier sujet abordé, labels (inconnus → meilleurs amis)
- **Maintien de proximité** — les persos restent face à face pendant toute la conversation

---

### 😊 Humeur visible *(v2)*

- **Icône emoji flottante** au-dessus de chaque perso avec animation de bobbing
- **10 humeurs** : 😊 heureux · ✨ enthousiaste · 🤔 curieux · 😴 fatigué · 😔 triste · 😤 énervé · 💕 affectueux · 😐 neutre · 😲 surpris · 😏 espiègle
- Évolue selon : le scénario de conversation, l'heure de la journée, le résultat des mini-jeux, le cycle sommeil/réveil

---

### 🎮 Mini-jeux *(v2)*

- **Pierre-feuille-ciseaux** automatique (~toutes les 10 min) quand deux persos sont proches au sol
- Annonce → choix simultané → résultat affiché avec bulles
- Relation mise à jour · Humeur changée (gagnant ✨, perdant 😔)

---

### 😴 Cycle sommeil / réveil *(v2)*

- À **22h** : countdown 5 min → humeur fatiguée 😴 → animation `Sleep` si disponible dans le pack
- À **6h** : réveil automatique avec bulle + humeur selon la qualité du sommeil
- **Bien dormi** (≥ 20 min) → 😊 *"Quelle bonne nuit ! Je suis en forme !"*
- **Mal dormi** → 😔 *"Je n'ai pas assez dormi… je suis épuisé."*
- Suivi individuel par personnage

---

### 🕐 Réactions système *(v2)*

- Commentaires spontanés selon l'heure (7 plages horaires : aube, matin, midi, après-midi, soirée, nuit, nuit profonde)
- **6 jours spéciaux** : Noël 🎄, Halloween 👻, Nouvel An 🎉, Saint-Valentin ♥, 1er avril, 31 décembre

---

### 🪪 Mini-profil par personnage *(v2)*

Clic droit sur un perso → **"🪪 Profil & Relations"** — fenêtre flottante draggable :
- **🤝 Relations** — tous les liens avec score coloré, nombre de rencontres, dernier sujet abordé
- **💬 Historique** — 40 derniers messages + résumé IA · Bouton effacer
- **✏ Personnalité** — éditeur direct + bouton "🔄 Régénérer via IA"

---

### 📦 Import de packs *(v2)*

- Importer un ZIP ou un dossier depuis le menu (clic droit → "📦 Importer un pack Shimeji…")
- Structures plates et imbriquées supportées
- Sprites `.PNG` majuscules détectés automatiquement
- Backup de l'ancien pack si le perso existait déjà

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
git clone https://github.com/nolhanjarrige-ctrl/shimeji-desk.git
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
| **Clic droit** sur un personnage | Menu contextuel (chat, profil, dupliquer, retirer) |
| **Glisser** un personnage | Le soulever et lancer |
| **Maintenir > 5s** | Le personnage se débat |

---

## ⚙️ Paramètres

Tout se configure depuis **Paramètres** (clic droit → icône tray).

| Onglet | Contenu |
|---|---|
| 🤖 IA | Backend, clé API, modèle |
| 🎭 Personnage | Personnalité par perso, échelle |
| ⚙ Comportements | WalkWithIE, Jump, Special, fréquence |
| 🌍 Physique | Vitesse, FPS, gravité, nb max persos |
| 🤝 Social & Mémoire | Conversations, bulles, humeur, mini-jeux, sommeil, mémoire, résumés |
| 🎨 Thème visuel | 5 thèmes (Arknights, Nature, Inferno, Violet, Clair) |
| 🐞 Debug | Overlay état/position/vélocité |

### Onglet Social & Mémoire

| Option | Description |
|---|---|
| 💬 Conversations | Active/désactive les échanges automatiques entre persos |
| 🗨 Bulles | Masque toutes les bulles de dialogue |
| 😊 Humeur | Affiche/cache les icônes d'humeur |
| 🎮 Mini-jeux | Active/désactive le pierre-feuille-ciseaux |
| 😴 Sommeil | Cycle automatique 22h–6h |
| 🕐 Réactions | Commentaires horaires et jours spéciaux |
| 📝 Mémoire | Sauvegarder l'historique des conversations |
| 📋 Résumés | Résumés automatiques toutes les 40 messages |
| 🔢 Historique max | Nombre de messages conservés par perso (10–500) |

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
| **FrostNova** | Rebond à l'atterrissage, chute douce, animation de réveil (`Wokeup`) |
| **Faust** | Téléportation depuis les murs, animations de saut et d'accrochage |
| **Skadi** | Sort ses épées (animation Special) |
| **Sora** | Portail à l'atterrissage |
| **Magallan** | Chute lente comme un ballon |

---

## ➕ Ajouter des personnages

### 📥 Via le menu (recommandé)

Clic droit → **"📦 Importer un pack Shimeji…"** → sélectionner un ZIP ou un dossier.

### 📂 Manuellement

```
assets/default/img/
└── NomDuPerso/
    ├── conf/
    │   └── actions.xml   ← obligatoire
    ├── idle1.png
    ├── walk1.png
    └── ...
```

### 🌐 Où trouver des packs

| Site | Lien |
|---|---|
| **Shimeji-ee** (officiel) | [kilkakon.com/shimeji](https://kilkakon.com/shimeji/) |
| **DeviantArt** | [deviantart.com/tag/shimeji](https://www.deviantart.com/tag/shimeji) |
| **Itch.io** | [itch.io/search?q=shimeji](https://itch.io/search?q=shimeji) |
| **GitHub** | [github.com/search?q=shimeji+sprites](https://github.com/search?q=shimeji+sprites) |

---

## 🗂️ Structure du projet

```
shimeji-desk/
├── main.py
├── config.py / config.json
├── requirements.txt
├── launch.bat / launch_debug.bat / install.bat
├── assets/default/img/         ← Dossiers personnages
├── core/
│   ├── behavior.py             ← Moteur comportemental
│   ├── physics.py              ← Physique (gravité, surfaces)
│   ├── sprite_engine.py        ← Chargement XML + animations
│   ├── mascot_controller.py
│   ├── conversation_manager.py ← Conversations inter-persos (v2)
│   ├── system_reactor.py       ← Sommeil, réactions horaires (v2)
│   ├── minigame_manager.py     ← Pierre-feuille-ciseaux (v2)
│   ├── pack_importer.py        ← Import ZIP/dossier (v2)
│   ├── window_detector.py
│   └── monitor_manager.py
├── ui/
│   ├── mascot_window.py        ← Fenêtre personnage PyQt6
│   ├── chat_window.py          ← Interface chat IA
│   ├── tray_icon.py            ← Menu tray + Paramètres
│   ├── mascot_bubble.py        ← Bulles de dialogue
│   ├── mood_indicator.py       ← Icônes d'humeur (v2)
│   ├── profile_dialog.py       ← Profil & Relations (v2)
│   └── character_selector.py
└── ai/
    ├── client.py               ← Client multi-backend
    └── memory.py               ← Mémoire SQLite + relations (v2)
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
