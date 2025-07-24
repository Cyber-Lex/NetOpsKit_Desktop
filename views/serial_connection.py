import time
import os  # Add os module import
import serial
from serial.tools import list_ports
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout, 
    QLineEdit, QPushButton, QTextEdit, QMessageBox, QComboBox, 
    QLabel, QFrame, QApplication, QSplitter, QProgressBar, QGroupBox,
    QFileDialog  # Add QFileDialog for file selection
)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QByteArray
from PyQt5.QtGui import QTextCursor

# Classe de thread pour l'injection de configuration
class ConfigInjectionThread(QThread):
    line_injected = pyqtSignal(str, str)  # type, message
    injection_complete = pyqtSignal(bool, str)
    progress_update = pyqtSignal(int, int)

    def __init__(self, serial_connection, config):
        super().__init__()
        self.serial_connection = serial_connection
        self.config = config
        self.running = True
        
        # Paramètres optimisés fixes
        self.BATCH_SIZE = 5       # Nombre de commandes par lot
        self.COMMAND_DELAY = 0.05 # Délai minimal entre les commandes (50ms)
        self.BATCH_DELAY = 0.15   # Délai après chaque lot (150ms)
        self.BUFFER_SIZE = 4096   # Taille du buffer de lecture

    def run(self):
        try:
            # Filtrer les lignes vides
            lines = [line for line in self.config.splitlines() if line.strip()]
            total_lines = len(lines)
            processed_lines = 0
            
            # Traitement par lots optimisé
            for i in range(0, total_lines, self.BATCH_SIZE):
                if not self.running:
                    self.injection_complete.emit(False, "Injection interrompue par l'utilisateur")
                    return
                
                # Prendre un lot de commandes
                batch = lines[i:i + self.BATCH_SIZE]
                batch_buffer = QByteArray()
                
                # Préparer le lot en un seul buffer
                for line in batch:
                    command = line + "\r\n"
                    batch_buffer.append(command.encode())
                    self.line_injected.emit("command", f"{line}")
                    processed_lines += 1
                    
                    # Pause minimale entre les commandes dans le même lot
                    QThread.msleep(int(self.COMMAND_DELAY * 1000))
                
                # Envoyer le lot d'un coup pour optimiser la communication
                self.serial_connection.write(batch_buffer)
                
                # Mise à jour de la progression
                self.progress_update.emit(processed_lines, total_lines)
                
                # Pause après l'envoi du lot pour permettre au périphérique de traiter
                QThread.msleep(int(self.BATCH_DELAY * 1000))
                
                # Lire les réponses de l'équipement
                self.read_responses()
            
            # Une dernière lecture des réponses pour vider le buffer
            QThread.msleep(100)  # Attendre un peu plus pour la dernière lecture
            self.read_responses()
            
            self.injection_complete.emit(True, "Configuration injectée avec succès.")
        except Exception as e:
            self.injection_complete.emit(False, f"Erreur lors de l'injection: {str(e)}")

    def read_responses(self):
        """Lit efficacement toutes les données disponibles sur le port série"""
        try:
            if self.serial_connection.in_waiting:
                # Lecture optimisée par blocs pour éviter les opérations trop fréquentes
                response = self.serial_connection.read(min(self.serial_connection.in_waiting, self.BUFFER_SIZE))
                if response:
                    decoded_response = response.decode(errors='ignore').strip()
                    if decoded_response:  # N'envoyer que les réponses non vides
                        # Limiter l'affichage des réponses trop longues
                        if len(decoded_response) > 200:
                            decoded_response = decoded_response[:200] + "... (tronqué)"
                        self.line_injected.emit("response", decoded_response)
        except Exception as e:
            self.line_injected.emit("error", f"Erreur de lecture: {str(e)}")

    def stop(self):
        self.running = False


