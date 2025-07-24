import os
import time
import json
import threading
import schedule
from datetime import datetime, timedelta
import jinja2

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTabWidget, QFormLayout, QLineEdit, QPushButton,
    QMessageBox, QFileDialog, QLabel, QHBoxLayout, QCheckBox, QProgressBar,
    QComboBox, QFrame, QApplication, QTextEdit, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QDialogButtonBox, QInputDialog
)
from PyQt5.QtCore import Qt, QThreadPool, QRunnable, pyqtSignal, QObject
from PyQt5.QtGui import QColor

import paramiko
from scp import SCPClient
from ui.modern_dialogs import ModernMessageBox

#########################
# INVENTAIRE MINIMAL
#########################

class DeviceInventory:
    """Inventaire minimal pour la gestion des tâches planifiées"""
    def __init__(self, file_path: str = "device_inventory.json"):
        self.file_path = file_path
        self.devices = {}
    def update_device_status(self, ip, status):
        # Implémentation minimale (peut être étendue)
        pass
    def update_backup_timestamp(self, ip):
        pass
    def get_all_devices(self):
        # Retourne une liste vide pour cet exemple
        return []

#########################
# TÂCHES PLANIFIÉES
#########################

class ScheduledTask:
    """Représente une tâche planifiée"""
    def __init__(self, task_id, task_type, device_ips, schedule_type, interval, local_folder="", username="", password="", enabled=True, last_run=None, next_run=None):
        self.task_id = task_id
        self.task_type = task_type      # "backup" ou "check"
        self.device_ips = device_ips
        self.schedule_type = schedule_type  # "minutes", "hourly", "daily", "weekly", "monthly"
        self.interval = interval
        self.local_folder = local_folder
        self.username = username
        self.password = password
        self.enabled = enabled
        self.last_run = last_run
        self.next_run = next_run

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "device_ips": self.device_ips,
            "schedule_type": self.schedule_type,
            "interval": self.interval,
            "local_folder": self.local_folder,
            "username": self.username,
            "password": self.password,
            "enabled": self.enabled,
            "last_run": self.last_run,
            "next_run": self.next_run
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            task_id=data.get("task_id", ""),
            task_type=data.get("task_type", ""),
            device_ips=data.get("device_ips", []),
            schedule_type=data.get("schedule_type", ""),
            interval=data.get("interval", 0),
            local_folder=data.get("local_folder", ""),
            username=data.get("username", ""),
            password=data.get("password", ""),
            enabled=data.get("enabled", True),
            last_run=data.get("last_run"),
            next_run=data.get("next_run")
        )

class ScheduleManager:
    """Gestionnaire des tâches planifiées"""
    def __init__(self, inventory, file_path: str = "scheduled_tasks.json"):
        self.file_path = file_path
        self.tasks = {}
        self.inventory = inventory
        self.scheduler_thread = None
        self.running = False
        self.load()
    
    def add_task(self, task: ScheduledTask):
        self.tasks[task.task_id] = task
        self.save()
        self._update_schedule()
    
    def remove_task(self, task_id: str):
        if task_id in self.tasks:
            del self.tasks[task_id]
            self.save()
            self._update_schedule()
    
    def get_task(self, task_id: str):
        return self.tasks.get(task_id)
    
    def get_all_tasks(self):
        return list(self.tasks.values())
    
    def enable_task(self, task_id: str, enabled: bool = True):
        if task_id in self.tasks:
            self.tasks[task_id].enabled = enabled
            self.save()
            self._update_schedule()
    
    def update_task_last_run(self, task_id: str):
        if task_id in self.tasks:
            now = datetime.now()
            self.tasks[task_id].last_run = now.strftime("%Y-%m-%d %H:%M:%S")
            interval = self.tasks[task_id].interval
            stype = self.tasks[task_id].schedule_type
            if stype == "minutes":
                next_run = now + timedelta(minutes=interval)
            elif stype == "hourly":
                next_run = now + timedelta(hours=interval)
            elif stype == "daily":
                next_run = now + timedelta(days=interval)
            elif stype == "weekly":
                next_run = now + timedelta(weeks=interval)
            elif stype == "monthly":
                next_run = now + timedelta(days=30 * interval)
            else:
                next_run = now + timedelta(days=1)
            self.tasks[task_id].next_run = next_run.strftime("%Y-%m-%d %H:%M:%S")
            self.save()
    
    def load(self):
        # Pour simplifier, on démarre avec aucune tâche
        self.tasks = {}
    
    def save(self):
        # Pour cet exemple, la sauvegarde en fichier n'est pas implémentée
        pass
    
    def start_scheduler(self):
        if self.scheduler_thread and self.running:
            return
        self.running = True
        self._update_schedule()
        def run_scheduler():
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        self.scheduler_thread = threading.Thread(target=run_scheduler)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
    
    def stop_scheduler(self):
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        schedule.clear()
    
    def _update_schedule(self):
        schedule.clear()
        for tid, task in self.tasks.items():
            if not task.enabled:
                continue
            def execute_task(task_id=tid):
                task_obj = self.get_task(task_id)
                if not task_obj:
                    return
                self.update_task_last_run(task_id)
                if task_obj.task_type == "backup":
                    worker = BackupWorker(task_obj.device_ips[0], task_obj.username, task_obj.password, task_obj.local_folder)
                    worker.run()  # Exécution synchrone pour cet exemple
                elif task_obj.task_type == "check":
                    worker = HealthCheckWorker(task_obj.device_ips[0], task_obj.username, task_obj.password)
                    worker.run()
            stype = task.schedule_type
            if stype == "minutes":
                schedule.every(task.interval).minutes.do(execute_task)
            elif stype == "hourly":
                schedule.every(task.interval).hours.do(execute_task)
            elif stype == "daily":
                schedule.every(task.interval).days.do(execute_task)
            elif stype == "weekly":
                schedule.every(task.interval).weeks.do(execute_task)
            elif stype == "monthly":
                schedule.every(30 * task.interval).days.do(execute_task)

