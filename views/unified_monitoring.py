import time
import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QProgressBar, QComboBox, QCheckBox,
    QGroupBox, QTabWidget, QHeaderView, QSplitter, QFrame, QTextEdit,
    QMenu, QAction, QStatusBar, QMessageBox, QDialog
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QIcon, QColor

class DeviceStatusThread(QThread):
    """Thread pour surveiller l'état des équipements"""
    update_status = pyqtSignal(str, bool, float)  # ip, is_reachable, latency
    finished = pyqtSignal()
    
    def __init__(self, devices, interval=5):
        super().__init__()
        self.devices = devices
        self.interval = interval
        self.running = True
    
    def run(self):
        while self.running:
            for device in self.devices:
                # Simulation de ping/vérification d'état (à remplacer par du code réel)
                time.sleep(0.1)  # Pour ne pas surcharger
                import random
                is_reachable = random.random() > 0.2  # 80% de chance d'être joignable
                latency = random.uniform(10, 100) if is_reachable else 0
                self.update_status.emit(device['ip'], is_reachable, latency)
            
            # Attendre l'intervalle spécifié
            for _ in range(self.interval * 10):  # Pour permettre une interruption plus rapide
                if not self.running:
                    break
                time.sleep(0.1)
                
        self.finished.emit()
    
    def stop(self):
        self.running = False

