# NetOpsKit

NetOpsKit est une suite d'outils professionnels pour l'administration, la supervision et la maintenance des réseaux Cisco et multi-vendeurs. L'application propose une interface graphique moderne (PyQt5) et regroupe de nombreux modules pour faciliter la gestion des équipements réseau.

## Fonctionnalités principales

- **Générateur de configuration** : Génération assistée de configurations pour routeurs, switches, CME, etc.
- **Connexion SSH & Console** : Gestion des connexions SSH et série pour l'injection de configuration et la supervision.
- **Sauvegarde & restauration** : Sauvegarde automatisée des configurations via SCP ou SSH, restauration et réinitialisation d'équipements.
- **Supervision graphique** : Visualisation du réseau, état des équipements, ping, découverte automatique, mapping interactif.
- **Syslog Server** : Collecte, affichage et export des logs Syslog avec statistiques avancées.
- **TFTP Server** : Serveur TFTP intégré pour le transfert d'images et de configurations.
- **Mise à jour IOS** : Workflow complet pour la mise à jour des équipements Cisco via TFTP et SSH.
- **Gestion des tâches planifiées** : Sauvegardes et vérifications automatisées selon une planification personnalisée.
- **Support Stormshield** : Outils dédiés pour la gestion et la restauration des firewalls Stormshield.

## Installation

1. **Prérequis** :
   - Python 3.8+
   - Modules : PyQt5, paramiko, scp, schedule, jinja2, serial, psutil, etc.
   - (Windows) : PyInstaller pour la compilation en exécutable

2. **Installation des dépendances** :
   ```bash
   pip install -r requirements.txt
   ```

3. **Lancement en mode développement** :
   ```bash
   python main.py
   ```

4. **Compilation en exécutable (Windows)** :
   Utilisez le script `compileur.py` pour obfusquer et compiler l'application :
   ```bash
   python compileur.py
   ```

## Structure du projet

```
00 - APP/APP V1/
├── main.py                # Point d'entrée principal
├── ui_main.py             # Fenêtre principale et gestion des pages
├── views/                 # Modules fonctionnels (SSH, Serial, Syslog, Supervision, etc.)
├── utils/                 # Utilitaires (sécurité, fichiers, configuration, thèmes)
├── resources/             # Fichiers de style, icônes, logos, templates
├── requirements.txt       # Dépendances Python
├── compileur.py           # Script de compilation et obfuscation
└── README.md              # Ce fichier
```

## Utilisation

- **Lancement** : Exécutez `main.py` pour démarrer l'application.
- **Navigation** : Utilisez les onglets pour accéder aux différents modules (génération de config, SSH, supervision, etc.).
- **Sauvegarde & export** : Les journaux, configurations et backups peuvent être exportés via les boutons dédiés.
- **Personnalisation** : Le style et les préférences sont configurables via le menu ou les fichiers de configuration.

## Support & Contributions

Pour toute question, bug ou suggestion, ouvrez une issue sur le dépôt Git ou contactez l'auteur.

Les contributions sont les bienvenues ! Veuillez respecter la structure du projet et les conventions de nommage.

## Licence

Ce projet est distribué sous licence propriétaire pour usage interne ou éducatif. Toute utilisation commerciale ou redistribution nécessite une autorisation.

---

**Auteur** : Alvaro Varez  
**Contact** : alvaro.varez@protonmail.com

---

*NetOpsKit - Simplifiez la gestion de vos réseaux !*
