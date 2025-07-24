import sys
import time
import paramiko
import re
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QLabel, QPushButton, QLineEdit, QProgressBar, QTextEdit, 
                            QFileDialog, QComboBox, QMessageBox, QGroupBox, QDialog,
                            QDialogButtonBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QObject

class ConfirmationDialog(QDialog):
    """Boîte de dialogue de confirmation personnalisée"""
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        # Configuration de la taille et du style
        self.resize(400, 200)
        self.setStyleSheet("QLabel { font-size: 12px; }")
        
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Message
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        
        # Boutons
        button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        
        layout.addWidget(self.message_label)
        layout.addWidget(button_box)

class SSHSignals(QObject):
    """Définit les signaux pour communiquer avec l'interface graphique"""
    update_log = pyqtSignal(str)
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    ios_version_detected = pyqtSignal(str)
    transfer_status = pyqtSignal(int, int)  # (bytes_transferred, total_bytes)

class IOSUpdateWorker(QThread):
    """Thread de travail pour effectuer la mise à jour IOS via SSH"""
    
    def __init__(self, remote_ip, username, password, enable_password, ios_filename, 
                 tftp_server_ip, check_only=False):
        super().__init__()
        self.remote_ip = remote_ip
        self.username = username
        self.password = password
        self.enable_password = enable_password
        self.ios_filename = ios_filename
        self.tftp_server_ip = tftp_server_ip
        self.check_only = check_only  # Si True, seulement vérifier la version IOS
        self.signals = SSHSignals()
        self.ssh_client = None
        self.shell = None
        self.stopped = False
        self.flash_location = None  # Sera détectée automatiquement
        self.current_ios = None
    
    def stop(self):
        """Arrête le processus de mise à jour"""
        self.stopped = True
        self.signals.update_log.emit(f"[{self.remote_ip}] Arrêt demandé par l'utilisateur")
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except:
                pass
    
    def run(self):
        """Exécute la vérification ou la mise à jour IOS"""
        try:
            if not self.connect_ssh():
                return
            
            # Détecter la version IOS actuelle
            self.signals.update_log.emit(f"[{self.remote_ip}] Détection de la version IOS...")
            self.signals.progress.emit(10)
            
            ios_version = self.detect_ios_version()
            if not ios_version:
                self.signals.error.emit("Impossible de détecter la version IOS")
                return
                
            self.current_ios = ios_version
            self.signals.ios_version_detected.emit(ios_version)
            
            # Détecter l'emplacement flash
            self.detect_flash_location()
            if not self.flash_location:
                self.signals.error.emit("Impossible de déterminer l'emplacement flash")
                return
                
            if self.check_only:
                self.signals.update_log.emit(f"[{self.remote_ip}] Version IOS actuelle: {ios_version}")
                self.signals.update_log.emit(f"[{self.remote_ip}] Emplacement flash détecté: {self.flash_location}")
                self.signals.progress.emit(100)
                self.signals.finished.emit()
                return
            
            # Vérification de l'espace disponible
            self.signals.update_log.emit(f"[{self.remote_ip}] Vérification de l'espace disponible...")
            self.signals.progress.emit(20)
            
            if not self.check_available_space():
                return
            
            # Configuration du TFTP
            self.signals.update_log.emit(f"[{self.remote_ip}] Configuration du blocksize TFTP...")
            self.signals.progress.emit(30)
            self.send_command_and_log("configure terminal", delay=1)
            self.send_command_and_log("ip tftp blocksize 8192", delay=1)
            self.send_command_and_log("exit", delay=1)
            
            # Transfert TFTP
            self.signals.update_log.emit(f"[{self.remote_ip}] Début du transfert TFTP...")
            self.signals.progress.emit(35)
            
            flash_path = f"{self.flash_location}"
            if not flash_path.endswith(':'):
                flash_path += ':'
                
            tftp_cmd = f"copy tftp://{self.tftp_server_ip}/{self.ios_filename} {flash_path}"
            
            # Lancement du transfert avec suivi de progression
            self.signals.update_log.emit(f"[{self.remote_ip}] Commande: {tftp_cmd}")
            self.monitor_tftp_transfer(tftp_cmd)
            
            if self.stopped:
                return
                
            # Configuration du système pour utiliser le nouvel IOS
            self.signals.update_log.emit(f"[{self.remote_ip}] Configuration du système pour utiliser le nouvel IOS...")
            self.signals.progress.emit(85)
            self.send_command_and_log("configure terminal", delay=1)
            
            # Nettoyer les anciennes commandes de boot si elles existent
            self.send_command_and_log("no boot system", delay=1)
            
            # Ajouter la nouvelle commande de boot
            boot_cmd = f"boot system {flash_path}/{self.ios_filename}"
            self.send_command_and_log(boot_cmd, delay=1)
            self.send_command_and_log("exit", delay=1)
            
            # Sauvegarde de la configuration
            self.signals.update_log.emit(f"[{self.remote_ip}] Sauvegarde de la configuration...")
            self.send_command_and_log("write memory", delay=3)
            
            # Redémarrage de l'équipement
            self.signals.update_log.emit(f"[{self.remote_ip}] Redémarrage de l'équipement...")
            self.signals.progress.emit(95)
            
            # Gestion du redémarrage avec vérification des différentes possibilités
            output = self.send_command_and_log("reload", delay=2)
            
            # Vérification pour la sauvegarde
            if "save" in output.lower() and "system configuration has been modified" in output.lower():
                output = self.send_command_and_log("n", delay=3)
            
            # Vérification pour la confirmation du redémarrage
            if "proceed with reload" in output.lower() or "[confirm]" in output.lower():
                self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation du redémarrage...")
                self.send_command_and_log("\n", delay=1, expect_response=False)
            
            # Seconde confirmation si nécessaire
            if self.shell.recv_ready():
                output = self.shell.recv(4096).decode('utf-8', errors='ignore')
                if "[confirm]" in output.lower() or "y/n" in output.lower():
                    self.send_command_and_log("\n", delay=1, expect_response=False)
            
            self.signals.update_log.emit(f"[{self.remote_ip}] Mise à jour terminée avec succès. L'équipement redémarre...")
            self.signals.update_log.emit(f"[{self.remote_ip}] Mise à jour de {self.current_ios} vers {self.ios_filename} terminée")
            self.signals.progress.emit(100)
            self.signals.finished.emit()
            
        except Exception as e:
            self.signals.error.emit(f"Erreur: {str(e)}")
        finally:
            if self.ssh_client:
                self.ssh_client.close()
    
    def connect_ssh(self):
        """Établit la connexion SSH"""
        try:
            self.signals.update_log.emit(f"[{self.remote_ip}] Connexion SSH...")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.remote_ip, username=self.username, password=self.password, timeout=10)
            self.shell = self.ssh_client.invoke_shell()
            self.shell.settimeout(30)
            
            # Attendre l'invite
            time.sleep(2)
            output = self.read_output()
            
            # Passer en mode enable si nécessaire
            if ">" in output:
                self.signals.update_log.emit(f"[{self.remote_ip}] Passage en mode privilégié...")
                self.shell.send("enable\n")
                time.sleep(1)
                prompt = self.read_output()
                if "Password" in prompt:
                    self.shell.send(f"{self.enable_password}\n")
                    time.sleep(2)
                    output = self.read_output()
            
            self.signals.update_log.emit(f"[{self.remote_ip}] Connecté avec succès")
            return True
        except Exception as e:
            self.signals.error.emit(f"Erreur de connexion SSH: {str(e)}")
            return False
    
    def detect_ios_version(self):
        """Détecte la version IOS actuelle"""
        try:
            self.send_command_and_log("terminal length 0", delay=1)  # Désactiver la pagination
            output = self.send_command_and_log("show version | include Version", delay=1)
            
            # Plusieurs patterns de version IOS possibles
            version_patterns = [
                r"Version\s+(\S+),",                # Format standard: "Version 15.2(4)M3,"
                r"Version\s+(\S+)\s+\[",            # Format alternatif: "Version 16.6.1 ["
                r"IOS.*Software.*Version\s+(\S+),", # Format IOS plus complet
                r"IOS.*Version\s+(\S+)"             # Format IOS XE
            ]
            
            for pattern in version_patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    ios_version = match.group(1)
                    self.signals.update_log.emit(f"[{self.remote_ip}] Version IOS détectée: {ios_version}")
                    return ios_version
            
            self.signals.update_log.emit(f"[{self.remote_ip}] Impossible de détecter la version IOS. Sortie complète:")
            self.signals.update_log.emit(output)
            return None
        except Exception as e:
            self.signals.error.emit(f"Erreur lors de la détection de la version IOS: {str(e)}")
            return None
    
    def detect_flash_location(self):
        """Détecte automatiquement l'emplacement flash"""
        try:
            # Liste des emplacements flash possibles
            possible_locations = ["flash:", "bootflash:", "disk0:", "usb0:", "slot0:"]
            
            for location in possible_locations:
                self.signals.update_log.emit(f"[{self.remote_ip}] Test de l'emplacement: {location}")
                output = self.send_command_and_log(f"dir {location}", delay=2)
                
                if "No such device" not in output and "Error" not in output:
                    self.flash_location = location
                    self.signals.update_log.emit(f"[{self.remote_ip}] Emplacement flash détecté: {location}")
                    return
            
            # Si aucun emplacement n'est trouvé, essayer flash: par défaut
            self.flash_location = "flash:"
            self.signals.update_log.emit(f"[{self.remote_ip}] Aucun emplacement flash détecté automatiquement. Utilisation de: {self.flash_location}")
        except Exception as e:
            self.signals.error.emit(f"Erreur lors de la détection de l'emplacement flash: {str(e)}")
            self.flash_location = "flash:"  # Valeur par défaut
    
    def check_available_space(self):
        """Vérifie l'espace disponible sur le flash"""
        try:
            # Exécuter la commande dir pour vérifier l'espace
            dir_cmd = f"dir {self.flash_location}"
            self.send_command_and_log(dir_cmd, delay=2)
            dir_output = self.read_output()
            
            # Rechercher les informations sur l'espace disponible
            available_bytes_match = re.search(r"(\d+) bytes free", dir_output)
            if available_bytes_match:
                available_bytes = int(available_bytes_match.group(1))
                # Taille estimée du fichier IOS (à adapter selon vos besoins)
                estimated_ios_size = 50 * 1024 * 1024  # 50 Mo par défaut
                
                if available_bytes < estimated_ios_size:
                    self.signals.error.emit(f"Espace insuffisant sur {self.flash_location}: {available_bytes/1024/1024:.1f} Mo disponibles, besoin d'environ 50 Mo")
                    return False
                else:
                    self.signals.update_log.emit(f"[{self.remote_ip}] Espace suffisant sur {self.flash_location}: {available_bytes/1024/1024:.1f} Mo disponibles")
                    return True
            else:
                self.signals.update_log.emit(f"[{self.remote_ip}] Impossible de déterminer l'espace disponible, poursuite de l'opération...")
                return True
        except Exception as e:
            self.signals.error.emit(f"Erreur lors de la vérification de l'espace disponible: {str(e)}")
            return False
    
    def monitor_tftp_transfer(self, tftp_cmd):
        """Surveille le transfert TFTP et met à jour la progression"""
        try:
            # Initialiser la progression au début du transfert
            self.signals.progress.emit(40)
            self.signals.update_log.emit(f"[{self.remote_ip}] Initialisation du transfert TFTP...")
            
            self.shell.send(tftp_cmd + "\n")
            time.sleep(1)
            
            # Répondre aux questions éventuelles
            prompt = self.read_output()
            if "Address or name of remote host" in prompt:
                self.shell.send(f"{self.tftp_server_ip}\n")
                time.sleep(1)
                prompt = self.read_output()
            
            if "Source filename" in prompt:
                self.shell.send(f"{self.ios_filename}\n")
                time.sleep(1)
                prompt = self.read_output()
            
            if "Destination filename" in prompt:
                destination = f"{self.ios_filename}"
                self.shell.send(f"{destination}\n")
                time.sleep(1)
                prompt = self.read_output()
            
            # Confirmation d'écrasement de fichier
            if "already existing" in prompt.lower() and "confirm" in prompt.lower():
                self.signals.update_log.emit(f"[{self.remote_ip}] Fichier existant détecté. Confirmation d'écrasement...")
                self.shell.send("\n")  # Confirmer écrasement
                time.sleep(1)
                prompt = self.read_output()
            
            # Surveillance du transfert
            start_time = time.time()
            transfer_complete = False
            last_message_time = time.time()
            
            # Informer l'utilisateur que le transfert commence
            self.signals.update_log.emit(f"[{self.remote_ip}] Téléchargement en cours. Ce processus peut prendre plusieurs minutes...")
            self.signals.progress.emit(45)
            
            while not transfer_complete and not self.stopped:
                if self.shell.recv_ready():
                    output = self.shell.recv(4096).decode('utf-8', errors='ignore')
                    
                    # Ne pas spammer le log, afficher seulement des mises à jour significatives
                    if "!" in output or "bytes copied" in output or "Error" in output:
                        self.signals.update_log.emit(output)
                    
                    # Recherche des informations de progression
                    bytes_match = re.search(r"(\d+)/(\d+) bytes", output)
                    if bytes_match:
                        bytes_transferred = int(bytes_match.group(1))
                        total_bytes = int(bytes_match.group(2))
                        progress_percent = min(80, 45 + int(bytes_transferred * 35 / total_bytes))
                        self.signals.progress.emit(progress_percent)
                        
                        # Mise à jour régulière du statut (pas plus d'une fois toutes les 3 secondes)
                        current_time = time.time()
                        if current_time - last_message_time > 3:
                            percentage = int(bytes_transferred * 100 / total_bytes)
                            self.signals.update_log.emit(f"[{self.remote_ip}] Transfert: {bytes_transferred/1024/1024:.1f} Mo / {total_bytes/1024/1024:.1f} Mo ({percentage}%)")
                            last_message_time = current_time
                    
                    # Vérifier si le transfert est terminé
                    if "bytes copied" in output and ("sec" in output or "OK" in output):
                        transfer_complete = True
                        self.signals.update_log.emit(f"[{self.remote_ip}] Transfert TFTP terminé avec succès")
                        self.signals.progress.emit(80)
                    
                    # Vérifier les erreurs
                    if "Error" in output or "failed" in output.lower() or "timed out" in output.lower():
                        self.signals.error.emit(f"Erreur durant le transfert TFTP: {output}")
                        return
                
                time.sleep(0.5)
                
                # Envoyer un signal de vie occasionnel pour éviter les timeouts
                current_time = time.time()
                if current_time - last_message_time > 60:
                    elapsed_minutes = int((current_time - start_time) / 60)
                    self.signals.update_log.emit(f"[{self.remote_ip}] Transfert en cours depuis {elapsed_minutes} minutes...")
                    last_message_time = current_time
                
                # Timeout de sécurité (30 minutes)
                if time.time() - start_time > 1800:
                    self.signals.error.emit("Timeout: Le transfert TFTP a pris trop de temps (30 minutes)")
                    return
        except Exception as e:
            self.signals.error.emit(f"Erreur durant le transfert TFTP: {str(e)}")
    
    def send_command_and_log(self, command, delay=0.5, expect_response=True):
        """Envoie une commande, attend et retourne la réponse"""
        try:
            if command:
                self.shell.send(command + "\n")
            
            time.sleep(delay)
            
            if expect_response:
                output = self.read_output()
                if command:
                    self.signals.update_log.emit(f"[{self.remote_ip}] Commande: {command}")
                    if output.strip():  # N'afficher que si la sortie n'est pas vide
                        self.signals.update_log.emit(output)
                return output
            return ""
        except Exception as e:
            self.signals.error.emit(f"Erreur lors de l'envoi de la commande '{command}': {str(e)}")
            return ""
    
    def read_output(self):
        """Lit la sortie disponible sur la connexion SSH"""
        output = ""
        if self.shell.recv_ready():
            while self.shell.recv_ready():
                output += self.shell.recv(4096).decode('utf-8', errors='ignore')
                time.sleep(0.1)
        return output


