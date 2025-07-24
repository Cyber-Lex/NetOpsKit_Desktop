import os
import time
import re
import paramiko
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRunnable, QObject

class UpdateWorkerSignals(QObject):
    finished = pyqtSignal(str, dict)
    update_log = pyqtSignal(str)
    progress = pyqtSignal(int)
    device_detected = pyqtSignal(dict)
    ios_version = pyqtSignal(str)

class UpdateWorker(QRunnable):
    """Worker pour la mise à jour d'un équipement par TFTP"""
    def __init__(self, remote_ip, username, password, enable_password=None, 
                 firmware_file=None, tftp_server_ip=None, check_only=False):
        super().__init__()
        self.remote_ip = remote_ip
        self.username = username
        self.password = password
        self.enable_password = enable_password or password
        self.firmware_file = firmware_file
        self.tftp_server_ip = tftp_server_ip
        self.check_only = check_only
        self.signals = UpdateWorkerSignals()
        self.stop_requested = False
        self.ssh = None
        self.channel = None
        self.flash_location = None

    def request_stop(self):
        self.stop_requested = True
        if self.ssh:
            try:
                self.ssh.close()
            except:
                pass

    def run(self):
        try:
            self.signals.update_log.emit(f"[{self.remote_ip}] Connexion SSH...")
            self.signals.progress.emit(5)
            
            # Se connecter à l'équipement
            try:
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(
                    hostname=self.remote_ip,
                    username=self.username,
                    password=self.password,
                    timeout=10
                )
                self.channel = self.ssh.invoke_shell()
                time.sleep(2)  # Attendre l'invite
                
                # Passer en mode enable si nécessaire
                output = self.read_output()
                if ">" in output:
                    self.send_command("enable", delay=1)
                    prompt = self.read_output()
                    if "Password" in prompt:
                        self.send_command(self.enable_password, delay=2)
                
                self.signals.update_log.emit(f"[{self.remote_ip}] Connecté avec succès")
                self.signals.progress.emit(10)
            except Exception as ce:
                error_msg = f"Erreur de connexion à {self.remote_ip}: {str(ce)}"
                self.signals.update_log.emit(error_msg)
                self.signals.finished.emit(error_msg, {'status': 'error'})
                return

            # Désactiver la pagination
            self.send_command("terminal length 0", delay=1)
            
            # Détecter la version IOS
            self.signals.update_log.emit(f"[{self.remote_ip}] Détection de la version IOS...")
            self.signals.progress.emit(20)
            
            current_ios = self.detect_ios_version()
            if not current_ios:
                error_msg = f"[{self.remote_ip}] Impossible de détecter la version IOS"
                self.signals.update_log.emit(error_msg)
                self.signals.finished.emit(error_msg, {'status': 'error'})
                return
            
            self.signals.ios_version.emit(current_ios)
            self.signals.update_log.emit(f"[{self.remote_ip}] Version IOS actuelle: {current_ios}")
            
            # Détecter l'emplacement flash
            self.detect_flash_location()
            
            # Si on vérifie seulement, terminer ici
            if self.check_only:
                device_info = {
                    'ios_version': current_ios,
                    'flash_location': self.flash_location
                }
                self.signals.device_detected.emit(device_info)
                self.signals.progress.emit(100)
                self.signals.finished.emit(f"Équipement {self.remote_ip} détecté avec IOS {current_ios}", 
                                          {'status': 'success', 'device_info': device_info})
                return
            
            # Vérifier l'espace disponible
            if not self.check_available_space():
                return
            
            # Configuration du TFTP
            self.signals.update_log.emit(f"[{self.remote_ip}] Configuration du blocksize TFTP...")
            self.signals.progress.emit(30)
            self.send_command("configure terminal", delay=1)
            self.send_command("ip tftp blocksize 8192", delay=1)
            self.send_command("exit", delay=1)
            
            # Transfert TFTP
            self.signals.progress.emit(35)
            tftp_cmd = f"copy tftp://{self.tftp_server_ip}/{self.firmware_file} {self.flash_location}"
            self.signals.update_log.emit(f"[{self.remote_ip}] Début du transfert TFTP: {tftp_cmd}")
            
            # Envoyer la commande TFTP
            self.channel.send(tftp_cmd + "\n")
            time.sleep(2)
            
            # Gérer les invites interactives
            output = self.read_output()
            if "Address or name of remote host" in output:
                self.send_command(self.tftp_server_ip, delay=1)
                output = self.read_output()
            
            if "Source filename" in output:
                self.send_command(self.firmware_file, delay=1)
                output = self.read_output()
            
            if "Destination filename" in output:
                self.send_command("", delay=1)  # Accepter le nom par défaut
                output = self.read_output()
            
            # Gérer l'écrasement de fichier
            if "existing" in output.lower() and "confirm" in output.lower():
                self.send_command("", delay=1)  # Confirmer l'écrasement
            
            # Surveiller le transfert
            self.signals.update_log.emit(f"[{self.remote_ip}] Transfert TFTP en cours...")
            self.signals.progress.emit(40)
            
            transfer_start = time.time()
            last_progress = time.time()
            transfer_complete = False
            
            while not transfer_complete and not self.stop_requested:
                if self.channel.recv_ready():
                    output = self.channel.recv(4096).decode("utf-8", errors="ignore")
                    
                    # Afficher des mises à jour significatives
                    if "!" in output or "bytes copied" in output or "Error" in output:
                        self.signals.update_log.emit(output)
                    
                    # Mise à jour de la progression
                    current_time = time.time()
                    elapsed = current_time - transfer_start
                    if current_time - last_progress > 5:  # Toutes les 5 secondes
                        progress = min(75, 40 + int(elapsed/300 * 35))  # Max 5 minutes pour 75%
                        self.signals.progress.emit(progress)
                        self.signals.update_log.emit(f"[{self.remote_ip}] Transfert en cours depuis {int(elapsed)} secondes...")
                        last_progress = current_time
                    
                    # Vérifier si le transfert est terminé
                    if "bytes copied" in output and "sec" in output:
                        transfer_complete = True
                        self.signals.progress.emit(75)
                        self.signals.update_log.emit(f"[{self.remote_ip}] Transfert TFTP terminé avec succès")
                    
                    # Vérifier les erreurs
                    if "Error" in output or "failed" in output.lower() or "timed out" in output.lower():
                        error_msg = f"Erreur durant le transfert TFTP: {output}"
                        self.signals.update_log.emit(error_msg)
                        self.signals.finished.emit(error_msg, {'status': 'error'})
                        return
                
                time.sleep(0.5)
                
                # Timeout après 30 minutes
                if time.time() - transfer_start > 1800:
                    error_msg = f"[{self.remote_ip}] Timeout après 30 minutes"
                    self.signals.update_log.emit(error_msg)
                    self.signals.finished.emit(error_msg, {'status': 'error'})
                    return
            
            if self.stop_requested:
                self.signals.update_log.emit(f"[{self.remote_ip}] Arrêt demandé, transfert annulé")
                return
            
            # Configurer l'équipement pour utiliser la nouvelle IOS
            self.signals.update_log.emit(f"[{self.remote_ip}] Configuration du système pour utiliser le nouvel IOS...")
            self.signals.progress.emit(80)
            
            self.send_command("configure terminal", delay=1)
            self.send_command("no boot system", delay=1)  # Supprimer les anciennes commandes de boot
            boot_cmd = f"boot system {self.flash_location}{self.firmware_file}"
            self.send_command(boot_cmd, delay=1)
            self.send_command("exit", delay=1)
            
            # Sauvegarde de la configuration
            self.signals.update_log.emit(f"[{self.remote_ip}] Sauvegarde de la configuration...")
            self.send_command("write memory", delay=3)
            self.signals.progress.emit(85)
            
            # Redémarrage de l'équipement
            self.signals.update_log.emit(f"[{self.remote_ip}] Redémarrage de l'équipement...")
            self.signals.progress.emit(90)
            
            output = self.send_command("reload", delay=2)
            
            # Gérer les différentes confirmations possibles
            if "save" in output.lower():
                output = self.send_command("n", delay=2)
                
            if "confirm" in output.lower() or "proceed" in output.lower():
                output = self.send_command("", delay=1, expect_response=False)
                
            # Seconde confirmation si nécessaire
            time.sleep(2)
            if self.channel.recv_ready():
                output = self.channel.recv(4096).decode("utf-8", errors="ignore")
                if "confirm" in output.lower():
                    self.channel.send("\n")
            
            self.signals.update_log.emit(f"[{self.remote_ip}] Mise à jour terminée, l'équipement redémarre...")
            self.signals.progress.emit(100)
            
            # Fermer proprement la connexion SSH
            try:
                if self.channel:
                    self.channel.close()
                if self.ssh:
                    self.ssh.close()
            except:
                pass
                
            success_msg = f"Mise à jour de {self.remote_ip} de {current_ios} vers {self.firmware_file} terminée avec succès. L'équipement redémarre."
            self.signals.finished.emit(success_msg, {
                'status': 'success', 
                'old_ios': current_ios,
                'new_ios': self.firmware_file
            })
            
        except Exception as e:
            error_msg = f"[{self.remote_ip}] Erreur lors de la mise à jour: {str(e)}"
            self.signals.update_log.emit(error_msg)
            self.signals.finished.emit(error_msg, {'status': 'error'})
            
            # Fermer la connexion SSH en cas d'erreur
            try:
                if self.channel:
                    self.channel.close()
                if self.ssh:
                    self.ssh.close()
            except:
                pass

    def read_output(self):
        """Lit la sortie disponible sur le canal SSH"""
        output = ""
        if self.channel.recv_ready():
            time.sleep(0.5)  # Laisser le temps pour que les données arrivent
            while self.channel.recv_ready():
                output += self.channel.recv(4096).decode("utf-8", errors="ignore")
                time.sleep(0.1)
        return output

    def send_command(self, command, delay=1, expect_response=True):
        """Envoie une commande et lit la réponse"""
        if self.stop_requested:
            return ""
            
        try:
            if command:
                self.signals.update_log.emit(f"[{self.remote_ip}] Commande: {command}")
                self.channel.send(command + "\n")
            else:
                self.channel.send("\n")  # Juste entrée pour confirmer
                
            time.sleep(delay)
            
            if expect_response:
                output = self.read_output()
                return output
            return ""
        except Exception as e:
            self.signals.update_log.emit(f"[{self.remote_ip}] Erreur lors de l'envoi de la commande: {str(e)}")
            return ""

    def detect_ios_version(self):
        """Détecte la version IOS actuelle de l'équipement"""
        try:
            output = self.send_command("show version | include Version", delay=2)
            
            # Plusieurs formats possibles
            version_patterns = [
                r"Version\s+(\S+),",                # Format standard: "Version 15.2(4)M3,"
                r"Version\s+(\S+)\s+\[",            # Format alternatif: "Version 16.6.1 ["
                r"IOS.*Software.*Version\s+(\S+),", # Format IOS plus complet
                r"IOS.*Version\s+(\S+)"             # Format IOS XE
            ]
            
            for pattern in version_patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return match.group(1)
                    
            # Si non trouvé, tenter de récupérer plus d'information
            self.signals.update_log.emit("Version IOS non détectée, tentative avec 'show version'")
            output = self.send_command("show version", delay=2)
            for pattern in version_patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return match.group(1)
                    
            return None
        except Exception as e:
            self.signals.update_log.emit(f"Erreur lors de la détection de la version IOS: {str(e)}")
            return None

    def detect_flash_location(self):
        """Détecte l'emplacement flash"""
        try:
            possible_locations = ["flash:", "bootflash:", "disk0:", "usb0:", "slot0:"]
            
            for location in possible_locations:
                output = self.send_command(f"dir {location}", delay=2)
                if "No such device" not in output and "% Error" not in output:
                    self.flash_location = location
                    self.signals.update_log.emit(f"[{self.remote_ip}] Emplacement flash détecté: {location}")
                    return
                    
            # Par défaut si aucun n'est trouvé
            self.flash_location = "flash:"
            self.signals.update_log.emit(f"[{self.remote_ip}] Emplacement flash par défaut: {self.flash_location}")
        except Exception as e:
            self.signals.update_log.emit(f"Erreur lors de la détection de l'emplacement flash: {str(e)}")
            self.flash_location = "flash:"

    def check_available_space(self):
        """Vérifie l'espace disponible dans la flash"""
        try:
            output = self.send_command(f"dir {self.flash_location}", delay=2)
            
            # Rechercher l'espace disponible
            space_match = re.search(r"(\d+) bytes free", output)
            if space_match:
                free_space = int(space_match.group(1))
                self.signals.update_log.emit(f"[{self.remote_ip}] Espace disponible: {free_space/1024/1024:.2f} Mo")
                
                # Estimer une taille minimale requise (50 Mo)
                if free_space < 50 * 1024 * 1024:
                    error_msg = f"Espace insuffisant dans {self.flash_location}: {free_space/1024/1024:.2f} Mo (minimum 50 Mo recommandé)"
                    self.signals.update_log.emit(error_msg)
                    self.signals.finished.emit(error_msg, {'status': 'error'})
                    return False
                return True
            else:
                # Impossible de déterminer l'espace, continuer avec avertissement
                self.signals.update_log.emit(f"[{self.remote_ip}] Impossible de déterminer l'espace disponible, poursuite du processus")
                return True
        except Exception as e:
            self.signals.update_log.emit(f"Erreur lors de la vérification de l'espace: {str(e)}")
            return True  # Continuer malgré l'erreur

# Classe pour l'onglet de mise à jour de l'application (non utilisée dans le workflow demandé)
class AppUpdateTab(QWidget):
    """Onglet pour la gestion des mises à jour de l'application"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        """Initialise l'interface utilisateur de l'onglet de mise à jour"""
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Mises à jour", self)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        
        # Informations sur la version actuelle
        self.current_version_label = QLabel("Version actuelle: 1.0.0", self)
        
        # Bouton de vérification
        self.check_button = QPushButton("Vérifier les mises à jour", self)
        
        # Barre de progression (cachée par défaut)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        
        # Résultat de la vérification
        self.result_label = QLabel("", self)
        self.result_label.setAlignment(Qt.AlignCenter)
        
        # Bouton de mise à jour (caché par défaut)
        self.update_button = QPushButton("Installer la mise à jour", self)
        self.update_button.setVisible(False)
        
        # Ajout des widgets au layout
        layout.addWidget(title_label)
        layout.addWidget(self.current_version_label)
        layout.addWidget(self.check_button)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.result_label)
        layout.addWidget(self.update_button)
        layout.addStretch()