class UnifiedMonitoringWidget(QWidget):
    """Interface unifiée pour le monitoring des équipements"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices = []  # Liste des équipements à surveiller
        self.monitoring_thread = None
        self.initUI()
        self.load_devices()  # Charger les équipements depuis une source persistante
    
    def initUI(self):
        main_layout = QVBoxLayout(self)
        
        # Barre d'outils
        toolbar_layout = QHBoxLayout()
        
        self.add_device_btn = QPushButton("Ajouter un équipement")
        self.add_device_btn.clicked.connect(self.add_device)
        toolbar_layout.addWidget(self.add_device_btn)
        
        self.remove_device_btn = QPushButton("Supprimer")
        self.remove_device_btn.clicked.connect(self.remove_selected_device)
        toolbar_layout.addWidget(self.remove_device_btn)
        
        self.start_monitoring_btn = QPushButton("Démarrer le monitoring")
        self.start_monitoring_btn.clicked.connect(self.toggle_monitoring)
        toolbar_layout.addWidget(self.start_monitoring_btn)
        
        self.refresh_btn = QPushButton("Actualiser maintenant")
        self.refresh_btn.clicked.connect(self.refresh_all)
        toolbar_layout.addWidget(self.refresh_btn)
        
        toolbar_layout.addStretch(1)
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["5s", "10s", "30s", "1min", "5min"])
        self.interval_combo.setCurrentIndex(0)
        toolbar_layout.addWidget(QLabel("Intervalle:"))
        toolbar_layout.addWidget(self.interval_combo)
        
        main_layout.addLayout(toolbar_layout)
        
        # Tableau des équipements
        self.devices_table = QTableWidget()
        self.devices_table.setColumnCount(6)
        self.devices_table.setHorizontalHeaderLabels([
            "Nom", "IP", "Type", "Statut", "Latence", "Dernière vérification"
        ])
        
        # Ajuster les colonnes
        self.devices_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.devices_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.devices_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.devices_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.devices_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.devices_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        
        main_layout.addWidget(self.devices_table)
        
        # Barre d'état
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)
        
        # Configuration initiale
        self.status_bar.showMessage("Prêt à démarrer le monitoring")
    
    def load_devices(self):
        """Charge la liste des équipements depuis une source persistante"""
        # Dans un vrai cas, charger depuis un fichier ou une base de données
        # Pour l'exemple, quelques équipements prédéfinis
        self.add_device_to_list("Routeur principal", "192.168.1.1", "Routeur")
        self.add_device_to_list("Switch 1", "192.168.1.2", "Switch")
        self.add_device_to_list("Switch 2", "192.168.1.3", "Switch")
    
    def add_device_to_list(self, name, ip, device_type):
        """Ajoute un équipement à la liste"""
        # Ajouter à la liste interne
        self.devices.append({
            'name': name,
            'ip': ip,
            'type': device_type,
            'status': 'Inconnu',
            'latency': 0,
            'last_check': '-'
        })
        
        # Ajouter au tableau
        row = self.devices_table.rowCount()
        self.devices_table.insertRow(row)
        
        # Remplir les colonnes
        self.devices_table.setItem(row, 0, QTableWidgetItem(name))
        self.devices_table.setItem(row, 1, QTableWidgetItem(ip))
        self.devices_table.setItem(row, 2, QTableWidgetItem(device_type))
        
        status_item = QTableWidgetItem("Inconnu")
        status_item.setTextAlignment(Qt.AlignCenter)
        self.devices_table.setItem(row, 3, status_item)
        
        latency_item = QTableWidgetItem("-")
        latency_item.setTextAlignment(Qt.AlignCenter)
        self.devices_table.setItem(row, 4, latency_item)
        
        self.devices_table.setItem(row, 5, QTableWidgetItem("-"))
    
    def add_device(self):
        """Ouvre un dialogue pour ajouter un nouvel équipement"""
        # Pour simplifier, utilisons des valeurs hardcodées
        # Dans un vrai cas, ouvrir un dialogue
        name = "Nouvel équipement"
        ip = "192.168.1.10"
        device_type = "Routeur"
        
        self.add_device_to_list(name, ip, device_type)
        self.status_bar.showMessage("Équipement ajouté")
    
    def remove_selected_device(self):
        """Supprime l'équipement sélectionné"""
        selected_rows = self.devices_table.selectedIndexes()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        ip = self.devices_table.item(row, 1).text()
        
        # Supprimer de la liste interne
        self.devices = [d for d in self.devices if d['ip'] != ip]
        
        # Supprimer du tableau
        self.devices_table.removeRow(row)
        
        self.status_bar.showMessage("Équipement supprimé")
    
    def toggle_monitoring(self):
        """Démarre ou arrête le monitoring"""
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            # Démarrer le monitoring
            interval_text = self.interval_combo.currentText()
            if "s" in interval_text:
                interval = int(interval_text.replace("s", ""))
            elif "min" in interval_text:
                interval = int(interval_text.replace("min", "")) * 60
            else:
                interval = 5  # Par défaut 5 secondes
                
            self.monitoring_thread = DeviceStatusThread(self.devices, interval)
            self.monitoring_thread.update_status.connect(self.update_device_status)
            self.monitoring_thread.finished.connect(self.on_monitoring_stopped)
            self.monitoring_thread.start()
            
            self.start_monitoring_btn.setText("Arrêter le monitoring")
            self.status_bar.showMessage(f"Monitoring en cours (intervalle: {interval_text})")
        else:
            # Arrêter le monitoring
            self.monitoring_thread.stop()
            self.start_monitoring_btn.setText("Démarrer le monitoring")
            self.status_bar.showMessage("Monitoring arrêté")
    
    def on_monitoring_stopped(self):
        """Appelé lorsque le thread de monitoring s'arrête"""
        self.start_monitoring_btn.setText("Démarrer le monitoring")
        self.status_bar.showMessage("Monitoring arrêté")
    
    def update_device_status(self, ip, is_reachable, latency):
        """Met à jour le statut d'un équipement dans la table"""
        # Trouver l'équipement dans la table
        for row in range(self.devices_table.rowCount()):
            if self.devices_table.item(row, 1).text() == ip:
                # Mettre à jour le statut
                status_text = "En ligne" if is_reachable else "Hors ligne"
                status_item = self.devices_table.item(row, 3)
                status_item.setText(status_text)
                status_item.setForeground(QColor("green" if is_reachable else "red"))
                
                # Mettre à jour la latence
                latency_text = f"{latency:.1f} ms" if is_reachable else "-"
                self.devices_table.item(row, 4).setText(latency_text)
                
                # Mettre à jour l'horodatage
                now = datetime.datetime.now().strftime("%H:%M:%S")
                self.devices_table.item(row, 5).setText(now)
                break
                
        # Mettre à jour la liste interne également
        for device in self.devices:
            if device['ip'] == ip:
                device['status'] = "En ligne" if is_reachable else "Hors ligne"
                device['latency'] = latency
                device['last_check'] = datetime.datetime.now().strftime("%H:%M:%S")
                break
    
    def refresh_all(self):
        """Force une actualisation immédiate de tous les équipements"""
        # Si le monitoring est en cours, il actualisera automatiquement
        # Sinon, faire une vérification ponctuelle
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            thread = DeviceStatusThread(self.devices, 0)  # 0 = une seule vérification
            thread.update_status.connect(self.update_device_status)
            thread.start()
            
            self.status_bar.showMessage("Actualisation en cours...")
