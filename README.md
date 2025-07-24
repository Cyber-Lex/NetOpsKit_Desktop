# NetOpsKit

*Simplifiez la gestion de vos réseaux Cisco et multi‑constructeurs avec une boîte à outils complète et une interface moderne.*

![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![GUI](https://img.shields.io/badge/GUI-PyQt5-green)
![License](https://img.shields.io/badge/License-NC--PAY--ATTR%20v1.0-orange)

---

## Table des matières

* [Aperçu](#aperçu)
* [Fonctionnalités](#fonctionnalités)
* [Installation](#installation)

  * [Prérequis](#prérequis)
  * [Installation des dépendances](#installation-des-dépendances)
  * [Lancement en mode développement](#lancement-en-mode-développement)
  * [Compilation en exécutable](#compilation-en-exécutable)
* [Structure du projet](#structure-du-projet)
* [Utilisation](#utilisation)
* [Roadmap / Todo](#roadmap--todo)
* [Contribution](#contribution)
* [Support](#support)
* [Licence](#licence)
* [Auteur](#auteur)

---

## Aperçu

**NetOpsKit** est une suite d’outils professionnels pour l’administration, la supervision et la maintenance de réseaux Cisco et multi‑vendeurs. L’application regroupe des modules pratiques (génération de configuration, supervision, sauvegardes, serveurs intégrés…) au sein d’une interface graphique PyQt5, pensée pour des workflows réseau quotidiens.

---

## Fonctionnalités

### Gestion & automatisation

* **Générateur de configuration** (routeurs, switches, CME…) avec modèles Jinja2.
* **Mise à jour IOS** via TFTP et SSH : workflow complet automatisé.
* **Tâches planifiées** : sauvegardes, vérifications périodiques (via `schedule`).

### Accès & opérations

* **Connexion SSH & Console série** (Paramiko / PySerial) pour injection de configuration et supervision.
* **Sauvegarde & restauration** automatisées (SCP/SSH), reset d’équipements.

### Supervision & visualisation

* **Supervision graphique** : ping, découverte, statut temps réel, cartographie interactive.
* **Syslog server** : collecte, affichage, export et statistiques avancées.
* **TFTP server** intégré pour transfert d’images et de configs.

### Spécifique Stormshield

* Outils dédiés pour la gestion / restauration des firewalls Stormshield.

---

## Installation

### Prérequis

* **Python 3.8+**
* Outils et modules : `PyQt5`, `paramiko`, `scp`, `schedule`, `jinja2`, `pyserial`, `psutil`, etc.
* (Windows) : **PyInstaller** si vous souhaitez compiler un exécutable autonome.

### Installation des dépendances

```bash
pip install -r requirements.txt
```

### Lancement en mode développement

```bash
python main.py
```

### Compilation en exécutable (Windows)

Utilisez le script `compileur.py` pour obfusquer et compiler l’application :

```bash
python compileur.py
```

*(Adaptez le spec PyInstaller si nécessaire.)*

---

## Structure du projet

```
APP V1 /
├── main.py                # Point d'entrée principal
├── ui_main.py             # Fenêtre principale, routing des pages PyQt5
├── compileur.py           # Script de build/obfuscation (PyInstaller)
├── requirements.txt       # Dépendances Python
├── ui/
│   ├── __init__.py
│   ├── custom_controls.py
│   ├── custom_titlebar.py
│   ├── main_window.py
│   └── modern_dialogs.py
├── utils/
│   ├── __init__.py
│   ├── file_utils.py
│   ├── theme_utils.py
│   ├── config_manager.py
│   ├── crypto_utils.py
│   └── profile_manager.py
├── views/
│   ├── __init__.py
│   ├── config_base.py
│   ├── config_generator_cme.py
│   ├── generateur.py
│   ├── home_page.py
│   ├── maj.py
│   ├── serial_connection.py
│   ├── ssh_connection.py
│   ├── stormshield.py
│   ├── supervision.py
│   ├── switch.py
│   ├── sys_log.py
│   └── tftp_server.py
├── worker/
│   ├── advanced_thread.py
│   ├── maj_worker.py
│   └── supervision_worker.py
└── resources/
    ├── style.qss
    ├── config_generator_ui.py
    ├── config_generator.ui
    ├── console.png
    ├── generer.png
    ├── logo/
    │   └── logo_netops.png
    └── map/
        ├── pc_icon.png
        ├── routeur.png
        ├── switch.png
        ├── SW3.png
        ├── firewall.png
        └── default_icon.png
```

---

## Utilisation

1. **Lancement** : `python main.py`
2. **Navigation** : utilisez la barre latérale / onglets pour accéder aux modules (générateur de config, SSH, supervision...).
3. **Sauvegarde & export** : les journaux, configs et backups peuvent être exportés via les boutons dédiés.
4. **Personnalisation** : styles et préférences configurables via les menus ou fichiers de config.
---

## Roadmap / Todo
.
* [ ] Support SNMP pour la supervision.
* [ ] Intégration d’une base de données (SQLite/PostgreSQL) pour stocker les configs et les logs.
* [ ] Deploiement de conteneur.

*(N’hésitez pas à ouvrir une issue ou une PR pour proposer des fonctionnalités.)*

---

## Contribution

Les contributions sont les bienvenues !

1. Forkez le dépôt
2. Créez une branche de feature : `git checkout -b feature/ma-feature`
3. Commitez vos changements : `git commit -m "feat: ajoute ma feature"`
4. Poussez : `git push origin feature/ma-feature`
5. Ouvrez une Pull Request

Merci de respecter :

* La structure du projet
* Les conventions de nommage / style (PEP8, etc.)
* Le processus de review s’il est défini

---

## Support

* **Issues GitHub** : pour les bugs/évolutions
* **Contact direct** : [project-github@proton.me](mailto:project-github@proton.me) (ou autre canal privé)

---

## Licence

Ce projet est distribué sous la licence **NC-PAY-ATTR v1.0** :

* Usage non commercial gratuit **avec attribution** obligatoire.
* Toute utilisation commerciale ou professionnelle nécessite une **licence payante** et un **crédit** à l’auteur.

➡️ Voir le fichier [`LICENSE`](LICENSE) pour tous les détails.

---

## Auteur

**Lex**
Contact : [project-github@proton.me](mailto:project-github@proton.me)

---

> *« NetOpsKit – Simplifiez la gestion de vos réseaux ! »*
