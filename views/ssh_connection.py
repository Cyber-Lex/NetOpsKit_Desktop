import time
import paramiko
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QTextEdit, QMessageBox, QHBoxLayout, 
    QApplication, QProgressBar, QLabel, QGroupBox, QSplitter, QFrame, QGridLayout, QFileDialog
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from PyQt5.QtGui import QTextCursor

# Classe de thread pour l'injection de configuration SSH
class SSHConfigInjectionThread(QThread):
    line_injected = pyqtSignal(str, str)  # type, message
    injection_complete = pyqtSignal(bool, str)
    progress_update = pyqtSignal(int, int)

    def __init__(self, ssh_client, config):
        super().__init__()
        self.ssh_client = ssh_client
        self.config = config
        self.running = True
        
        # Paramètres optimisés pour les équipements Cisco
        self.BATCH_SIZE = 1        # Pour Cisco, une commande à la fois est plus sûr
        self.COMMAND_DELAY = 0.2   # Délai entre les commandes (200ms)
        self.BATCH_DELAY = 0.5     # Délai après chaque lot (500ms)
        self.BUFFER_SIZE = 8192    # Taille du buffer de lecture
        self.COMMAND_TIMEOUT = 3   # Temps d'attente pour une réponse complète (3s)
        
        # Détection des prompts Cisco pour savoir quand la commande est terminée
        self.CISCO_PROMPTS = ['>', '#', '(config)#', '(config-if)#', '(config-line)#', '(config-router)#']

    def run(self):
        try:
            # Créer une session shell interactive
            shell = self.ssh_client.invoke_shell()
            shell.settimeout(0.1)  # Non-bloquant mais avec timeout court
            
            # Attendre que le prompt apparaisse
            time.sleep(1)
            
            if shell.recv_ready():
                initial_output = shell.recv(self.BUFFER_SIZE).decode(errors='ignore')
                self.line_injected.emit("response", f"Prompt initial: {initial_output}")
                
            # Pour les équipements Cisco, désactiver le mode paginer
            shell.send("terminal length 0\n")
            time.sleep(0.5)
            
            # Vider les réponses du 'terminal length'
            if shell.recv_ready():
                term_output = shell.recv(self.BUFFER_SIZE).decode(errors='ignore')
                self.line_injected.emit("response", f"Configuration du terminal: {term_output}")
            
            # Filtrer les lignes vides et les commentaires
            lines = [line for line in self.config.splitlines() 
                    if line.strip() and not line.strip().startswith('!')]
            total_lines = len(lines)
            processed_lines = 0
            
            # Première détection du prompt pour adapter le processus
            current_prompt = self.detect_prompt(initial_output)
            if current_prompt:
                self.line_injected.emit("info", f"Prompt Cisco détecté: {current_prompt}")
            
            # Traitement des commandes (une par une pour Cisco)
            for i in range(0, total_lines):
                if not self.running:
                    shell.close()
                    self.injection_complete.emit(False, "Injection interrompue par l'utilisateur")
                    return
                
                # Prendre la commande
                cmd = lines[i]
                
                # Préparation de la commande (avec retour chariot)
                command = cmd + "\n"
                shell.send(command)
                self.line_injected.emit("command", f"{cmd}")
                processed_lines += 1
                
                # Attente et lecture des réponses avec détection du prompt
                response = self.read_until_prompt(shell)
                
                # Mise à jour de la progression
                self.progress_update.emit(processed_lines, total_lines)
                
                # Pause après chaque commande pour laisser l'équipement traiter
                QThread.msleep(int(self.COMMAND_DELAY * 1000))
            
            # Une dernière lecture des réponses pour vider le buffer
            QThread.msleep(500)  # Attente un peu plus longue à la fin
            if shell.recv_ready():
                final_output = shell.recv(self.BUFFER_SIZE).decode(errors='ignore')
                if final_output.strip():
                    self.line_injected.emit("response", f"Sortie finale: {final_output}")
            
            shell.close()
            self.injection_complete.emit(True, "Configuration injectée avec succès.")
        except Exception as e:
            self.injection_complete.emit(False, f"Erreur lors de l'injection: {str(e)}")

    def detect_prompt(self, output):
        """Détecte le prompt Cisco dans la sortie"""
        if not output:
            return None
            
        lines = output.strip().split('\n')
        last_line = lines[-1] if lines else ""
        
        for prompt in self.CISCO_PROMPTS:
            if prompt in last_line:
                return prompt
                
        return None

    def read_until_prompt(self, shell):
        """Lit les données jusqu'à ce qu'un prompt Cisco soit détecté ou timeout"""
        buffer = ""
        timeout = time.time() + self.COMMAND_TIMEOUT
        prompt_detected = False
        
        while time.time() < timeout and not prompt_detected:
            if shell.recv_ready():
                chunk = shell.recv(self.BUFFER_SIZE).decode(errors='ignore')
                buffer += chunk
                
                # Vérifier si un prompt est présent dans la sortie
                for prompt in self.CISCO_PROMPTS:
                    if prompt in buffer:
                        prompt_detected = True
                        break
                        
                # Reset timeout si on reçoit des données
                if chunk:
                    timeout = time.time() + 0.5
            else:
                # Attente courte avant nouvelle vérification
                QThread.msleep(50)
                
                # Si un prompt a été détecté, on peut sortir plus tôt
                if prompt_detected:
                    break
        
        if buffer:
            # Limiter l'affichage des réponses trop longues
            if len(buffer) > 500:
                display_buffer = buffer[:500] + "... (tronqué)"
            else:
                display_buffer = buffer
            self.line_injected.emit("response", display_buffer)
            
        return buffer

    def stop(self):
        self.running = False