class SerialConnection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_connection = None
        self.injection_thread = None
        self.is_authenticated = False
        self.parent = parent
        self.setWindowTitle("Injecteur de Configuration Série")
        
        # Main layout for the entire widget
        self.main_layout = QVBoxLayout(self)
        
        # Create the back button at the top
        self.backToHomeButton = QPushButton("Retour")
        self.backToHomeButton.setObjectName("backToHomeFromConsoleButton")
        self.backToHomeButton.setMinimumHeight(40)
        self.main_layout.addWidget(self.backToHomeButton)
        
        # Connect back button to parent's show_home method if available
        if parent and hasattr(parent, 'show_home'):
            self.backToHomeButton.clicked.connect(parent.show_home)
        
        # Create the serial_widget container
        self.serial_widget = QWidget()
        self.main_layout.addWidget(self.serial_widget)
        
        # Initialize the actual UI in the serial widget
        self.initUI()
    
    def initUI(self):
        # Create layout for serial widget
        main_layout = QVBoxLayout(self.serial_widget)
        
        # Partie supérieure - Configuration
        config_group = QGroupBox("Configuration de la connexion")
        config_layout = QGridLayout()
        
        # Ligne 1 - Port
        port_label = QLabel("Port COM:")
        self.port_combo = QComboBox()
        self.port_combo.setObjectName("portCombo")
        self.port_combo.setMinimumWidth(200)
        
        self.refresh_button = QPushButton("Rafraîchir")
        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.clicked.connect(self.refresh_ports)
        
        config_layout.addWidget(port_label, 0, 0)
        config_layout.addWidget(self.port_combo, 0, 1)
        config_layout.addWidget(self.refresh_button, 0, 2)
        
        # Ligne 2 - Baudrate
        baudrate_label = QLabel("Baudrate:")
        self.baudrate_line = QLineEdit()
        self.baudrate_line.setObjectName("baudrateField")
        self.baudrate_line.setText("9600")
        config_layout.addWidget(baudrate_label, 1, 0)
        config_layout.addWidget(self.baudrate_line, 1, 1, 1, 2)
        
        # Ligne 3 - Identifiants (côte à côte)
        username_label = QLabel("Identifiant:")
        self.username_line = QLineEdit()
        self.username_line.setObjectName("usernameField")
        
        password_label = QLabel("Mot de passe:")
        self.password_line = QLineEdit()
        self.password_line.setObjectName("passwordField")
        self.password_line.setEchoMode(QLineEdit.Password)
        
        config_layout.addWidget(username_label, 2, 0)
        config_layout.addWidget(self.username_line, 2, 1)
        config_layout.addWidget(password_label, 3, 0)
        config_layout.addWidget(self.password_line, 3, 1)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Se connecter")
        self.connect_button.setObjectName("connectButton")
        self.connect_button.clicked.connect(self.connect)
        
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
        
        # Zone de logs - Utiliser un splitter pour permettre le redimensionnement
        log_group = QGroupBox("Journal des opérations")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setObjectName("logArea")
        self.log_text.setMinimumHeight(200)
        
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        
        main_layout.addWidget(log_group)
        
        # Ajouter le bouton "Injecter la config"
        self.inject_config_button = QPushButton("Injecter la config")
        self.inject_config_button.setObjectName("injectConfigButton")
        self.inject_config_button.setMinimumHeight(40)
        # Connect directly to inject_configuration instead of open_file_dialog
        self.inject_config_button.clicked.connect(self.inject_configuration)
        main_layout.addWidget(self.inject_config_button)
        
        # Console status label
        self.status_label = QLabel("Status: Déconnecté")
        self.status_label.setMinimumHeight(30)
        main_layout.addWidget(self.status_label)
        
        # Configure le layout principal
        self.setLayout(main_layout)
        self.setMinimumSize(500, 600)
        
        # Timer pour mettre à jour l'interface
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_log)
        self.timer.start(50)  # Mise à jour toutes les 50ms pour plus de réactivité
        
        # Initialisation
        self.refresh_ports()

    def log(self, message, msg_type="info"):
        """Ajoute un message au journal"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        self.log_text.append(log_message)
        
        # Défiler automatiquement vers le bas
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
        # Suppression de la mise à jour de la barre d'état

    def refresh_ports(self):
        self.port_combo.clear()
        ports = list_ports.comports()
        if ports:
            for port in ports:
                self.port_combo.addItem(f"{port.device} ({port.description})", port.device)
            self.log(f"{len(ports)} ports COM détectés")
        else:
            self.log("Aucun port COM détecté", "error")

    def connect(self):
        port_data = self.port_combo.currentData()
        if not port_data:
            self.log("Aucun port COM sélectionné", "error")
            return
        port = port_data
        try:
            baudrate = int(self.baudrate_line.text())
        except ValueError:
            self.log("Erreur : Baudrate invalide", "error")
            return

        username = self.username_line.text()
        password = self.password_line.text()

        self.log(f"Connexion sur le port {port} à {baudrate} bauds...")
        
        try:
            # Utiliser un timeout plus court pour améliorer la réactivité
            self.serial_connection = serial.Serial(port, baudrate, timeout=0.5)
            # Augmenter les tailles de buffer pour une meilleure performance
            self.serial_connection.set_buffer_size(rx_size=8192, tx_size=8192)
            self.log("Connexion série réussie", "success")
            
            # Réinitialiser l'état d'authentification
            self.is_authenticated = False
            
            # Attendre que l'équipement envoie un prompt initial
            time.sleep(1.0)
            initial_prompt = ""
            if self.serial_connection.in_waiting:
                initial_prompt = self.serial_connection.read(self.serial_connection.in_waiting).decode(errors='ignore')
                if initial_prompt.strip():
                    self.log(f"Prompt initial: {initial_prompt}", "response")
            
            # Vérifier si le prompt initial demande un nom d'utilisateur
            username_prompts = ["username", "login", "user:", "utilisateur"]
            password_prompts = ["password", "mot de passe"]
            
            # Vérifier si l'équipement demande immédiatement un identifiant
            needs_auth = any(prompt in initial_prompt.lower() for prompt in username_prompts + password_prompts)
            
            if needs_auth:
                self.log("L'équipement demande une authentification", "info")
                if not username or not password:
                    self.log("Authentification requise mais aucun identifiant fourni", "error")
                    QMessageBox.critical(self, "Authentification requise", 
                                       "L'équipement demande un identifiant et un mot de passe, mais aucun n'a été fourni.")
                    # Fermer la connexion puisqu'on ne peut pas procéder
                    if self.serial_connection and self.serial_connection.is_open:
                        self.serial_connection.close()
                        self.serial_connection = None
                    return
                else:
                    # Envoyer les identifiants
                    self.authenticate(username, password)
            elif username and password:
                # Si des identifiants sont fournis, essayer de s'authentifier même sans prompt initial
                self.authenticate(username, password)
            else:
                # Pas de prompt d'authentification immédiat, tester si l'authentification est nécessaire
                self.test_authentication_required()
                
        except Exception as e:
            self.log(f"Erreur de connexion série : {str(e)}", "error")
            
    def test_authentication_required(self):
        """Teste si l'équipement nécessite une authentification même sans prompt initial"""
        self.log("Test de la nécessité d'authentification...", "info")
        
        # Envoyer un retour chariot pour déclencher une réponse
        self.serial_connection.write("\r\n".encode())
        time.sleep(0.5)
        
        # Lire la réponse
        response = ""
        if self.serial_connection.in_waiting:
            response = self.serial_connection.read(self.serial_connection.in_waiting).decode(errors='ignore')
            if response.strip():
                self.log(f"Réponse au test: {response}", "response")
        
        # Vérifier si la réponse contient une demande d'authentification
        auth_prompts = ["username:", "login:", "password:", "utilisateur:", "mot de passe:"]
        if any(prompt in response.lower() for prompt in auth_prompts):
            self.log("L'équipement demande une authentification après le test", "warning")
            self.is_authenticated = False
            QMessageBox.warning(self, "Authentification requise", 
                               "L'équipement demande une authentification. Veuillez vous reconnecter avec des identifiants.")
            return
        
        # Si aucune demande d'authentification n'est détectée, considérer comme authentifié
        self.log("Aucune authentification requise détectée", "success") 
        self.is_authenticated = True

    def authenticate(self, username, password):
        """Méthode séparée pour l'authentification avec vérification du résultat"""
        self.log(f"Authentification avec l'identifiant: {username}")
        time.sleep(0.5)
        
        # Lire le prompt actuel
        prompt = ""
        if self.serial_connection.in_waiting:
            prompt = self.serial_connection.read(self.serial_connection.in_waiting).decode(errors='ignore')
            if prompt.strip():
                self.log(f"Prompt: {prompt}", "response")
        
        # Envoyer l'identifiant
        self.serial_connection.write((username + "\r\n").encode())
        self.log("Envoi de l'identifiant", "command")
        time.sleep(0.5)
        
        # Lire la réponse après l'identifiant
        id_response = ""
        if self.serial_connection.in_waiting:
            id_response = self.serial_connection.read(self.serial_connection.in_waiting).decode(errors='ignore')
            if id_response.strip():
                self.log(f"Réponse après identifiant: {id_response}", "response")
        
        # Vérifier si le login a été rejeté
        login_error_keywords = ["failed", "incorrect", "invalid", "error", "échec", "erreur", "login invalid"]
        if any(keyword in id_response.lower() for keyword in login_error_keywords):
            self.log("Authentification échouée: identifiant incorrect", "error")
            self.is_authenticated = False
            QMessageBox.critical(self, "Erreur d'authentification", 
                               "Identifiant incorrect. L'authentification a échoué.")
            return
        
        # Envoyer le mot de passe (que la réponse demande un mot de passe ou non)
        # Certains équipements demandent un mot de passe sans afficher de prompt
        self.serial_connection.write((password + "\r\n").encode())
        self.log("Envoi du mot de passe", "command")
        time.sleep(1.0)
        
        # Lire la réponse après le mot de passe
        auth_response = ""
        if self.serial_connection.in_waiting:
            auth_response = self.serial_connection.read(self.serial_connection.in_waiting).decode(errors='ignore')
            if auth_response.strip():
                self.log(f"Réponse après authentification: {auth_response}", "response")
        
        # Vérifier explicitement si l'authentification a échoué
        # Mots-clés d'échec à rechercher
        auth_error_keywords = ["failed", "incorrect", "invalid", "error", "denied", "échec", 
                               "erreur", "refusé", "login invalid", "bad password"]
        
        if any(keyword in auth_response.lower() for keyword in auth_error_keywords):
            self.log("Authentification échouée: mot de passe incorrect", "error")
            self.is_authenticated = False
            QMessageBox.critical(self, "Erreur d'authentification", 
                               "Mot de passe incorrect. L'authentification a échoué.")
            return
        
        # Vérifier si on a reçu un nouveau prompt pour l'authentification (échec silencieux)
        if "username" in auth_response.lower() or "login" in auth_response.lower():
            self.log("Authentification échouée: l'équipement redemande un identifiant", "error")
            self.is_authenticated = False
            QMessageBox.critical(self, "Erreur d'authentification", 
                               "L'équipement redemande un identifiant, ce qui indique un échec d'authentification.")
            return
            
        # Si aucune erreur d'authentification n'est détectée, considérer comme authentifié
        self.log("Authentification réussie", "success")
        self.is_authenticated = True

    def disconnect(self):
        if self.injection_thread and self.injection_thread.isRunning():
            self.stop_injection()
            
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                self.log("Déconnexion série réussie", "success")
                self.serial_connection = None
                self.is_authenticated = False  # Réinitialiser l'état d'authentification
            except Exception as e:
                self.log(f"Erreur lors de la déconnexion : {str(e)}", "error")
        else:
            self.log("Aucune connexion série ouverte", "error")

    def inject_configuration(self, config=None):
        """
        Inject configuration via Serial connection. 
        If config is None, prompt the user to select a configuration file.
        """
        # Update status label when starting file selection
        self.status_label.setText("Status: Sélection du fichier de configuration...")
        
        if not self.serial_connection or not self.serial_connection.is_open:
            QMessageBox.critical(self, "Erreur", "Veuillez d'abord vous connecter.")
            self.status_label.setText("Status: Erreur - Aucune connexion")
            return
            
        # Vérifier si une injection est déjà en cours
        if self.injection_thread and self.injection_thread.isRunning():
            QMessageBox.warning(self, "Injection en cours", "Une injection est déjà en cours. Veuillez attendre qu'elle se termine.")
            return
        
        # Vérification plus robuste du paramètre config pour éviter les erreurs de type
        need_file_selection = False
        
        if config is None:
            need_file_selection = True
        elif isinstance(config, bool):
            # Si config est un booléen, nous devons sélectionner un fichier
            need_file_selection = True
        elif isinstance(config, str) and config.strip() == "":
            # Si config est une chaîne vide, nous devons sélectionner un fichier
            need_file_selection = True
            
        # Si aucune config valide n'est fournie, ouvrir un dialogue pour sélectionner un fichier
        if need_file_selection:
            # Log the file selection action
            self.log("Sélection d'un fichier de configuration...", "info")
            
            # Ouvrir un dialogue de sélection de fichier
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Sélectionner un fichier de configuration",
                "",
                "Fichiers texte (*.txt);;Fichiers de configuration (*.cfg);;Tous les fichiers (*.*)"
            )
            
            # Si l'utilisateur annule, sortir de la méthode
            if not file_path:
                self.log("Sélection de fichier annulée", "warning")
                self.status_label.setText("Status: Sélection annulée")
                return
                
            # Lire le contenu du fichier
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    config = file.read()
                self.log(f"Fichier de configuration chargé: {file_path}", "success")
                self.status_label.setText(f"Status: Fichier chargé - {os.path.basename(file_path)}")
            except Exception as e:
                self.log(f"Erreur lors de la lecture du fichier: {str(e)}", "error")
                self.status_label.setText("Status: Erreur de lecture")
                QMessageBox.critical(self, "Erreur de lecture", f"Impossible de lire le fichier de configuration:\n{str(e)}")
                return
        elif not isinstance(config, str):
            # Si config n'est pas None, pas un booléen, pas une chaîne vide, mais pas une chaîne non plus
            self.log("Type de configuration non pris en charge", "error")
            self.status_label.setText("Status: Erreur - Type invalide")
            QMessageBox.critical(self, "Erreur de type", "Le type de configuration fourni n'est pas pris en charge.")
            return
            
        # Démarrage de l'injection
        self.log("Démarrage de l'injection de configuration optimisée...", "info")
        self.status_label.setText("Status: Injection en cours...")
        
        # Réinitialiser la barre de progression
        self.progress_bar.setValue(0)
        
        # Créer et configurer le thread d'injection
        self.injection_thread = ConfigInjectionThread(self.serial_connection, config)
        self.injection_thread.line_injected.connect(self.on_line_injected)
        self.injection_thread.injection_complete.connect(self.on_injection_complete)
        self.injection_thread.progress_update.connect(self.on_progress_update)
        
        # Désactiver les boutons pendant l'injection
        self.connect_button.setEnabled(False)
        self.disconnect_button.setEnabled(False)
        self.stop_injection_button.setEnabled(True)
        
        # Démarrer le thread
        self.injection_thread.start()

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
            self.injection_thread.wait(1000)  # Réduit de 2000ms à 1000ms
            
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

    def injectConsoleConfig(self):
        """Open a file dialog to select a configuration file and inject it via the console"""
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
                # Use our existing inject_configuration method
                self.inject_configuration(config)
                QMessageBox.information(self, "Succès", "Configuration injectée avec succès via la console.")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de l'injection : {e}")
    
    @classmethod
    def create_console_page(cls, parent=None):
        """Factory method to create a fully configured console page with back button"""
        # Create a container widget for the page
        page = QWidget(parent)
        layout = QVBoxLayout(page)
        
        # Create back button at the top
        back_button = QPushButton("Retour")
        back_button.setObjectName("backToHomeFromConsoleButton")
        back_button.setMinimumHeight(40)
        layout.addWidget(back_button)
        
        # Create serial connection instance
        serial_connection = cls(parent)
        layout.addWidget(serial_connection)
        
        # Store the back button as an attribute of the page for easy access
        page.backToHomeFromConsoleButton = back_button
        # Store the serial connection as an attribute of the page
        page.serialConnection = serial_connection
        
        return page
    
    def getBackButton(self):
        """Returns the back button if it exists"""
        if hasattr(self, 'backToHomeButton'):
            return self.backToHomeButton
        return None

    def set_home_callback(self, callback):
        """Set the callback for the back button"""
        if hasattr(self, 'backToHomeButton'):
            # Disconnect any existing connections
            try:
                self.backToHomeButton.clicked.disconnect()
            except:
                pass
            # Connect the new callback
            self.backToHomeButton.clicked.connect(callback)