#########################
# WORKER CLASSES
#########################

# ----- RESET WORKER -----
class ResetWorkerSignals(QObject):
    finished = pyqtSignal(str)  # Message de fin
    update_log = pyqtSignal(str)  # Message de log
    progress_update = pyqtSignal(str, str, int)  # IP, message, pourcentage (0-100)

class ResetWorker(QRunnable):
    def __init__(self, remote_ip, username, password, device_type):
        super().__init__()
        self.remote_ip = remote_ip
        self.username = username
        self.password = password
        self.device_type = device_type  # "Routeur", "Switch" ou "Stormshield"
        self.signals = ResetWorkerSignals()

    def send_command_and_log(self, channel, command, delay=1, expect_response=True):
        log_message = f"[{self.remote_ip}] Envoi de la commande: {command.strip()}"
        self.signals.update_log.emit(log_message)
        channel.send(command)
        time.sleep(delay)
        output = ""
        if expect_response and channel.recv_ready():
            output = channel.recv(9999).decode("utf-8", errors="ignore")
            log_message = f"[{self.remote_ip}] Réponse reçue:\n{output}"
            self.signals.update_log.emit(log_message)
        return output

    def run(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.signals.update_log.emit(f"[{self.remote_ip}] Tentative de connexion...")
            ssh.connect(self.remote_ip, username=self.username, password=self.password, timeout=10)
            self.signals.update_log.emit(f"[{self.remote_ip}] Connecté")
            
            channel = ssh.invoke_shell()
            time.sleep(1)
            if channel.recv_ready():
                initial_output = channel.recv(9999).decode("utf-8", errors="ignore")
                self.signals.update_log.emit(f"[{self.remote_ip}] État initial:\n{initial_output}")
            
            if self.device_type.lower() == "routeur":
                output = self.send_command_and_log(channel, "erase startup-config\n", delay=2)
                if "[confirm]" in output:
                    output = self.send_command_and_log(channel, "\n", delay=5)
                elif "confirm" in output.lower():
                    output = self.send_command_and_log(channel, "y\n", delay=5)
                output = self.send_command_and_log(channel, "reload\n", delay=2)
                if "save" in output.lower() or "system configuration has been modified" in output.lower():
                    output = self.send_command_and_log(channel, "n\n", delay=3)
                    if "proceed with reload" in output.lower() or "[confirm]" in output:
                        self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation du redémarrage...")
                        output = self.send_command_and_log(channel, "\n", delay=1, expect_response=False)
                else:
                    if "[confirm]" in output:
                        self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation du redémarrage...")
                        output = self.send_command_and_log(channel, "\n", delay=1, expect_response=False)
                time.sleep(2)
                if channel.recv_ready():
                    output = channel.recv(9999).decode("utf-8", errors="ignore")
                    self.signals.update_log.emit(f"[{self.remote_ip}] Réponse reçue:\n{output}")
                    if "proceed with reload" in output.lower() or "[confirm]" in output:
                        self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation finale du redémarrage...")
                        self.send_command_and_log(channel, "\n", delay=1, expect_response=False)
                self.signals.update_log.emit(f"[{self.remote_ip}] Redémarrage en cours...")
            
            elif self.device_type.lower() == "switch":
                output = self.send_command_and_log(channel, "delete vlan.dat\n", delay=2)
                if "delete filename" in output.lower() or "[vlan.dat]?" in output:
                    output = self.send_command_and_log(channel, "\n", delay=3)
                if "delete flash:" in output.lower() or "[confirm]" in output:
                    output = self.send_command_and_log(channel, "\n", delay=5)
                self.signals.update_log.emit(f"[{self.remote_ip}] Suppression de la configuration de démarrage...")
                output = self.send_command_and_log(channel, "erase startup-config\n", delay=2)
                if "[confirm]" in output:
                    output = self.send_command_and_log(channel, "\n", delay=5)
                elif "confirm" in output.lower():
                    output = self.send_command_and_log(channel, "\n", delay=5)
                self.signals.update_log.emit(f"[{self.remote_ip}] Lancement du redémarrage...")
                output = self.send_command_and_log(channel, "reload\n", delay=2)
                if "save" in output.lower() or "system configuration has been modified" in output.lower():
                    output = self.send_command_and_log(channel, "n\n", delay=3)
                if "proceed with reload" in output.lower() or "[confirm]" in output:
                    self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation du redémarrage...")
                    output = self.send_command_and_log(channel, "\n", delay=1, expect_response=False)
                    self.signals.update_log.emit(f"[{self.remote_ip}] Redémarrage en cours...")
            
            elif self.device_type.lower() == "stormshield":
                def send_command_and_wait_completion(channel, command, prompt_patterns, timeout=120, task_description=""):
                    self.signals.update_log.emit(f"[{self.remote_ip}] Envoi de la commande: {command.strip()}")
                    channel.send(command)
                    start_time = time.time()
                    output = ""
                    command_completed = False
                    last_progress_time = start_time
                    progress_update_interval = 2
                    
                    while not command_completed and (time.time() - start_time) < timeout:
                        time.sleep(0.5)
                        if channel.recv_ready():
                            chunk = channel.recv(9999).decode("utf-8", errors="ignore")
                            output += chunk
                            if len(chunk) > 10:
                                self.signals.update_log.emit(f"[{self.remote_ip}] Réception: {chunk}")
                            for pattern in prompt_patterns:
                                if pattern in output.lower():
                                    command_completed = True
                                    break
                        current_time = time.time()
                        if current_time - last_progress_time >= progress_update_interval:
                            elapsed_time = current_time - start_time
                            progress_percent = min(int((elapsed_time / timeout) * 100), 99)
                            progress_message = f"{task_description} en cours..."
                            self.signals.progress_update.emit(self.remote_ip, progress_message, progress_percent)
                            last_progress_time = current_time
                    
                    if command_completed:
                        self.signals.progress_update.emit(self.remote_ip, f"{task_description} terminé", 100)
                    else:
                        self.signals.update_log.emit(f"[{self.remote_ip}] Délai d'attente dépassé pour la commande: {command.strip()}")
                    
                    return output
                
                prompt_patterns = ["#", ">", "confirm", "[y/n]", "[y/N]", "done", "completed", "finished"]
                
                self.signals.update_log.emit(f"[{self.remote_ip}] Lancement du nettoyage du firewall...")
                self.signals.progress_update.emit(self.remote_ip, "Nettoyage du firewall", 0)
                output = send_command_and_wait_completion(channel, "cleanfw -c -s -l\n", prompt_patterns, 
                                                          timeout=180, task_description="Nettoyage du firewall")
                
                if "confirm" in output.lower() or "[y/n]" in output.lower() or "[y/N]" in output:
                    self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation de nettoyage demandée...")
                    output = send_command_and_wait_completion(channel, "y\n", prompt_patterns, 
                                                              timeout=180, task_description="Confirmation de nettoyage")
                
                self.signals.update_log.emit(f"[{self.remote_ip}] Restauration de la configuration par défaut...")
                self.signals.progress_update.emit(self.remote_ip, "Restauration de la configuration", 0)
                output = send_command_and_wait_completion(channel, "defaultconfig -L -r -f -p -c\n", prompt_patterns, 
                                                          timeout=300, task_description="Restauration de la configuration")
                
                if "confirm" in output.lower() or "[y/n]" in output.lower() or "[y/N]" in output:
                    self.signals.update_log.emit(f"[{self.remote_ip}] Confirmation de configuration par défaut demandée...")
                    output = send_command_and_wait_completion(channel, "y\n", prompt_patterns, 
                                                              timeout=300, task_description="Confirmation de restauration")
                
                self.signals.update_log.emit(f"[{self.remote_ip}] Finalisation de la restauration...")
                self.signals.progress_update.emit(self.remote_ip, "Finalisation de la restauration", 95)
                time.sleep(10)
                
                self.signals.update_log.emit(f"[{self.remote_ip}] Restauration terminée avec succès!")
                self.signals.progress_update.emit(self.remote_ip, "Restauration terminée", 100)
                
                time.sleep(2)
                try:
                    channel.close()
                    ssh.close()
                    self.signals.update_log.emit(f"[{self.remote_ip}] Connexion fermée")
                except:
                    self.signals.update_log.emit(f"[{self.remote_ip}] La connexion a été interrompue")
                
                self.signals.finished.emit(f"Réinitialisation réussie pour {self.remote_ip}")
            
        except Exception as e:
            error_msg = f"[{self.remote_ip}] Erreur : {str(e)}"
            self.signals.update_log.emit(error_msg)
            self.signals.finished.emit(f"Erreur pour {self.remote_ip} : {e}")

# ----- BACKUP WORKER -----
class BackupWorkerSignals(QObject):
    finished = pyqtSignal(str)
    update_log = pyqtSignal(str)

class BackupWorker(QRunnable):
    def __init__(self, remote_ip, username, password, local_folder):
        super().__init__()
        self.remote_ip = remote_ip
        self.username = username
        self.password = password
        self.local_folder = local_folder
        self.signals = BackupWorkerSignals()

    def send_command_and_log(self, channel, command, delay=1, expect_response=True):
        log_message = f"[{self.remote_ip}] Envoi de la commande: {command.strip()}"
        self.signals.update_log.emit(log_message)
        channel.send(command)
        time.sleep(delay)
        output = ""
        if expect_response and channel.recv_ready():
            output = channel.recv(9999).decode("utf-8", errors="ignore")
            log_message = f"[{self.remote_ip}] Réponse reçue:\n{output}"
            self.signals.update_log.emit(log_message)
        return output

    def run(self):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.signals.update_log.emit(f"[{self.remote_ip}] Tentative de connexion...")
            ssh.connect(self.remote_ip, username=self.username, password=self.password, timeout=10)
            self.signals.update_log.emit(f"[{self.remote_ip}] Connecté")
            
            channel = ssh.invoke_shell()
            time.sleep(1)
            if channel.recv_ready():
                channel.recv(9999)
            
            output = self.send_command_and_log(channel, "show running-config | include hostname\n", delay=2)
            hostname = "unknown"
            for line in output.splitlines():
                if "hostname" in line.lower():
                    parts = line.split()
                    for i in range(len(parts)):
                        if parts[i].lower() == "hostname" and i+1 < len(parts):
                            hostname = parts[i+1].strip()
                            break
            self.signals.update_log.emit(f"[{self.remote_ip}] Hostname détecté: {hostname}")
            
            date_str = datetime.now().strftime("%d_%m_%Y")
            backup_filename = f"{hostname}_{date_str}.txt"
            date_folder = datetime.now().strftime('%d-%m-%Y')
            backup_path = os.path.join(self.local_folder, date_folder)
            os.makedirs(backup_path, exist_ok=True)
            local_file_path = os.path.join(backup_path, backup_filename)
            
            temp_file = os.path.join(os.path.dirname(local_file_path), "temp_config.txt")
            self.send_command_and_log(channel, "terminal length 0\n", delay=1)
            output = self.send_command_and_log(channel, "show running-config\n", delay=5)
            self.signals.update_log.emit(f"[{self.remote_ip}] Sauvegarde de la configuration en cours...")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(output)
            os.rename(temp_file, local_file_path)
            self.signals.update_log.emit(f"[{self.remote_ip}] Configuration sauvegardée dans: {local_file_path}")
            
            channel.close()
            ssh.close()
            self.signals.update_log.emit(f"[{self.remote_ip}] Connexion fermée")
            self.signals.finished.emit(f"Backup réussi pour {self.remote_ip} :\n{local_file_path}")
        except Exception as e:
            error_msg = f"[{self.remote_ip}] Erreur : {str(e)}"
            self.signals.update_log.emit(error_msg)
            self.signals.finished.emit(f"Erreur pour {self.remote_ip} : {e}")

# ----- HEALTH CHECK WORKER -----
class HealthCheckWorkerSignals(QObject):
    finished = pyqtSignal(str, str, bool)  # ip, message, success
    progress = pyqtSignal(str)

class HealthCheckWorker(QRunnable):
    def __init__(self, remote_ip, username, password):
        super().__init__()
        self.remote_ip = remote_ip
        self.username = username
        self.password = password
        self.signals = HealthCheckWorkerSignals()
    def run(self):
        try:
            self.signals.progress.emit(f"Connexion à {self.remote_ip}...")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.remote_ip, username=self.username, password=self.password, timeout=10)
            ssh.close()
            success = True
            message = "Équipement fonctionnel"
        except Exception as e:
            success = False
            message = f"Erreur : {e}"
        self.signals.finished.emit(self.remote_ip, message, success)