class SSHConnection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.client = None
        self.injection_thread = None
        self.parent = parent
        self.setWindowTitle("Injecteur de Configuration SSH")
        
        # Main layout for the entire widget
        self.main_layout = QVBoxLayout(self)
        
        # Create the back button at the top
        # Pour éviter la duplication, on s'assure que cette propriété est publique
        # et qu'elle est accessible par HomePage
        self.backToHomeButton = QPushButton("Retour")
        self.backToHomeButton.setObjectName("backToHomeFromSSHButton")  
        self.backToHomeButton.setMinimumHeight(40)
        self.main_layout.addWidget(self.backToHomeButton)
        
        # Connect back button to parent's show_home method if available
        # IMPORTANT: HomePage va prendre le contrôle de ce bouton, donc on ne connecte rien ici
        # pour éviter les connexions en double
        
        # Create a container for the SSH widget content
        self.ssh_widget = QWidget()
        self.main_layout.addWidget(self.ssh_widget)
        
        # Initialize the UI
        self.initUI()

    def initUI(self):
        main_layout = QVBoxLayout(self.ssh_widget)
        
        # Partie supérieure - Configuration
        config_group = QGroupBox("Configuration de la connexion SSH")
        config_layout = QGridLayout()
        
        # Ligne 1 - Host et port
        host_label = QLabel("Adresse IP:")
        self.host_line = QLineEdit()
        self.host_line.setObjectName("hostField")
        
        port_label = QLabel("Port:")
        self.port_line = QLineEdit()
        self.port_line.setObjectName("portField")
        self.port_line.setText("22")
        
        config_layout.addWidget(host_label, 0, 0)
        config_layout.addWidget(self.host_line, 0, 1)
        config_layout.addWidget(port_label, 0, 2)
        config_layout.addWidget(self.port_line, 0, 3)
        
        # Ligne 2 - Identifiants
        username_label = QLabel("Identifiant:")
        self.username_line = QLineEdit()
        self.username_line.setObjectName("usernameField")
        
        password_label = QLabel("Mot de passe:")
        self.password_line = QLineEdit()
        self.password_line.setObjectName("passwordField")
        self.password_line.setEchoMode(QLineEdit.Password)
        
        config_layout.addWidget(username_label, 1, 0)
        config_layout.addWidget(self.username_line, 1, 1)
        config_layout.addWidget(password_label, 1, 2)
        config_layout.addWidget(self.password_line, 1, 3)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # Boutons d'action - IMPORTANT: s'assurer que ces objets soient accessibles
        # tout en restant uniques dans l'interface
        action_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Se connecter")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.clicked.connect(self.ssh_connect)
        
        self.disconnect_button = QPushButton("Se déconnecter")
        self.disconnect_button.setObjectName("disconnectButton")
        self.disconnect_button.clicked.connect(self.disconnect)
        
        self.stop_injection_button = QPushButton("Arrêter l'injection")
        self.stop_injection_button.setObjectName("stopInjectionButton")
        self.stop_injection_button.clicked.connect(self.stop_injection)
        self.stop_injection_button.setEnabled(False)
        
        # Mettre tous les boutons de la même taille
        action_layout.addWidget(self.connect_button)
        action_layout.addWidget(self.disconnect_button)
        action_layout.addWidget(self.stop_injection_button)
        
        main_layout.addLayout(action_layout)
        
        # Barre de progression
        progress_layout = QHBoxLayout()
        progress_label = QLabel("Progression:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        
        main_layout.addLayout(progress_layout)
        
        # Zone de logs
        log_group = QGroupBox("Journal des opérations")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logArea")
        self.log_text.setMinimumHeight(200)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(log_group)
        
        # Le bouton d'injection de config doit être accessible par HomePage
        # Assurez-vous qu'il n'est créé qu'une seule fois
        self.inject_config_button = QPushButton("Injecter la config")
        self.inject_config_button.setObjectName("injectConfigButton")
        self.inject_config_button.setMinimumHeight(40)
        self.inject_config_button.clicked.connect(self.open_file_dialog)
        main_layout.addWidget(self.inject_config_button)
        
        # Status label aussi accessible par HomePage
        self.status_label = QLabel("Status: Déconnecté")
        self.status_label.setMinimumHeight(30)
        self.status_label.setObjectName("sshStatusLabel")
        main_layout.addWidget(self.status_label)
        
        # Configure layout
        self.setMinimumSize(500, 600)
        
        # Timer pour mettre à jour l'interface
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_log)
        self.timer.start(50)

    def log(self, message, msg_type="info"):
        """Ajoute un message au journal"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        self.log_text.append(log_message)
        
        # Défiler automatiquement vers le bas
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def ssh_connect(self):
        host = self.host_line.text()
        try:
            port = int(self.port_line.text())
        except ValueError:
            self.log("Erreur : Port invalide", "error")
            return
            
        username = self.username_line.text()
        password = self.password_line.text()
        
        self.log(f"Connexion SSH sur {host}:{port} avec l'identifiant '{username}'...")
        
        try:
            # Configuration du client SSH optimisée pour Cisco
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Configuration des timeout pour une meilleure réactivité
            self.client.connect(
                hostname=host, 
                port=port, 
                username=username, 
                password=password,
                timeout=5,        # Timeout de connexion
                banner_timeout=5, # Timeout pour le banner SSH
                auth_timeout=10   # Timeout pour l'authentification
            )
            self.log("Connexion SSH réussie", "success")
            
            # On crée une session shell juste pour tester, mais on ne la garde pas active
            temp_shell = self.client.invoke_shell()
            temp_shell.settimeout(1.0)
            
            # Attendre le prompt initial
            time.sleep(1.0)
            initial_response = ""
            if temp_shell.recv_ready():
                initial_response = temp_shell.recv(4096).decode(errors='ignore')
                self.log("Connexion à l'équipement Cisco établie", "success")
            
            # Désactiver le paging pour obtenir des sorties complètes
            temp_shell.send("terminal length 0\n")
            time.sleep(0.5)
            
            # Récupérer et ignorer la réponse à cette commande
            if temp_shell.recv_ready():
                temp_shell.recv(4096)
            
            # Fermer cette session shell de test - on n'en a plus besoin
            temp_shell.close()
            
        except Exception as e:
            self.log(f"Erreur de connexion SSH : {str(e)}", "error")
            QMessageBox.critical(self, "Erreur de connexion", 
                                f"Impossible de se connecter à l'équipement Cisco sur {host}:{port}\n\nErreur: {str(e)}")
            self.client = None

    def disconnect(self):
        if self.injection_thread and self.injection_thread.isRunning():
            self.stop_injection()
            
        if self.client:
            try:
                self.client.close()
                self.log("Déconnexion SSH réussie", "success")
                self.client = None
            except Exception as e:
                self.log(f"Erreur lors de la déconnexion SSH : {str(e)}", "error")
        else:
            self.log("Aucune connexion SSH active", "error")

    def inject_configuration(self, config):
        if not self.client:
            QMessageBox.critical(self, "Erreur", "Veuillez d'abord vous connecter.")
            return
            
        # Vérifier si une injection est déjà en cours
        if self.injection_thread and self.injection_thread.isRunning():
            QMessageBox.warning(self, "Injection en cours", "Une injection est déjà en cours. Veuillez attendre qu'elle se termine.")
            return
        
        # Vérification et prétraitement des commandes Cisco
        try:
            # Vérifier si le contenu ressemble à une configuration Cisco
            lines = config.splitlines()
            cisco_commands = ["interface", "router", "ip route", "line", "hostname", 
                             "enable", "configure terminal", "end", "exit", "vlan"]
            
            # Vérifier si des commandes Cisco sont présentes
            has_cisco_commands = any(any(cmd in line for cmd in cisco_commands) for line in lines if line.strip())
            
            if not has_cisco_commands:
                # Si aucune commande Cisco n'est détectée, demander confirmation
                reply = QMessageBox.question(
                    self, "Confirmation de configuration",
                    "Aucune commande Cisco typique n'a été détectée dans la configuration.\n\n"
                    "Êtes-vous sûr de vouloir injecter cette configuration?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            
            # Vérifier si "configure terminal" est présent, sinon l'ajouter au début
            has_config_terminal = any("configure terminal" in line.lower() for line in lines)
            
            # Préparation de la configuration
            if not has_config_terminal:
                self.log("Ajout automatique de 'configure terminal' au début de la configuration", "info")
                config = "configure terminal\n" + config
                
            # Vérifier si "end" ou "exit" est présent à la fin, sinon l'ajouter
            last_lines = [line for line in reversed(lines) if line.strip()]
            if not last_lines or not any(cmd in last_lines[0].lower() for cmd in ["end", "exit"]):
                self.log("Ajout automatique de 'end' à la fin de la configuration", "info")
                config = config + "\nend"
        except Exception as e:
            self.log(f"Erreur lors de l'analyse de la configuration: {str(e)}", "error")
            # On continue quand même, ce n'est qu'une vérification préventive
            
        self.log("Démarrage de l'injection de configuration Cisco...", "info")
        
        # Réinitialiser la barre de progression
        self.progress_bar.setValue(0)
        
        try:
            # Vérifier si la connexion SSH est toujours active
            transport = self.client.get_transport()
            if transport is None or not transport.is_active():
                self.log("La connexion SSH n'est plus active. Reconnexion...", "warning")
                
                # On peut essayer de se reconnecter ici
                host = self.host_line.text()
                try:
                    port = int(self.port_line.text())
                except ValueError:
                    self.log("Erreur : Port invalide", "error")
                    return
                
                username = self.username_line.text()
                password = self.password_line.text()
                
                try:
                    self.client.connect(
                        hostname=host, 
                        port=port, 
                        username=username, 
                        password=password,
                        timeout=5
                    )
                    self.log("Reconnexion SSH réussie", "success")
                except Exception as e:
                    self.log(f"Échec de reconnexion SSH : {str(e)}", "error")
                    QMessageBox.critical(self, "Erreur de connexion", 
                                        f"Impossible de rétablir la connexion SSH.\n\nErreur: {str(e)}")
                    return
            
            # Créer et configurer le thread d'injection
            self.injection_thread = SSHConfigInjectionThread(self.client, config)
            self.injection_thread.line_injected.connect(self.on_line_injected)
            self.injection_thread.injection_complete.connect(self.on_injection_complete)
            self.injection_thread.progress_update.connect(self.on_progress_update)
            
            # Désactiver les boutons pendant l'injection
            self.connect_button.setEnabled(False)
            self.disconnect_button.setEnabled(False)
            self.stop_injection_button.setEnabled(True)
            
            # Démarrer le thread
            self.injection_thread.start()
            
        except Exception as e:
            self.log(f"Erreur lors de la préparation de l'injection: {str(e)}", "error")
            QMessageBox.critical(self, "Erreur d'injection", f"Erreur lors de la préparation de l'injection: {str(e)}")
            self.progress_bar.setValue(0)

    def on_line_injected(self, msg_type, message):
        # Limiter le nombre de messages dans la fenêtre de log pour éviter de ralentir l'UI
        if self.log_text.document().lineCount() > 1000:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 100)  # Supprimer les 100 premières lignes
            cursor.removeSelectedText()
            
        self.log(message, msg_type)
        
    def on_injection_complete(self, success, message):
        # Réactiver les boutons
        self.connect_button.setEnabled(True)
        self.disconnect_button.setEnabled(True)
        self.stop_injection_button.setEnabled(False)
        
        # Compléter la barre de progression
        self.progress_bar.setValue(100)
        
        # Ajouter le message final
        if success:
            self.log(message, "success")
            QMessageBox.information(self, "Injection terminée", message)
        else:
            self.log(message, "error")
            QMessageBox.warning(self, "Erreur d'injection", message)

    def on_progress_update(self, current, total):
        # Mettre à jour la barre de progression
        progress_pct = int((current / total) * 100)
        self.progress_bar.setValue(progress_pct)
        
        # Afficher la progression de manière optimisée (seulement tous les 5%)
        if progress_pct % 5 < 1 or current == total:  # Afficher tous les ~5% ou à la fin
            self.log(f"Progression: {current}/{total} commandes ({progress_pct}%)", "info")

    def stop_injection(self):
        if self.injection_thread and self.injection_thread.isRunning():
            self.log("Arrêt de l'injection en cours...", "info")
            self.injection_thread.stop()
            self.injection_thread.wait(1000)  # Attendre max 1 seconde
            
            # Si le thread est toujours en cours après délai
            if self.injection_thread.isRunning():
                self.log("Arrêt forcé du thread...", "error")
                self.injection_thread.terminate()
                
            self.connect_button.setEnabled(True)
            self.disconnect_button.setEnabled(True)
            self.stop_injection_button.setEnabled(False)

    def update_log(self):
        # Cette méthode est appelée régulièrement par le timer
        QApplication.processEvents()

    def open_file_dialog(self):
        """Open file dialog to select configuration file and inject it"""
        self.status_label.setText("Status: Sélection du fichier de configuration...")
        
        file_name, _ = QFileDialog.getOpenFileName(
            self, 
            "Sélectionner un fichier de configuration", 
            "", 
            "Fichiers texte (*.txt);;Fichiers de configuration (*.cfg);;Tous les fichiers (*.*)"
        )
        
        if file_name:
            try:
                with open(file_name, "r", encoding="utf-8") as f:
                    config = f.read()
                # Inject the configuration
                self.inject_configuration(config)
                QMessageBox.information(self, "Succès", "Configuration injectée avec succès via SSH.")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de l'injection : {e}")

    def getBackButton(self):
        """Returns the back button if it exists"""
        if hasattr(self, 'backToHomeButton'):
            return self.backToHomeButton
        return None

    # Modifier cette méthode pour s'assurer qu'elle remplace bien l'ancienne connexion
    def set_home_callback(self, callback):
        """Set the callback for the back button"""
        if hasattr(self, 'backToHomeButton'):
            try:
                # Tentative de déconnexion sécurisée
                self.backToHomeButton.clicked.disconnect()
            except (TypeError, RuntimeError):
                # Pas de connexions existantes ou autre erreur de déconnexion
                pass
            # Ajouter la nouvelle connexion
            self.backToHomeButton.clicked.connect(callback)