class CiscoDeviceConnector:
    """Classe utilitaire pour la connexion aux équipements Cisco"""
    
    @staticmethod
    def connect(ip, username, password, enable_password=None, timeout=10):
        """Établit une connexion SSH et retourne le client et le shell"""
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh_client.connect(ip, username=username, password=password, timeout=timeout)
            shell = ssh_client.invoke_shell()
            shell.settimeout(timeout)
            
            # Attendre l'invite
            time.sleep(2)
            output = ""
            if shell.recv_ready():
                output = shell.recv(9999).decode('utf-8', errors='ignore')
            
            # Si un mot de passe enable est fourni, passer en mode privilégié
            if enable_password:
                shell.send("enable\n")
                time.sleep(1)
                if shell.recv_ready():
                    resp = shell.recv(9999).decode('utf-8', errors='ignore')
                    if "password" in resp.lower():
                        shell.send(f"{enable_password}\n")
                        time.sleep(1)
                        if shell.recv_ready():
                            shell.recv(9999)  # Vider le buffer
            
            return ssh_client, shell
            
        except Exception as e:
            if ssh_client:
                ssh_client.close()
            raise ConnectionError(f"Erreur de connexion SSH à {ip}: {str(e)}")


class UpdateTab(QMainWindow):
    """Interface utilisateur pour la mise à jour IOS Cisco avec workflow amélioré"""
    
    def __init__(self):
        super().__init__()
        self.worker = None
        self.current_ios_version = None
        self.step = 0  # 0: Connexion, 1: Vérification IOS, 2: Confirmation, 3: TFTP, 4: Mise à jour
        self.initUI()
    
    def initUI(self):
        """Initialise l'interface utilisateur"""
        self.setWindowTitle("Mise à jour IOS Cisco")
        self.setGeometry(100, 100, 800, 600)
        
        # Widget principal
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Groupe de connexion
        connection_group = QGroupBox("Paramètres de connexion")
        connection_layout = QVBoxLayout()
        
        # Adresse IP
        ip_layout = QHBoxLayout()
        ip_label = QLabel("Adresse IP de l'équipement:")
        self.ip_input = QLineEdit()
        ip_layout.addWidget(ip_label)
        ip_layout.addWidget(self.ip_input)
        connection_layout.addLayout(ip_layout)
        
        # Identifiants
        creds_layout = QHBoxLayout()
        username_label = QLabel("Nom d'utilisateur:")
        self.username_input = QLineEdit()
        password_label = QLabel("Mot de passe:")
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        enable_label = QLabel("Mot de passe enable:")
        self.enable_input = QLineEdit()
        self.enable_input.setEchoMode(QLineEdit.Password)
        
        creds_layout.addWidget(username_label)
        creds_layout.addWidget(self.username_input)
        creds_layout.addWidget(password_label)
        creds_layout.addWidget(self.password_input)
        creds_layout.addWidget(enable_label)
        creds_layout.addWidget(self.enable_input)
        connection_layout.addLayout(creds_layout)
        
        connection_group.setLayout(connection_layout)
        main_layout.addWidget(connection_group)
        
        # Groupe TFTP
        tftp_group = QGroupBox("Paramètres TFTP")
        tftp_layout = QVBoxLayout()
        
        # Serveur TFTP
        tftp_server_layout = QHBoxLayout()
        tftp_server_label = QLabel("Adresse IP du serveur TFTP:")
        self.tftp_server_input = QLineEdit()
        tftp_server_layout.addWidget(tftp_server_label)
        tftp_server_layout.addWidget(self.tftp_server_input)
        tftp_layout.addLayout(tftp_server_layout)
        
        # Fichier IOS
        ios_file_layout = QHBoxLayout()
        ios_file_label = QLabel("Fichier IOS:")
        self.ios_file_input = QLineEdit()
        browse_button = QPushButton("Parcourir")
        browse_button.clicked.connect(self.browse_ios_file)
        ios_file_layout.addWidget(ios_file_label)
        ios_file_layout.addWidget(self.ios_file_input)
        ios_file_layout.addWidget(browse_button)
        tftp_layout.addLayout(ios_file_layout)
        
        tftp_group.setLayout(tftp_layout)
        main_layout.addWidget(tftp_group)
        
        # Information version actuelle
        info_group = QGroupBox("Information sur l'équipement")
        info_layout = QVBoxLayout()
        
        self.current_ios_label = QLabel("Version IOS actuelle: Non détectée")
        self.current_ios_label.setStyleSheet("font-weight: bold; color: #3498db;")
        info_layout.addWidget(self.current_ios_label)
        
        info_group.setLayout(info_layout)
        main_layout.addWidget(info_group)
        
        # Barre de progression
        progress_layout = QHBoxLayout()
        progress_label = QLabel("Progression:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_layout.addWidget(progress_label)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)
        
        # Zone de log
        log_label = QLabel("Journal d'opérations:")
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_text)
        
        # Boutons d'action
        button_layout = QHBoxLayout()
        self.connect_button = QPushButton("Se connecter")
        self.connect_button.clicked.connect(self.connect_to_device)
        
        self.update_button = QPushButton("Procéder à la mise à jour")
        self.update_button.clicked.connect(self.start_update_process)
        self.update_button.setEnabled(False)
        
        self.stop_button = QPushButton("Arrêter")
        self.stop_button.clicked.connect(self.stop_process)
        self.stop_button.setEnabled(False)
        
        button_layout.addWidget(self.connect_button)
        button_layout.addWidget(self.update_button)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        
        # Remplir avec des valeurs par défaut
        self.ip_input.setText("192.168.1.1")
        self.username_input.setText("admin")
        self.tftp_server_input.setText("192.168.1.100")
        
        # Message de bienvenue
        self.log_text.append("Bienvenue dans l'outil de mise à jour IOS Cisco")
        self.log_text.append("1. Connectez-vous d'abord à l'équipement pour vérifier sa version IOS")
        self.log_text.append("2. Configurez ensuite le serveur TFTP et choisissez la nouvelle image IOS")
        self.log_text.append("3. Cliquez sur 'Procéder à la mise à jour' pour lancer le processus")
    
    def browse_ios_file(self):
        """Ouvre un dialogue pour sélectionner le fichier IOS"""
        filename, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier IOS", "", "Fichiers IOS (*.bin *.image);;Tous les fichiers (*)")
        if filename:
            # Extraire juste le nom du fichier sans le chemin
            import os
            self.ios_file_input.setText(os.path.basename(filename))
    
    def connect_to_device(self):
        """Se connecte à l'équipement et récupère la version IOS"""
        # Validation des entrées
        if not self.ip_input.text() or not self.username_input.text() or not self.password_input.text():
            QMessageBox.warning(self, "Champs manquants", "Veuillez remplir tous les champs de connexion.")
            return
        
        # Récupération des paramètres
        remote_ip = self.ip_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        enable_password = self.enable_input.text() or password
        
        # Désactiver les boutons pendant la connexion
        self.connect_button.setEnabled(False)
        self.update_button.setEnabled(False)
        
        # Créer et démarrer le worker pour la vérification uniquement
        self.worker = IOSUpdateWorker(
            remote_ip, username, password, enable_password,
            "", "", check_only=True
        )
        
        # Connexion des signaux
        self.worker.signals.update_log.connect(self.update_log)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.connection_finished)
        self.worker.signals.error.connect(self.handle_error)
        self.worker.signals.ios_version_detected.connect(self.update_ios_version)
        
        # Mise à jour de l'interface
        self.progress_bar.setValue(0)
        self.log_text.append("\n--- CONNEXION À L'ÉQUIPEMENT ---\n")
        self.step = 1
        
        # Démarrer le thread
        self.worker.start()
        self.stop_button.setEnabled(True)
    
    def update_ios_version(self, ios_version):
        """Met à jour l'affichage de la version IOS détectée"""
        self.current_ios_version = ios_version
        self.current_ios_label.setText(f"Version IOS actuelle: {ios_version}")
    
    def connection_finished(self):
        """Gère la fin du processus de connexion"""
        self.connect_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        
        if self.current_ios_version:
            self.update_button.setEnabled(True)
            self.log_text.append("\n--- CONNEXION RÉUSSIE ---")
            self.log_text.append("Vous pouvez maintenant configurer le serveur TFTP et choisir la nouvelle image IOS.")
            self.log_text.append("Puis cliquez sur 'Procéder à la mise à jour' pour continuer.")
    
    def start_update_process(self):
        """Lance le processus de mise à jour avec confirmation"""
        # Vérifier que tous les champs nécessaires sont remplis
        if not self.tftp_server_input.text() or not self.ios_file_input.text():
            QMessageBox.warning(self, "Champs manquants", "Veuillez remplir l'adresse du serveur TFTP et le nom du fichier IOS.")
            return
        
        # Première confirmation
        dialog = ConfirmationDialog(
            "Confirmation de mise à jour",
            f"Voulez-vous procéder à la mise à jour de l'équipement {self.ip_input.text()} ?\n\n"
            f"Version actuelle: {self.current_ios_version}\n"
            f"Nouvelle version: {self.ios_file_input.text()}",
            self
        )
        
        if dialog.exec_() != QDialog.Accepted:
            return
            
        # Deuxième confirmation pour le serveur TFTP
        dialog = ConfirmationDialog(
            "Serveur TFTP",
            f"Veuillez activer votre serveur TFTP à l'adresse {self.tftp_server_input.text()} "
            f"et assurez-vous que le fichier {self.ios_file_input.text()} est accessible.\n\n"
            "Êtes-vous prêt à continuer ?",
            self
        )
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # Lancer le processus de mise à jour
        remote_ip = self.ip_input.text()
        username = self.username_input.text()
        password = self.password_input.text()
        enable_password = self.enable_input.text() or password
        ios_filename = self.ios_file_input.text()
        tftp_server_ip = self.tftp_server_input.text()
        
        # Créer le worker pour la mise à jour
        self.worker = IOSUpdateWorker(
            remote_ip, username, password, enable_password,
            ios_filename, tftp_server_ip
        )
        
        # Connexion des signaux
        self.worker.signals.update_log.connect(self.update_log)
        self.worker.signals.progress.connect(self.update_progress)
        self.worker.signals.finished.connect(self.update_finished)
        self.worker.signals.error.connect(self.handle_error)
        self.worker.signals.ios_version_detected.connect(self.update_ios_version)
        
        # Mise à jour de l'interface
        self.connect_button.setEnabled(False)
        self.update_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.append("\n--- DÉMARRAGE DU PROCESSUS DE MISE À JOUR ---\n")
        self.step = 3
        
        # Démarrer le thread
        self.worker.start()
    
    def stop_process(self):
        """Arrête le processus en cours"""
        if self.worker:
            self.worker.stop()
            self.log_text.append("\n--- ARRÊT DEMANDÉ PAR L'UTILISATEUR ---\n")
    
    @pyqtSlot(str)
    def update_log(self, message):
        """Met à jour la zone de log"""
        self.log_text.append(message)
        # Défiler automatiquement vers le bas
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    @pyqtSlot(int)
    def update_progress(self, value):
        """Met à jour la barre de progression"""
        self.progress_bar.setValue(value)
    
    @pyqtSlot()
    def update_finished(self):
        """Gère la fin du processus de mise à jour"""
        self.connect_button.setEnabled(True)
        self.update_button.setEnabled(False)  # Désactivé car mise à jour terminée
        self.stop_button.setEnabled(False)
        
        # Afficher message de fin
        QMessageBox.information(self, "Mise à jour terminée", 
            f"La mise à jour de l'équipement {self.ip_input.text()} est terminée.\n\n"
            f"L'équipement a été redémarré avec la nouvelle version IOS: {self.ios_file_input.text()}")
        
        self.log_text.append("\n--- MISE À JOUR TERMINÉE AVEC SUCCÈS ---\n")
        self.log_text.append("L'équipement redémarre avec la nouvelle version IOS.")
        self.log_text.append("Veuillez patienter quelques minutes avant de vous reconnecter.")
    
    @pyqtSlot(str)
    def handle_error(self, error_message):
        """Gère les erreurs"""
        self.log_text.append(f"ERREUR: {error_message}")
        self.connect_button.setEnabled(True)
        self.update_button.setEnabled(self.current_ios_version is not None)
        self.stop_button.setEnabled(False)
        QMessageBox.critical(self, "Erreur", error_message)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UpdateTab()
    window.show()
    sys.exit(app.exec_())