#########################
# INTERFACE PRINCIPALE
#########################

class GenerateurConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(10)  # Limiter pour éviter la surcharge
        self.reset_results = []
        self.backup_results = []
        self._worker_cache = {}
        self._active_workers = 0
        self._max_workers = 5
        
        # Création de l'inventaire minimal et du gestionnaire de planification
        self.device_inventory = DeviceInventory()
        self.schedule_manager = ScheduleManager(self.device_inventory)
        self.schedule_manager.start_scheduler()
        self.initUI()

    def initUI(self):
        self.load_stylesheet("style.qss")
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        # Onglets existants
        self.tabs.addTab(self.initResetTab(), "Réinitialisation")
        self.tabs.addTab(self.initBackupTab(), "Sauvegarde")
        self.tabs.addTab(self.initPlannificationsTab(), "Planifications")
        self.tabs.addTab(self.initLogTab(), "Journaux")
        main_layout.addWidget(self.tabs)

    def load_stylesheet(self, filename):
        try:
            with open(filename, "r") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Fichier de style {filename} non trouvé.")

    # ----- Onglet Réinitialisation -----
    def initResetTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.reset_ip_edit = QLineEdit()
        self.reset_ip_edit.setPlaceholderText("ex: 192.168.1.1, 10.1.1.1")
        form.addRow("Adresses IP (virgule séparée) :", self.reset_ip_edit)
        self.reset_username_edit = QLineEdit()
        form.addRow("Nom d'utilisateur :", self.reset_username_edit)
        self.reset_password_edit = QLineEdit()
        self.reset_password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Mot de passe :", self.reset_password_edit)
        self.device_type_combo = QComboBox()
        self.device_type_combo.addItems(["Routeur", "Switch", "Stormshield"])
        self.device_type_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        form.addRow("Type d'équipement :", self.device_type_combo)
        self.reset_confirm_checkbox = QCheckBox("Confirmer la réinitialisation (action irréversible)")
        form.addRow("Confirmation :", self.reset_confirm_checkbox)
        layout.addLayout(form)
        self.reset_execute_btn = QPushButton("Exécuter la réinitialisation via SSH")
        self.reset_execute_btn.setObjectName("resetExecuteButton")
        # Uniformiser la taille du bouton avec celui de sauvegarde
        self.reset_execute_btn.setMinimumHeight(40)
        self.reset_execute_btn.setMinimumWidth(220)
        self.reset_execute_btn.clicked.connect(self.reset_config_ssh)
        layout.addWidget(self.reset_execute_btn)
        self.reset_progress_bar = QProgressBar()
        self.reset_progress_bar.setValue(0)
        layout.addWidget(self.reset_progress_bar)
        return tab

    def reset_config_ssh(self):
        ips_text = self.reset_ip_edit.text().strip()
        username = self.reset_username_edit.text().strip()
        password = self.reset_password_edit.text().strip()
        device_type = self.device_type_combo.currentText()
        confirm = self.reset_confirm_checkbox.isChecked()
        
        if not ips_text or not username or not password:
            QMessageBox.warning(self, "Erreur", "Tous les champs doivent être renseignés.")
            return
        if not confirm:
            QMessageBox.warning(self, "Confirmation", "Veuillez confirmer la réinitialisation.")
            return
        
        ips = [ip.strip() for ip in ips_text.split(",") if ip.strip()]
        if not ips:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir au moins une adresse IP valide.")
            return
        
        # Limitation du nombre de workers simultanés
        if self._active_workers >= self._max_workers:
            QMessageBox.warning(self, "Limite atteinte", 
                              f"Maximum {self._max_workers} opérations simultanées autorisées.")
            return
        
        if device_type.lower() == "stormshield":
            if hasattr(self, 'stormshield_progress_frame') and self.stormshield_progress_frame:
                self.stormshield_progress_frame.deleteLater()
            
            self.stormshield_progress_frame = QFrame()
            self.stormshield_progress_frame.setFrameShape(QFrame.Box)
            self.stormshield_progress_frame.setFrameShadow(QFrame.Sunken)
            self.stormshield_progress_layout = QVBoxLayout(self.stormshield_progress_frame)
            
            title_label = QLabel("Progression des restaurations Stormshield")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            self.stormshield_progress_layout.addWidget(title_label)
            
            self.stormshield_progress_bars = {}
            
            for ip in ips:
                ip_frame = QFrame()
                ip_frame.setFrameShape(QFrame.StyledPanel)
                ip_layout = QVBoxLayout(ip_frame)
                
                ip_label = QLabel(f"Équipement: {ip}")
                ip_label.setStyleSheet("font-weight: bold;")
                ip_layout.addWidget(ip_label)
                
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                progress_bar.setValue(0)
                progress_bar.setTextVisible(True)
                progress_bar.setFormat("%p% complété")
                ip_layout.addWidget(progress_bar)
                
                status_label = QLabel("En attente de démarrage...")
                status_label.setAlignment(Qt.AlignCenter)
                ip_layout.addWidget(status_label)
                
                self.stormshield_progress_layout.addWidget(ip_frame)
                self.stormshield_progress_bars[ip] = {
                    'bar': progress_bar,
                    'label': status_label
                }
            
            reset_tab_layout = self.tabs.widget(0).layout()
            reset_tab_layout.addWidget(self.stormshield_progress_frame)
        
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self.log_text.clear()
        self.log_text.append("=== DÉBUT DE LA RÉINITIALISATION ===")
        
        total = len(ips)
        self.reset_progress_bar.setMaximum(total)
        self.reset_progress_bar.setValue(0)
        self.reset_results = []
        
        # Démarrer les workers avec limitation
        batch_size = min(len(ips), self._max_workers)
        for ip in ips[:batch_size]:
            if self._active_workers < self._max_workers:
                worker = ResetWorker(ip, username, password, device_type)
                worker.signals.finished.connect(self.on_reset_finished)
                worker.signals.finished.connect(lambda: self._decrement_worker_count())
                worker.signals.update_log.connect(self.update_log)
                if device_type.lower() == "stormshield":
                    worker.signals.progress_update.connect(self.update_stormshield_progress)
                self.threadpool.start(worker)
                self._active_workers += 1

    def _decrement_worker_count(self):
        """Décremente le compteur de workers actifs"""
        self._active_workers = max(0, self._active_workers - 1)
        
        # Lancer le prochain worker en file d'attente s'il en reste
        if hasattr(self, '_pending_workers') and self._pending_workers:
            next_worker = self._pending_workers.pop(0)
            self.threadpool.start(next_worker)
            self._active_workers += 1

    def update_stormshield_progress(self, ip, message, progress_value):
        if hasattr(self, 'stormshield_progress_bars') and ip in self.stormshield_progress_bars:
            progress_bar = self.stormshield_progress_bars[ip]['bar']
            status_label = self.stormshield_progress_bars[ip]['label']
            
            progress_bar.setValue(progress_value)
            status_label.setText(message)
            
            if progress_value == 100:
                progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #27ae60; }")
                status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            elif progress_value > 70:
                progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2980b9; }")
            elif progress_value > 30:
                progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #f39c12; }")
            else:
                progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #e67e22; }")
            
            if progress_value % 25 == 0 or progress_value == 100:
                self.log_text.append(f"[{ip}] {message} - {progress_value}%")

    def on_reset_finished(self, message):
        self.reset_results.append(message)
        current_count = len(self.reset_results)
        self.reset_progress_bar.setValue(current_count)
        
        if current_count == self.reset_progress_bar.maximum():
            summary = "\n".join(self.reset_results)
            self.log_text.append("=== FIN DE LA RÉINITIALISATION ===")
            QMessageBox.information(self, "Réinitialisations terminées", summary)

    # ----- Onglet Sauvegarde -----
    def initBackupTab(self):
        tab = QWidget()
        main_layout = QVBoxLayout(tab)
        form = QFormLayout()
        self.backup_ip_edit = QLineEdit()
        self.backup_ip_edit.setPlaceholderText("ex: 9.1.11.194, 10.1.1.1")
        form.addRow("Adresses IP (virgule séparée) :", self.backup_ip_edit)
        self.backup_username_edit = QLineEdit()
        form.addRow("Nom d'utilisateur :", self.backup_username_edit)
        self.backup_password_edit = QLineEdit()
        self.backup_password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Mot de passe :", self.backup_password_edit)
        backup_folder_layout = QHBoxLayout()
        self.backup_folder_edit = QLineEdit()
        self.backup_folder_edit.setPlaceholderText("Chemin du dossier de sauvegarde local")
        backup_folder_layout.addWidget(self.backup_folder_edit)
        self.browse_btn = QPushButton("Parcourir...")
        self.browse_btn.setObjectName("browseButton")
        self.browse_btn.clicked.connect(self.browse_backup_folder)
        backup_folder_layout.addWidget(self.browse_btn)
        form.addRow("Répertoire local :", backup_folder_layout)
        main_layout.addLayout(form)
        scp_layout = QHBoxLayout()
        scp_label = QLabel("Attention : SCP doit être activé")
        scp_label.setStyleSheet("font-weight: bold;")
        scp_layout.addStretch()
        scp_layout.addWidget(scp_label)
        scp_layout.addStretch()
        main_layout.addLayout(scp_layout)
        scp_button_layout = QHBoxLayout()
        scp_button_layout.addStretch()
        self.enable_scp_btn = QPushButton("Générer configuration SCP")
        self.enable_scp_btn.setObjectName("generateSCPButton")
        self.enable_scp_btn.clicked.connect(self.generate_scp_activation_config)
        scp_button_layout.addWidget(self.enable_scp_btn)
        scp_button_layout.addStretch()
        main_layout.addLayout(scp_button_layout)
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        exec_layout = QHBoxLayout()
        exec_layout.addStretch()
        self.execute_backup_btn = QPushButton("Exécuter la sauvegarde via SCP")
        self.execute_backup_btn.setObjectName("executeBackupButton")
        # Stylisation bouton sauvegarde
        self.execute_backup_btn.setStyleSheet("""
            QPushButton#executeBackupButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                border-radius: 5px;
                padding: 8px 16px;
            }
            QPushButton#executeBackupButton:hover {
                background-color: #1c5d99;
            }
        """)
        self.execute_backup_btn.clicked.connect(self.backup_config_scp)
        exec_layout.addWidget(self.execute_backup_btn)
        exec_layout.addStretch()
        main_layout.addLayout(exec_layout)
        self.backup_progress_bar = QProgressBar()
        self.backup_progress_bar.setValue(0)
        main_layout.addWidget(self.backup_progress_bar)
        return tab

    def browse_backup_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionnez le répertoire de sauvegarde")
        if folder:
            self.backup_folder_edit.setText(folder)

    def backup_config_scp(self):
        ips_text = self.backup_ip_edit.text().strip()
        username = self.backup_username_edit.text().strip()
        password = self.backup_password_edit.text().strip()
        local_folder = self.backup_folder_edit.text().strip()
        if not ips_text or not username or not password or not local_folder:
            QMessageBox.warning(self, "Erreur", "Tous les champs doivent être renseignés.")
            return
        ips = [ip.strip() for ip in ips_text.split(",") if ip.strip()]
        if not ips:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir au moins une adresse IP valide.")
            return
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        self.log_text.clear()
        self.log_text.append("=== DÉBUT DE LA SAUVEGARDE ===")
        total = len(ips)
        self.backup_progress_bar.setMaximum(total)
        self.backup_progress_bar.setValue(0)
        self.backup_results = []
        for ip in ips:
            worker = BackupWorker(ip, username, password, local_folder)
            worker.signals.finished.connect(self.on_backup_finished)
            worker.signals.update_log.connect(self.update_log)
            self.threadpool.start(worker)

    def on_backup_finished(self, message):
        self.backup_results.append(message)
        current_count = len(self.backup_results)
        self.backup_progress_bar.setValue(current_count)
        if current_count == self.backup_progress_bar.maximum():
            summary = "\n".join(self.backup_results)
            self.log_text.append("=== FIN DE LA SAUVEGARDE ===")
            QMessageBox.information(self, "Sauvegardes terminées", summary)

    def generate_scp_activation_config(self):
        config_scp = """
conf t
ip scp server enable
aaa new-model
aaa authentication login default local
aaa authorization exec default local
aaa authentication attempts login 3
"""
        file_name, _ = QFileDialog.getSaveFileName(self, "Sauvegarder la configuration SCP", "", "Fichiers texte (*.txt);;Tous les fichiers (*)")
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(config_scp)
                QMessageBox.information(self, "Succès", f"Configuration SCP sauvegardée dans {file_name}")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la sauvegarde : {e}")
        QMessageBox.information(self, "Configuration SCP", config_scp)

    # ----- Onglet Planifications -----
    def initPlannificationsTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        header_label = QLabel("Tâches planifiées")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(7)
        self.tasks_table.setHorizontalHeaderLabels(["ID", "Type", "Équipements", "Fréquence", "Prochaine exécution", "Dernière exécution", "État"])
        self.tasks_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.tasks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self.tasks_table)
        
        # Correction : Ajout des boutons sous le tableau (dans layout, pas dans btn_layout)
        btn_layout = QHBoxLayout()
        self.add_task_btn = QPushButton("Ajouter tâche")
        self.add_task_btn.clicked.connect(self.add_scheduled_task)
        btn_layout.addWidget(self.add_task_btn)
        self.edit_task_btn = QPushButton("Modifier tâche")
        self.edit_task_btn.clicked.connect(self.edit_scheduled_task)
        btn_layout.addWidget(self.edit_task_btn)
        self.delete_task_btn = QPushButton("Supprimer tâche")
        self.delete_task_btn.clicked.connect(self.delete_scheduled_task)
        btn_layout.addWidget(self.delete_task_btn)
        self.toggle_task_btn = QPushButton("Activer/Désactiver")
        self.toggle_task_btn.clicked.connect(self.toggle_scheduled_task)
        btn_layout.addWidget(self.toggle_task_btn)
        self.run_task_btn = QPushButton("Exécuter maintenant")
        self.run_task_btn.clicked.connect(self.run_scheduled_task_now)
        btn_layout.addWidget(self.run_task_btn)
        layout.addLayout(btn_layout)
        
        self.refresh_scheduled_tasks()
        return tab

    # Méthode pour parcourir et sélectionner un dossier pour une tâche planifiée
    def browse_folder_for_task(self, folder_edit):
        folder = QFileDialog.getExistingDirectory(self, "Sélectionnez le répertoire de sauvegarde")
        if folder:
            folder_edit.setText(folder)

    def refresh_scheduled_tasks(self):
        self.tasks_table.setRowCount(0)
        for task in self.schedule_manager.get_all_tasks():
            row = self.tasks_table.rowCount()
            self.tasks_table.insertRow(row)
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.task_id))
            task_type = "Sauvegarde" if task.task_type == "backup" else "Vérification"
            self.tasks_table.setItem(row, 1, QTableWidgetItem(task_type))
            if len(task.device_ips) > 3:
                devices_text = f"{', '.join(task.device_ips[:3])}... ({len(task.device_ips)})"
            else:
                devices_text = ", ".join(task.device_ips)
            self.tasks_table.setItem(row, 2, QTableWidgetItem(devices_text))
            if task.schedule_type == "minutes":
                freq_text = f"Toutes les {task.interval} minute(s)"
            elif task.schedule_type == "hourly":
                freq_text = f"Toutes les {task.interval} heure(s)"
            elif task.schedule_type == "daily":
                freq_text = f"Tous les {task.interval} jour(s)"
            elif task.schedule_type == "weekly":
                freq_text = f"Toutes les {task.interval} semaine(s)"
            elif task.schedule_type == "monthly":
                freq_text = f"Tous les {task.interval} mois"
            else:
                freq_text = f"{task.schedule_type} {task.interval}"
            self.tasks_table.setItem(row, 3, QTableWidgetItem(freq_text))
            next_run = task.next_run if task.next_run else "Non planifié"
            self.tasks_table.setItem(row, 4, QTableWidgetItem(next_run))
            last_run = task.last_run if task.last_run else "Jamais"
            self.tasks_table.setItem(row, 5, QTableWidgetItem(last_run))
            state = "Activé" if task.enabled else "Désactivé"
            state_item = QTableWidgetItem(state)
            state_item.setForeground(QColor("#27ae60") if task.enabled else QColor("#e74c3c"))
            self.tasks_table.setItem(row, 6, state_item)

    # ----------------------- MODIFICATIONS -----------------------
    # Ajout d'une tâche planifiée toujours de type "sauvegarde"
    def add_scheduled_task(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Ajouter une tâche planifiée")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        task_id_edit = QLineEdit()
        task_id_edit.setText(f"Task_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        form.addRow("ID de la tâche:", task_id_edit)
        
        # Suppression du sélecteur de type de tâche (toujours "sauvegarde")
        
        devices_edit = QLineEdit()
        devices_edit.setPlaceholderText("ex: 192.168.1.1, 10.0.0.1")
        form.addRow("Équipements:", devices_edit)
        
        username_edit = QLineEdit()
        form.addRow("Utilisateur:", username_edit)
        
        password_edit = QLineEdit()
        password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Mot de passe:", password_edit)
        
        folder_layout = QHBoxLayout()
        folder_edit = QLineEdit()
        folder_layout.addWidget(folder_edit)
        browse_folder_btn = QPushButton("Parcourir...")
        browse_folder_btn.clicked.connect(lambda: self.browse_folder_for_task(folder_edit))
        folder_layout.addWidget(browse_folder_btn)
        form.addRow("Dossier sauvegarde:", folder_layout)
        
        schedule_type_combo = QComboBox()
        schedule_type_combo.addItem("Toutes les X minutes", "minutes")
        schedule_type_combo.addItem("Toutes les X heures", "hourly")
        schedule_type_combo.addItem("Tous les X jours", "daily")
        schedule_type_combo.addItem("Toutes les X semaines", "weekly")
        schedule_type_combo.addItem("Tous les X mois", "monthly")
        form.addRow("Fréquence:", schedule_type_combo)
        
        interval_spinbox = QLineEdit()
        interval_spinbox.setText("1")
        form.addRow("Intervalle:", interval_spinbox)
        
        first_run_edit = QLineEdit()
        first_run_edit.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        form.addRow("Première exécution:", first_run_edit)
        
        enable_checkbox = QCheckBox("Activer la tâche immédiatement")
        enable_checkbox.setChecked(True)
        form.addRow("", enable_checkbox)
        
        layout.addLayout(form)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            task_id = task_id_edit.text().strip()
            task_type = "backup"  # Toujours de type "sauvegarde"
            device_ips = [ip.strip() for ip in devices_edit.text().split(",") if ip.strip()]
            username = username_edit.text().strip()
            password = password_edit.text().strip()
            local_folder = folder_edit.text().strip()
            schedule_type = schedule_type_combo.currentData()
            
            try:
                interval = int(interval_spinbox.text().strip())
            except:
                interval = 1
                
            enabled = enable_checkbox.isChecked()
            next_run = first_run_edit.text().strip()
            
            if not task_id or not device_ips:
                ModernMessageBox.warning(self, "Erreur", "ID et au moins une IP sont requis.")
                return
                
            if not local_folder:
                ModernMessageBox.warning(self, "Erreur", "Un dossier est requis pour la sauvegarde.")
                return
                
            new_task = ScheduledTask(task_id, task_type, device_ips, schedule_type, interval,
                                 local_folder, username, password, enabled, None, next_run)
            self.schedule_manager.add_task(new_task)
            self.refresh_scheduled_tasks()
            ModernMessageBox.information(self, "Tâche planifiée", f"Tâche {task_id} ajoutée.")

    # Modification de la fonction d'édition (toujours de type sauvegarde)
    def edit_scheduled_task(self):
        selected = self.tasks_table.selectedIndexes()
        if not selected:
            ModernMessageBox.warning(self, "Erreur", "Sélectionnez une tâche à modifier.")
            return
        row = selected[0].row()
        task_id = self.tasks_table.item(row, 0).text()
        task = self.schedule_manager.get_task(task_id)
        if not task:
            ModernMessageBox.warning(self, "Erreur", f"Tâche {task_id} introuvable.")
            return
            
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Modifier la tâche: {task_id}")
        dialog.setMinimumWidth(450)
        layout = QVBoxLayout(dialog)
        form = QFormLayout()
        
        task_id_edit = QLineEdit()
        task_id_edit.setText(task.task_id)
        task_id_edit.setReadOnly(True)
        form.addRow("ID de la tâche:", task_id_edit)
        
        # Suppression du sélecteur de type de tâche (toujours "sauvegarde")
        
        devices_edit = QLineEdit()
        devices_edit.setText(", ".join(task.device_ips))
        form.addRow("Équipements:", devices_edit)
        
        username_edit = QLineEdit()
        username_edit.setText(task.username)
        form.addRow("Utilisateur:", username_edit)
        
        password_edit = QLineEdit()
        password_edit.setText(task.password)
        password_edit.setEchoMode(QLineEdit.Password)
        form.addRow("Mot de passe:", password_edit)
        
        folder_layout = QHBoxLayout()
        folder_edit = QLineEdit()
        folder_edit.setText(task.local_folder)
        folder_layout.addWidget(folder_edit)
        browse_folder_btn = QPushButton("Parcourir...")
        browse_folder_btn.clicked.connect(lambda: self.browse_folder_for_task(folder_edit))
        folder_layout.addWidget(browse_folder_btn)
        form.addRow("Dossier sauvegarde:", folder_layout)
        
        schedule_type_combo = QComboBox()
        schedule_type_combo.addItem("Toutes les X minutes", "minutes")
        schedule_type_combo.addItem("Toutes les X heures", "hourly")
        schedule_type_combo.addItem("Tous les X jours", "daily")
        schedule_type_combo.addItem("Toutes les X semaines", "weekly")
        schedule_type_combo.addItem("Tous les X mois", "monthly")
        stype_index = {"minutes":0, "hourly":1, "daily":2, "weekly":3, "monthly":4}.get(task.schedule_type, 0)
        schedule_type_combo.setCurrentIndex(stype_index)
        form.addRow("Fréquence:", schedule_type_combo)
        
        interval_edit = QLineEdit()
        interval_edit.setText(str(task.interval))
        form.addRow("Intervalle:", interval_edit)
        
        next_run_edit = QLineEdit()
        next_run_edit.setText(task.next_run if task.next_run else "")
        form.addRow("Prochaine exécution:", next_run_edit)
        
        enable_checkbox = QCheckBox("Activer la tâche")
        enable_checkbox.setChecked(task.enabled)
        form.addRow("", enable_checkbox)
        
        layout.addLayout(form)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            task.device_ips = [ip.strip() for ip in devices_edit.text().split(",") if ip.strip()]
            task.username = username_edit.text().strip()
            task.password = password_edit.text().strip()
            task.local_folder = folder_edit.text().strip()
            task.schedule_type = schedule_type_combo.currentData()
            
            try:
                task.interval = int(interval_edit.text().strip())
            except:
                task.interval = 1
                
            task.enabled = enable_checkbox.isChecked()
            task.next_run = next_run_edit.text().strip()
            
            if not task.device_ips:
                ModernMessageBox.warning(self, "Erreur", "Au moins une IP est requise.")
                return
                
            if not task.local_folder:
                ModernMessageBox.warning(self, "Erreur", "Un dossier est requis pour la sauvegarde.")
                return
                
            self.schedule_manager.add_task(task)
            self.refresh_scheduled_tasks()
            ModernMessageBox.information(self, "Succès", f"Tâche {task.task_id} modifiée.")

    # Modification de l'exécution immédiate (toujours utiliser BackupWorker)
    def run_scheduled_task_now(self):
        selected = self.tasks_table.selectedIndexes()
        if not selected:
            ModernMessageBox.warning(self, "Erreur", "Sélectionnez une tâche à exécuter.")
            return
        row = selected[0].row()
        task_id = self.tasks_table.item(row, 0).text()
        task = self.schedule_manager.get_task(task_id)
        if not task:
            ModernMessageBox.warning(self, "Erreur", f"Tâche {task_id} introuvable.")
            return
            
        confirmation = ModernMessageBox.question(self, "Confirmation", f"Exécuter la tâche {task_id} maintenant ?")
        if confirmation == QMessageBox.Yes:
            # Toujours utiliser BackupWorker, car toutes les tâches sont de type sauvegarde
            worker = BackupWorker(task.device_ips[0], task.username, task.password, task.local_folder)
            worker.signals.finished.connect(self.on_backup_finished)
            worker.signals.update_log.connect(self.update_log)
            self.threadpool.start(worker)
            
            self.schedule_manager.update_task_last_run(task_id)
            self.refresh_scheduled_tasks()
    # ----------------------- FIN MODIFICATIONS -----------------------

    def delete_scheduled_task(self):
        selected = self.tasks_table.selectedIndexes()
        if not selected:
            ModernMessageBox.warning(self, "Erreur", "Sélectionnez une tâche à supprimer.")
            return
        row = selected[0].row()
        task_id = self.tasks_table.item(row, 0).text()
        confirmation = ModernMessageBox.question(self, "Confirmation", f"Supprimer la tâche {task_id} ?")
        if confirmation == QMessageBox.Yes:
            self.schedule_manager.remove_task(task_id)
            self.refresh_scheduled_tasks()
            ModernMessageBox.information(self, "Succès", f"Tâche {task_id} supprimée.")

    def toggle_scheduled_task(self):
        selected = self.tasks_table.selectedIndexes()
        if not selected:
            ModernMessageBox.warning(self, "Erreur", "Sélectionnez une tâche à activer/désactiver.")
            return
        row = selected[0].row()
        task_id = self.tasks_table.item(row, 0).text()
        task = self.schedule_manager.get_task(task_id)
        if task:
            new_state = not task.enabled
            self.schedule_manager.enable_task(task_id, new_state)
            self.refresh_scheduled_tasks()

    # ----- Onglet Journaux -----
    def initLogTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        layout.addWidget(self.log_text)
        btn_layout = QHBoxLayout()
        self.clear_log_btn = QPushButton("Effacer les journaux")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        btn_layout.addWidget(self.clear_log_btn)
        self.save_log_btn = QPushButton("Enregistrer les journaux")
        self.save_log_btn.clicked.connect(self.save_logs)
        btn_layout.addWidget(self.save_log_btn)
        layout.addLayout(btn_layout)
        return tab

    def update_log(self, message):
        """Version optimisée du logging avec limitation de taille"""
        # Limiter la taille du log pour éviter les ralentissements
        if self.log_text.document().blockCount() > 1000:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.movePosition(cursor.Down, cursor.KeepAnchor, 200)
            cursor.removeSelectedText()
        
        self.log_text.append(message)
        
        # Scroll optimisé - seulement si nécessaire
        scrollbar = self.log_text.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum() - 10:
            scrollbar.setValue(scrollbar.maximum())

    def save_logs(self):
        if not self.log_text.toPlainText():
            QMessageBox.information(self, "Information", "Aucun journal à enregistrer.")
            return
        file_name, _ = QFileDialog.getSaveFileName(self, "Enregistrer les journaux", "", "Fichiers texte (*.txt);;Tous les fichiers (*)")
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
                QMessageBox.information(self, "Succès", f"Journaux enregistrés dans {file_name}")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de l'enregistrement : {e}")

