import sys
import os
import socket
import threading
import time
import logging
import json
import re
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass
from queue import Queue
from typing import Dict, List, Optional, Tuple, Union, Set

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QLabel, QSpinBox, QTextEdit, QFileDialog, QMessageBox,
    QGroupBox, QTabWidget, QSplitter, QTreeWidget, QTreeWidgetItem, QCheckBox,
    QMenu, QAction, QInputDialog, QColorDialog, QToolBar, QSystemTrayIcon,
    QDateTimeEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QStatusBar,
    QProgressBar, QFrame, QSlider, QDialog, QTextBrowser, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize, QDateTime, QSettings
from PyQt5.QtGui import QColor, QBrush, QFont, QTextCursor, QIcon, QPalette, QPixmap, QFontDatabase

# Tente d'importer netifaces pour la détection des interfaces réseau
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False

# --- Configuration du logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.StreamHandler()
                    ])
logger = logging.getLogger("SyslogServer")

# --- Constantes ---
DEFAULT_PORT = 514
MAX_LOG_ENTRIES = 10000  # Nombre maximum d'entrées à conserver dans la table
APP_VERSION = "3.0"
APP_TITLE = "Serveur SYSLOG Professional Edition"

# --- Création du répertoire des ressources si nécessaire ---
RESOURCES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
if not os.path.exists(RESOURCES_DIR):
    os.makedirs(RESOURCES_DIR)

# --- Classes pour le serveur SYSLOG ---

class SyslogServerSignals(QObject):
    new_message = pyqtSignal(str, str, int, int, str)  # (timestamp, source, facility, severity, message)
    log_message = pyqtSignal(str, str)  # (niveau, message)
    server_started = pyqtSignal(str, int)  # (host, port)
    server_stopped = pyqtSignal()
    stats_updated = pyqtSignal(dict)  # statistiques
    active_hosts_updated = pyqtSignal(set)  # ensemble d'hôtes actifs

class SyslogParser:
    FACILITIES = {
        0: "kern", 1: "user", 2: "mail", 3: "daemon", 4: "auth", 5: "syslog",
        6: "lpr", 7: "news", 8: "uucp", 9: "cron", 10: "authpriv", 11: "ftp",
        12: "ntp", 13: "security", 14: "console", 15: "solaris-cron", 16: "local0",
        17: "local1", 18: "local2", 19: "local3", 20: "local4", 21: "local5",
        22: "local6", 23: "local7"
    }
    SEVERITIES = {
        0: "Emergency", 1: "Alert", 2: "Critical", 3: "Error",
        4: "Warning", 5: "Notice", 6: "Informational", 7: "Debug"
    }
    
    @staticmethod
    def parse_syslog_message(message: str) -> Tuple[int, int, str]:
        # Format traditionnel: <PRI>Timestamp Host Message
        pri_match = re.match(r'<(\d+)>(.*)', message)
        if pri_match:
            pri = int(pri_match.group(1))
            facility_num = pri // 8
            severity_num = pri % 8
            parsed_message = pri_match.group(2)
        else:
            facility_num = 23  # local7 par défaut
            severity_num = 6   # info par défaut
            parsed_message = message
        return facility_num, severity_num, parsed_message
    
    @staticmethod
    def get_facility_name(facility_num: int) -> str:
        return SyslogParser.FACILITIES.get(facility_num, f"unknown({facility_num})")
    
    @staticmethod
    def get_severity_name(severity_num: int) -> str:
        return SyslogParser.SEVERITIES.get(severity_num, f"unknown({severity_num})")
    
    @staticmethod
    def get_severity_color(severity_num: int) -> str:
        colors = {
            0: "#FF0000",  # Emergency - Rouge vif
            1: "#FF1A1A",  # Alert - Rouge intense
            2: "#FF3333",  # Critical - Rouge
            3: "#FF6600",  # Error - Orange vif
            4: "#FFCC00",  # Warning - Jaune-orange
            5: "#FFFF00",  # Notice - Jaune
            6: "#FFFFFF",  # Informational - Blanc
            7: "#CCCCCC"   # Debug - Gris clair
        }
        return colors.get(severity_num, "#FFFFFF")
    
    @staticmethod
    def get_severity_background(severity_num: int) -> str:
        """Retourne une couleur de fond en fonction de la sévérité pour meilleure visibilité"""
        bg_colors = {
            0: "#990000",  # Emergency - Rouge foncé
            1: "#CC0000",  # Alert - Rouge
            2: "#CC3333",  # Critical - Rouge-brun
            3: "#CC6600",  # Error - Orange foncé
            4: None,       # Warning - Pas de fond
            5: None,       # Notice - Pas de fond
            6: None,       # Informational - Pas de fond
            7: None        # Debug - Pas de fond
        }
        return bg_colors.get(severity_num)

class ServerConfig:
    def __init__(self):
        self.host: str = "0.0.0.0"
        self.port: int = DEFAULT_PORT
        self.buffer_size: int = 8192
        self.auto_start: bool = False
        self.save_logs: bool = True
        self.log_directory: str = os.path.join(os.path.expanduser("~"), "syslog_logs")
        self.filters: dict = {
            "enabled": False,
            "hosts": [],
            "facilities": [],
            "severities": [],
            "keywords": []
        }
        # Nouvelles options d'interface utilisateur
        self.ui_options: dict = {
            "theme": "modern",      # Options: modern, classic, dark
            "font_size": 10,        # Taille de police par défaut
            "auto_scroll": True,    # Défilement automatique des logs
            "timestamp_format": "standard",  # Options: standard, iso, short
            "max_log_entries": MAX_LOG_ENTRIES  # Nombre maximum d'entrées dans les tables
        }
        self.load_config()
        
    def save_config(self) -> None:
        settings = QSettings("SyslogServer", "Config")
        settings.setValue("host", self.host)
        settings.setValue("port", self.port)
        settings.setValue("buffer_size", self.buffer_size)
        settings.setValue("auto_start", self.auto_start)
        settings.setValue("save_logs", self.save_logs)
        settings.setValue("log_directory", self.log_directory)
        settings.setValue("filters", json.dumps(self.filters))
        settings.setValue("ui_options", json.dumps(self.ui_options))
        
    def load_config(self) -> None:
        settings = QSettings("SyslogServer", "Config")
        if settings.contains("host"):
            self.host = settings.value("host")
        if settings.contains("port"):
            self.port = int(settings.value("port"))
        if settings.contains("buffer_size"):
            self.buffer_size = int(settings.value("buffer_size"))
        if settings.contains("auto_start"):
            self.auto_start = settings.value("auto_start") == "true"
        if settings.contains("save_logs"):
            self.save_logs = settings.value("save_logs") == "true"
        if settings.contains("log_directory"):
            self.log_directory = settings.value("log_directory")
        if settings.contains("filters"):
            try:
                self.filters = json.loads(settings.value("filters"))
            except Exception:
                pass
        if settings.contains("ui_options"):
            try:
                self.ui_options = json.loads(settings.value("ui_options"))
            except Exception:
                pass

class SyslogStats:
    def __init__(self):
        self.reset()
        
    def reset(self) -> None:
        self.message_count: int = 0
        self.start_time: datetime = datetime.now()
        self.messages_per_host: Dict[str, int] = defaultdict(int)
        self.messages_per_facility: Dict[int, int] = defaultdict(int)
        self.messages_per_severity: Dict[int, int] = defaultdict(int)
        self.messages_per_hour: Dict[int, int] = defaultdict(int)
        
    def update(self, host: str, facility: int, severity: int) -> None:
        self.message_count += 1
        self.messages_per_host[host] += 1
        self.messages_per_facility[facility] += 1
        self.messages_per_severity[severity] += 1
        hour = datetime.now().hour
        self.messages_per_hour[hour] += 1
        
    def get_stats_dict(self) -> dict:
        uptime = (datetime.now() - self.start_time).total_seconds()
        msgs_per_sec = self.message_count / max(1, uptime)
        top_hosts = sorted(self.messages_per_host.items(), key=lambda x: x[1], reverse=True)[:10]
        return {
            "message_count": self.message_count,
            "uptime_seconds": uptime,
            "msgs_per_second": msgs_per_sec,
            "top_hosts": dict(top_hosts),
            "per_facility": dict(self.messages_per_facility),
            "per_severity": dict(self.messages_per_severity),
            "per_hour": dict(self.messages_per_hour)
        }

class SyslogServer:
    def __init__(self, config: Optional[ServerConfig] = None) -> None:
        self.config: ServerConfig = config or ServerConfig()
        self.running: bool = False
        self.sock: Optional[socket.socket] = None
        self.worker: Optional[threading.Thread] = None
        self.signals: SyslogServerSignals = SyslogServerSignals()
        self.stats: SyslogStats = SyslogStats()
        self.active_hosts: Set[str] = set()  # Pour suivre les hôtes actifs
        
        # Timer pour les stats
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.emit_stats)
        self.stats_timer.start(5000)  # Mise à jour toutes les 5 secondes
        
        # Timer pour les hôtes actifs
        self.hosts_timer = QTimer()
        self.hosts_timer.timeout.connect(self.emit_active_hosts)
        self.hosts_timer.start(10000)  # Mise à jour toutes les 10 secondes
        
        # Création des répertoires nécessaires
        self._ensure_directories()
        
    def start(self) -> None:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.config.host, self.config.port))
            self.running = True
            logger.info(f"Syslog Server démarré sur {self.config.host}:{self.config.port}")
            self.signals.server_started.emit(self.config.host, self.config.port)
            self.stats.reset()
            self.active_hosts.clear()
            if self.config.save_logs and not os.path.exists(self.config.log_directory):
                os.makedirs(self.config.log_directory)
            self.worker = threading.Thread(target=self._receive_loop, daemon=True)
            self.worker.start()
        except Exception as e:
            logger.error(f"Erreur lors du démarrage du serveur syslog: {e}")
            self.signals.log_message.emit("ERROR", f"Erreur lors du démarrage: {e}")
            self.running = False

    def stop(self) -> None:
        self.running = False
        try:
            if self.sock:
                self.sock.close()
                self.sock = None
            logger.info("Syslog Server arrêté")
            self.signals.server_stopped.emit()
        except Exception as e:
            logger.error(f"Erreur lors de l'arrêt du serveur syslog: {e}")
            self.signals.log_message.emit("ERROR", f"Erreur lors de l'arrêt: {e}")

    def _receive_loop(self) -> None:
        log_files = {}  # Dict[str, Dict[str, Any]]
        while self.running:
            try:
                self.sock.settimeout(0.5)
                try:
                    data, addr = self.sock.recvfrom(self.config.buffer_size)
                except socket.timeout:
                    continue
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                src_ip = addr[0]
                src_port = addr[1]
                src = f"{src_ip}:{src_port}"
                
                # Ajouter à la liste des hôtes actifs
                self.active_hosts.add(src_ip)
                
                try:
                    raw_message = data.decode('utf-8', errors='replace').strip()
                    facility_num, severity_num, parsed_message = SyslogParser.parse_syslog_message(raw_message)
                    self.stats.update(src_ip, facility_num, severity_num)
                    
                    if self.config.filters["enabled"]:
                        if self.config.filters["hosts"] and src_ip not in self.config.filters["hosts"]:
                            continue
                        if self.config.filters["facilities"] and facility_num not in self.config.filters["facilities"]:
                            continue
                        if self.config.filters["severities"] and severity_num not in self.config.filters["severities"]:
                            continue
                        if self.config.filters["keywords"]:
                            if not any(keyword.lower() in parsed_message.lower() for keyword in self.config.filters["keywords"]):
                                continue
                    
                    if self.config.save_logs:
                        log_date = datetime.now().strftime("%Y-%m-%d")
                        log_filename = os.path.join(self.config.log_directory, f"{src_ip}_{log_date}.log")
                        if src_ip not in log_files or log_date not in log_files[src_ip]:
                            try:
                                if src_ip in log_files:
                                    log_files[src_ip]["file"].close()
                                log_files[src_ip] = {"date": log_date, "file": open(log_filename, "a", encoding="utf-8")}
                            except Exception as e:
                                logger.error(f"Erreur lors de l'ouverture du fichier de log {log_filename}: {e}")
                        try:
                            log_file = log_files[src_ip]["file"]
                            log_file.write(f"[{timestamp}] <{facility_num}.{severity_num}> {parsed_message}\n")
                            log_file.flush()
                        except Exception as e:
                            logger.error(f"Erreur lors de l'écriture du fichier de log: {e}")
                    logger.debug(f"Message reçu de {src}: {parsed_message}")
                    self.signals.new_message.emit(timestamp, src, facility_num, severity_num, parsed_message)
                except Exception as e:
                    logger.error(f"Erreur lors du traitement du message: {e}")
                    self.signals.log_message.emit("ERROR", f"Erreur lors du traitement du message: {e}")
            except Exception as e:
                logger.error(f"Erreur dans la réception syslog: {e}")
                self.signals.log_message.emit("ERROR", f"Erreur dans la réception: {e}")
        
        # Fermeture des fichiers de logs à la fin
        for host in log_files:
            try:
                log_files[host]["file"].close()
            except Exception:
                pass

    def emit_stats(self) -> None:
        if self.running:
            stats = self.stats.get_stats_dict()
            self.signals.stats_updated.emit(stats)
    
    def emit_active_hosts(self) -> None:
        if self.running:
            self.signals.active_hosts_updated.emit(self.active_hosts)

    def _ensure_directories(self) -> None:
        if self.config.save_logs and not os.path.exists(self.config.log_directory):
            os.makedirs(self.config.log_directory)

# --- Widget d'affichage des logs ---
class EnhancedLogTable(QTableWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(0, 5, parent)
        self.setHorizontalHeaderLabels(["Timestamp", "Source", "Facility", "Severity", "Message"])
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showContextMenu)
        self.max_entries = MAX_LOG_ENTRIES
        self.filtered_host = None  # Pour filtrer par hôte
        self.all_rows = []  # Pour stocker toutes les lignes avant filtrage
        
    def addMessage(self, timestamp: str, source: str, facility_num: int, severity_num: int, message: str) -> None:
        # Si filtre actif, vérifier si ce message correspond au filtre
        source_ip = source.split(":")[0]
        if self.filtered_host and source_ip != self.filtered_host:
            # Stocker quand même le message pour pouvoir le récupérer si le filtre change
            self.all_rows.append((timestamp, source, facility_num, severity_num, message))
            if len(self.all_rows) > self.max_entries * 2:  # Limiter la taille
                self.all_rows = self.all_rows[len(self.all_rows) - self.max_entries:]
            return
            
        if self.rowCount() >= self.max_entries:
            self.removeRow(0)
        
        row = self.rowCount()
        self.insertRow(row)
        
        facility_name = SyslogParser.get_facility_name(facility_num)
        severity_name = SyslogParser.get_severity_name(severity_num)
        severity_color = SyslogParser.get_severity_color(severity_num)
        severity_bg = SyslogParser.get_severity_background(severity_num)
        
        timestamp_item = QTableWidgetItem(timestamp)
        source_item = QTableWidgetItem(source)
        facility_item = QTableWidgetItem(facility_name)
        severity_item = QTableWidgetItem(severity_name)
        message_item = QTableWidgetItem(message)
        
        # Personnalisation avancée des couleurs selon la sévérité
        for item in [timestamp_item, source_item, facility_item, severity_item, message_item]:
            # Couleur du texte basée sur la sévérité
            item.setForeground(QBrush(QColor(severity_color)))
            
            # Fond coloré pour les sévérités importantes
            if severity_bg:
                item.setBackground(QBrush(QColor(severity_bg)))
                
            # Gras pour les messages critiques
            if severity_num <= 2:  # Emergency, Alert, Critical
                font = QFont()
                font.setBold(True)
                item.setFont(font)
        
        self.setItem(row, 0, timestamp_item)
        self.setItem(row, 1, source_item)
        self.setItem(row, 2, facility_item)
        self.setItem(row, 3, severity_item)
        self.setItem(row, 4, message_item)
        
        # Assurer que le nouveau message est visible
        self.scrollToBottom()
    
    def setFilterHost(self, host: Optional[str]) -> None:
        """Filtre les logs pour n'afficher que ceux de l'hôte spécifié"""
        self.filtered_host = host
        self.clearTable()
        
        if not host or host == "Tous les équipements":
            # Afficher tous les messages stockés
            for msg in self.all_rows[-self.max_entries:]:
                self.addMessage(msg[0], msg[1], msg[2], msg[3], msg[4])
        else:
            # Filtrer et afficher seulement les messages de l'hôte spécifié
            filtered_msgs = [msg for msg in self.all_rows if msg[1].split(":")[0] == host]
            for msg in filtered_msgs[-self.max_entries:]:
                self.addMessage(msg[0], msg[1], msg[2], msg[3], msg[4])
    
    def clearTable(self) -> None:
        """Vide la table sans perdre les données"""
        self.clearContents()
        self.setRowCount(0)
        
    def showContextMenu(self, position) -> None:
        menu = QMenu()
        copy_action = menu.addAction("Copier")
        clear_action = menu.addAction("Effacer la vue")
        export_action = menu.addAction("Exporter la sélection...")
        
        selected_indexes = self.selectedIndexes()
        if not selected_indexes:
            copy_action.setEnabled(False)
            export_action.setEnabled(False)
        
        action = menu.exec_(self.mapToGlobal(position))
        if action == copy_action:
            self.copySelectedToClipboard()
        elif action == clear_action:
            self.clearTable()
            self.all_rows = []  # Effacer aussi l'historique
        elif action == export_action:
            self.exportSelection()
            
    def copySelectedToClipboard(self) -> None:
        selected_rows = {index.row() for index in self.selectedIndexes()}
        text = ""
        for row in sorted(selected_rows):
            row_data = []
            for col in range(self.columnCount()):
                item = self.item(row, col)
                row_data.append(item.text() if item else "")
            text += "\t".join(row_data) + "\n"
        QApplication.clipboard().setText(text)
        
    def exportSelection(self) -> None:
        selected_rows = {index.row() for index in self.selectedIndexes()}
        if not selected_rows:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter la sélection",
            os.path.join(os.path.expanduser("~"), "syslog_export.txt"),
            "Fichiers texte (*.txt);;Fichiers CSV (*.csv);;Tous les fichiers (*)"
        )
        if not file_path:
            return
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                headers = [self.horizontalHeaderItem(col).text() for col in range(self.columnCount())]
                if file_path.lower().endswith('.csv'):
                    f.write(",".join([f'"{h}"' for h in headers]) + "\n")
                    for row in sorted(selected_rows):
                        row_data = []
                        for col in range(self.columnCount()):
                            item = self.item(row, col)
                            cell_text = item.text() if item else ""
                            escaped_text = cell_text.replace('"', '""')
                            row_data.append(f'"{escaped_text}"')
                        f.write(",".join(row_data) + "\n")
                else:
                    f.write("\t".join(headers) + "\n")
                    f.write("-" * 100 + "\n")
                    for row in sorted(selected_rows):
                        row_data = [self.item(row, col).text() if self.item(row, col) else "" for col in range(self.columnCount())]
                        f.write("\t".join(row_data) + "\n")
            QMessageBox.information(self, "Export réussi", f"Les données ont été exportées vers {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de l'export: {e}")

# --- Widget pour afficher les logs par hôte ---
class HostLogWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hosts = {}  # Dict[str, Dict[str, Any]]
        self.config = ServerConfig()  # Référence à la configuration
        self.initUI()
        
    def initUI(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Groupe pour les contrôles et la recherche
        controls_group = QGroupBox("Contrôles des logs")
        controls_group.setObjectName("sectionGroup")
        controls_layout = QVBoxLayout(controls_group)
        
        # Barre d'outils pour les hôtes - améliorée
        toolbar_layout = QHBoxLayout()
        
        # Partie recherche
        search_layout = QHBoxLayout()
        search_label = QLabel("Recherche:")
        self.search_host = QLineEdit()
        self.search_host.setPlaceholderText("Rechercher un hôte...")
        self.search_host.textChanged.connect(self.filterHosts)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_host, 1)
        
        # Boutons d'action avec style cohérent
        refresh_btn = QPushButton("🔄 Actualiser")
        refresh_btn.setObjectName("settingsButton")  # Style bleu info
        refresh_btn.clicked.connect(self.refreshHostList)
        
        collapse_all_btn = QPushButton("📁 Replier tout")
        collapse_all_btn.setObjectName("settingsButton")  # Style bleu info
        collapse_all_btn.clicked.connect(self.collapseAllTabs)
        
        # Bouton pour définir le dossier de sauvegarde
        save_folder_btn = QPushButton("📂 Dossier de sauvegarde")
        save_folder_btn.setObjectName("saveButton")  # Style vert success
        save_folder_btn.clicked.connect(self.configureSaveFolder)
        
        toolbar_layout.addLayout(search_layout)
        toolbar_layout.addWidget(refresh_btn)
        toolbar_layout.addWidget(collapse_all_btn)
        toolbar_layout.addWidget(save_folder_btn)
        
        controls_layout.addLayout(toolbar_layout)
        
        # Affichage du dossier de sauvegarde actuel
        self.save_dir_layout = QHBoxLayout()
        self.save_dir_layout.addWidget(QLabel("Dossier de sauvegarde:"))
        self.save_dir_label = QLabel(self.config.log_directory)
        self.save_dir_label.setStyleSheet("color: #3498db; font-weight: bold;")
        self.save_dir_layout.addWidget(self.save_dir_label, 1)
        
        controls_layout.addLayout(self.save_dir_layout)
        
        layout.addWidget(controls_group)
        
        # Zone principale avec liste des hôtes et onglets de logs - style amélioré
        main_group = QGroupBox("Logs par hôte")
        main_group.setObjectName("sectionGroup")
        main_layout = QVBoxLayout(main_group)
        
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)  # Empêche de réduire complètement un panneau
        
        # Liste des hôtes avec regroupement par réseau
        host_panel = QWidget()
        host_panel_layout = QVBoxLayout(host_panel)
        host_panel_layout.setContentsMargins(0, 0, 0, 0)
        
        # Étiquette pour la liste des hôtes
        hosts_label = QLabel("Liste des hôtes")
        hosts_label.setProperty("subtitle", "true")
        host_panel_layout.addWidget(hosts_label)
        
        self.host_list = QTreeWidget()
        self.host_list.setHeaderLabels(["Hôtes"])
        self.host_list.setMinimumWidth(250)
        self.host_list.itemClicked.connect(self.hostSelected)
        
        host_panel_layout.addWidget(self.host_list)
        
        # Panneau d'onglets pour les logs
        self.log_tabs = QTabWidget()
        self.log_tabs.setTabsClosable(True)
        self.log_tabs.tabCloseRequested.connect(self.closeHostTab)
        
        # Ajout des composants au splitter
        splitter.addWidget(host_panel)
        splitter.addWidget(self.log_tabs)
        splitter.setSizes([250, 750])
        
        main_layout.addWidget(splitter)
        layout.addWidget(main_group, 1)  # 1 pour que ce widget prenne tout l'espace disponible
    
    def configureSaveFolder(self) -> None:
        """Configure le dossier de sauvegarde des logs"""
        current_dir = self.config.log_directory
        new_dir = QFileDialog.getExistingDirectory(
            self, 
            "Sélectionner le dossier de sauvegarde des logs",
            current_dir
        )
        
        if new_dir:
            self.config.log_directory = new_dir
            self.config.save_config()
            self.save_dir_label.setText(new_dir)
            QMessageBox.information(
                self, 
                "Dossier de sauvegarde", 
                f"Le dossier de sauvegarde a été défini à:\n{new_dir}"
            )
        
    def filterHosts(self, text):
        """Filtre la liste des hôtes en fonction du texte de recherche"""
        search_text = text.lower()
        for i in range(self.host_list.topLevelItemCount()):
            network_item = self.host_list.topLevelItem(i)
            
            # Recherche dans les enfants (hôtes)
            visible_children = 0
            for j in range(network_item.childCount()):
                host_item = network_item.child(j)
                if search_text in host_item.text(0).lower():
                    host_item.setHidden(False)
                    visible_children += 1
                else:
                    host_item.setHidden(True)
            
            # Afficher/masquer le noeud réseau en fonction de ses enfants
            network_item.setHidden(visible_children == 0)
            
    def refreshHostList(self):
        """Actualise la liste des hôtes"""
        # Sauvegarder l'état d'expansion
        expanded_networks = set()
        for i in range(self.host_list.topLevelItemCount()):
            network_item = self.host_list.topLevelItem(i)
            if network_item.isExpanded():
                expanded_networks.add(network_item.text(0))
        
        # Reconstruire l'arborescence
        self.rebuildHostTree()
        
        # Restaurer l'état d'expansion
        for i in range(self.host_list.topLevelItemCount()):
            network_item = self.host_list.topLevelItem(i)
            if network_item.text(0) in expanded_networks:
                network_item.setExpanded(True)
                
    def rebuildHostTree(self):
        """Reconstruit l'arborescence des hôtes par réseau"""
        self.host_list.clear()
        
        # Regrouper les hôtes par réseau (simplement par les 3 premiers octets)
        networks = {}
        for host in self.hosts.keys():
            ip_parts = host.split('.')
            if len(ip_parts) >= 3:  # S'assurer que c'est bien une IPv4
                network = '.'.join(ip_parts[:3])
                if network not in networks:
                    networks[network] = []
                networks[network].append(host)
        
        # Créer l'arborescence
        for network, hosts in networks.items():
            network_item = QTreeWidgetItem(self.host_list, [f"Réseau {network}.0/24"])
            network_item.setExpanded(True)
            
            for host in sorted(hosts, key=lambda x: [int(p) if p.isdigit() else p for p in x.split('.')]):
                host_item = QTreeWidgetItem(network_item, [host])
                # Ajouter une icône ou un indicateur si des logs sont disponibles
                if self.hosts[host]["tab_index"] >= 0:
                    host_item.setForeground(0, QBrush(QColor("#2980b9")))
                    host_item.setFont(0, QFont("", -1, QFont.Bold))
        
    def collapseAllTabs(self):
        """Ferme tous les onglets ouverts"""
        while self.log_tabs.count() > 0:
            self.closeHostTab(0)
        
    def addHost(self, host: str) -> None:
        if host not in self.hosts:
            # Ajouter l'hôte au dictionnaire
            log_table = EnhancedLogTable()
            self.hosts[host] = {"table": log_table, "tab_index": -1}
            
            # Mettre à jour l'arborescence
            self.refreshHostList()
            
    def hostSelected(self, item, column) -> None:
        """Gère la sélection d'un hôte dans l'arborescence"""
        if item.parent() is None:
            # C'est un réseau, pas un hôte
            return
            
        host = item.text(0)
        if host in self.hosts:
            if self.hosts[host]["tab_index"] >= 0:
                self.log_tabs.setCurrentIndex(self.hosts[host]["tab_index"])
            else:
                log_table = self.hosts[host]["table"]
                tab_index = self.log_tabs.addTab(log_table, host)
                self.hosts[host]["tab_index"] = tab_index
                self.log_tabs.setCurrentIndex(tab_index)
                item.setForeground(0, QBrush(QColor("#2980b9")))
                item.setFont(0, QFont("", -1, QFont.Bold))
                
    def closeHostTab(self, index: int) -> None:
        host_to_close = None
        for host, info in self.hosts.items():
            if info["tab_index"] == index:
                host_to_close = host
                break
        if host_to_close:
            self.hosts[host_to_close]["tab_index"] = -1
            for host, info in self.hosts.items():
                if info["tab_index"] > index:
                    info["tab_index"] -= 1
            self.log_tabs.removeTab(index)
            
            # Mettre à jour le style dans l'arborescence
            for i in range(self.host_list.topLevelItemCount()):
                network_item = self.host_list.topLevelItem(i)
                for j in range(network_item.childCount()):
                    host_item = network_item.child(j)
                    if host_item.text(0) == host_to_close:
                        host_item.setForeground(0, self.host_list.foreground(0))
                        host_item.setFont(0, self.host_list.font())
                        break
            
    def addMessage(self, host: str, timestamp: str, source: str, facility_num: int, severity_num: int, message: str) -> None:
        host_ip = source.split(":")[0]
        if host_ip not in self.hosts:
            self.addHost(host_ip)
        self.hosts[host_ip]["table"].addMessage(timestamp, source, facility_num, severity_num, message)
        
    def clearLogs(self) -> None:
        for host, info in self.hosts.items():
            info["table"].clearTable()

# --- Widget de statistiques amélioré ---
class StatsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.current_stats = {}  # Stockage des statistiques actuelles
        self.initUI()
        
    def initUI(self) -> None:
        layout = QVBoxLayout(self)
        
        # Panneau d'information générale
        info_panel = QWidget()
        info_layout = QHBoxLayout(info_panel)
        
        # Carte d'information - Uptime
        uptime_card = QGroupBox("Temps de fonctionnement")
        uptime_card.setObjectName("sectionGroup")
        uptime_layout = QVBoxLayout(uptime_card)
        self.uptime_label = QLabel("0 secondes")
        self.uptime_label.setProperty("subtitle", "true")
        self.uptime_label.setAlignment(Qt.AlignCenter)
        uptime_layout.addWidget(self.uptime_label)
        info_layout.addWidget(uptime_card)
        
        # Carte d'information - Total des messages
        msg_count_card = QGroupBox("Nombre total de messages")
        msg_count_card.setObjectName("sectionGroup")
        msg_count_layout = QVBoxLayout(msg_count_card)
        self.msg_count_label = QLabel("0")
        self.msg_count_label.setProperty("subtitle", "true")
        self.msg_count_label.setAlignment(Qt.AlignCenter)
        msg_count_layout.addWidget(self.msg_count_label)
        info_layout.addWidget(msg_count_card)
        
        # Carte d'information - Débit
        msg_rate_card = QGroupBox("Débit de messages")
        msg_rate_card.setObjectName("sectionGroup")
        msg_rate_layout = QVBoxLayout(msg_rate_card)
        self.msg_rate_label = QLabel("0 / sec")
        self.msg_rate_label.setProperty("subtitle", "true")
        self.msg_rate_label.setAlignment(Qt.AlignCenter)
        msg_rate_layout.addWidget(self.msg_rate_label)
        info_layout.addWidget(msg_rate_card)
        
        layout.addWidget(info_panel)
        
        # Séparateur
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # Panneau des statistiques détaillées avec onglets
        stats_tabs = QTabWidget()
        
        # Onglet "Top Hôtes"
        hosts_tab = QWidget()
        hosts_layout = QVBoxLayout(hosts_tab)
        self.hosts_list = QTableWidget(0, 2)
        self.hosts_list.setHorizontalHeaderLabels(["Hôte", "Messages"])
        self.hosts_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.hosts_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.hosts_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hosts_list.setAlternatingRowColors(True)
        hosts_layout.addWidget(self.hosts_list)
        stats_tabs.addTab(hosts_tab, "Top Hôtes")
        
        # Onglet "Par Facility"
        facility_tab = QWidget()
        facility_layout = QVBoxLayout(facility_tab)
        self.facility_list = QTableWidget(0, 2)
        self.facility_list.setHorizontalHeaderLabels(["Facility", "Messages"])
        self.facility_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.facility_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.facility_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.facility_list.setAlternatingRowColors(True)
        facility_layout.addWidget(self.facility_list)
        stats_tabs.addTab(facility_tab, "Par Facility")
        
        # Onglet "Par Sévérité"
        severity_tab = QWidget()
        severity_layout = QVBoxLayout(severity_tab)
        self.severity_list = QTableWidget(0, 2)
        self.severity_list.setHorizontalHeaderLabels(["Sévérité", "Messages"])
        self.severity_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.severity_list.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.severity_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.severity_list.setAlternatingRowColors(True)
        severity_layout.addWidget(self.severity_list)
        stats_tabs.addTab(severity_tab, "Par Sévérité")
        
        # Ajout du panneau d'onglets au layout principal
        layout.addWidget(stats_tabs, 1)  # 1 pour que ce widget prenne tout l'espace disponible
        
        # Bouton de réinitialisation des statistiques
        reset_btn = QPushButton("Réinitialiser les statistiques")
        reset_btn.setObjectName("clearButton")  # Rouge danger
        reset_btn.clicked.connect(self.resetStatsRequested)
        layout.addWidget(reset_btn)
        
    def resetStatsRequested(self):
        reply = QMessageBox.question(
            self, 
            "Réinitialiser les statistiques", 
            "Êtes-vous sûr de vouloir réinitialiser toutes les statistiques?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.parent().resetServerStats()
        
    def updateStats(self, stats: dict) -> None:
        # Mise à jour des informations générales
        uptime_seconds = stats["uptime_seconds"]
        if uptime_seconds < 60:
            uptime_text = f"{uptime_seconds:.1f} secondes"
        elif uptime_seconds < 3600:
            uptime_text = f"{uptime_seconds/60:.1f} minutes"
        else:
            uptime_text = f"{uptime_seconds/3600:.1f} heures"
        self.uptime_label.setText(uptime_text)
        self.msg_count_label.setText(f"{stats['message_count']:,}".replace(',', ' '))
        self.msg_rate_label.setText(f"{stats['msgs_per_second']:.2f} / sec")
        
        # Mise à jour de la liste des hôtes
        self.hosts_list.setRowCount(0)
        for host, count in stats["top_hosts"].items():
            row = self.hosts_list.rowCount()
            self.hosts_list.insertRow(row)
            self.hosts_list.setItem(row, 0, QTableWidgetItem(host))
            self.hosts_list.setItem(row, 1, QTableWidgetItem(str(count)))
        
        # Mise à jour de la liste des facilities
        self.facility_list.setRowCount(0)
        for facility_num, count in stats["per_facility"].items():
            row = self.facility_list.rowCount()
            self.facility_list.insertRow(row)
            facility_name = SyslogParser.get_facility_name(int(facility_num))
            self.facility_list.setItem(row, 0, QTableWidgetItem(f"{facility_name} ({facility_num})"))
            self.facility_list.setItem(row, 1, QTableWidgetItem(str(count)))
        
        # Mise à jour de la liste des sévérités
        self.severity_list.setRowCount(0)
        for severity_num, count in stats["per_severity"].items():
            row = self.severity_list.rowCount()
            self.severity_list.insertRow(row)
            severity_name = SyslogParser.get_severity_name(int(severity_num))
            self.severity_list.setItem(row, 0, QTableWidgetItem(f"{severity_name} ({severity_num})"))
            self.severity_list.setItem(row, 1, QTableWidgetItem(str(count)))
            # Coloration en fonction de la sévérité
            severity_color = SyslogParser.get_severity_color(int(severity_num))
            if int(severity_num) <= 3:  # Emergency, Alert, Critical, Error
                for col in range(2):
                    self.severity_list.item(row, col).setForeground(QBrush(QColor(severity_color)))
                    if int(severity_num) <= 2:  # Emergency, Alert, Critical
                        self.severity_list.item(row, col).setFont(QFont("", -1, QFont.Bold))

# Classe de boîte de dialogue d'erreur moderne
class ModernErrorDialog(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QMessageBox.Critical)
        self.setWindowTitle("Erreur")
        
    def show_error(self, title: str, message: str) -> None:
        self.setWindowTitle(title)
        self.setText(message)
        self.exec_()

class SyslogServerGUI(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - v{APP_VERSION}")
        self.setMinimumSize(900, 650)
        self.config = ServerConfig()
        self.server = None
        self.active_hosts = set()  # Pour stocker les hôtes actifs

        # Onglets principaux en haut
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setObjectName("mainTabWidget")
        
        # Création du widget pour les logs par hôte
        self.host_log_widget = HostLogWidget()
        
        self.setupTabs()

        # Layout principal moderne avec marges et espacements réduits
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.addWidget(self.tab_widget)

        # Connexion des signaux
        self.setupConnections()

        # Barre d'état
        self.statusBar().showMessage("Prêt")

        # Application du style général cohérent
        self.applyStyles()

    def setupTabs(self):
        self.addConfigTab()
        self.addLogsTab()
        self.addStatsTab()
        self.addHostsTab()  # Onglet pour les logs par hôte

    def addConfigTab(self):
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setSpacing(15)
        config_layout.setContentsMargins(20, 20, 20, 20)

        # Groupe Contrôle du Serveur
        server_controls = QGroupBox("Contrôle du Serveur")
        server_controls.setObjectName("sectionGroup")
        server_controls_layout = QHBoxLayout(server_controls)
        self.start_button = QPushButton("🟢 Démarrer")
        self.start_button.setObjectName("connectButton")
        self.stop_button = QPushButton("🔴 Arrêter")
        self.stop_button.setObjectName("disconnectButton")
        self.stop_button.setEnabled(False)
        server_controls_layout.addWidget(self.start_button)
        server_controls_layout.addWidget(self.stop_button)
        config_layout.addWidget(server_controls)

        # Groupe État du Serveur
        status_group = QGroupBox("État du Serveur")
        status_group.setObjectName("sectionGroup")
        status_layout = QHBoxLayout(status_group)
        self.status_label = QLabel("⚪ En attente")
        self.status_label.setStyleSheet("""
            padding: 5px;
            border-radius: 3px;
            background-color: #2c3e50;
            color: #ecf0f1;
            font-weight: bold;
            font-size: 15px;
        """)
        status_layout.addWidget(self.status_label)
        config_layout.addWidget(status_group)

        # Groupe Statistiques en temps réel
        stats_group = QGroupBox("Statistiques")
        stats_group.setObjectName("sectionGroup")
        stats_layout = QHBoxLayout(stats_group)
        self.msg_count_label = QLabel("Messages: 0")
        self.msg_count_label.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 15px;")
        self.msg_rate_label = QLabel("Débit: 0/s")
        self.msg_rate_label.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 15px;")
        stats_layout.addWidget(self.msg_count_label)
        stats_layout.addWidget(self.msg_rate_label)
        config_layout.addWidget(stats_group)

        # Groupe Log d'application
        log_group = QGroupBox("Log d'application")
        log_group.setObjectName("sectionGroup")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextBrowser()
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("""
            background-color: #1e2a36;
            color: #94a3b8;
            border: 1px solid #3d566e;
            border-radius: 6px;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 13px;
        """)
        log_layout.addWidget(self.log_text)
        config_layout.addWidget(log_group)

        # Configuration réseau (dans le même onglet)
        network_group = self.createNetworkGroup()
        config_layout.addWidget(network_group)

        # Options avancées
        advanced_group = self.createAdvancedGroup()
        config_layout.addWidget(advanced_group)

        config_layout.addStretch()
        self.tab_widget.addTab(config_widget, "Configuration")

    def createNetworkGroup(self):
        group = QGroupBox("Configuration Réseau")
        group.setObjectName("sectionGroup")
        layout = QFormLayout(group)
        self.host_combo = QComboBox()
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(DEFAULT_PORT)
        if NETIFACES_AVAILABLE:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        self.host_combo.addItem(f"{iface} - {addr['addr']}", addr['addr'])
        layout.addRow("Interface:", self.host_combo)
        layout.addRow("Port:", self.port_spin)
        return group

    def createAdvancedGroup(self):
        group = QGroupBox("Options Avancées")
        group.setObjectName("sectionGroup")
        layout = QVBoxLayout(group)
        self.auto_start_check = QCheckBox("Démarrage automatique")
        self.save_logs_check = QCheckBox("Sauvegarder les logs")
        layout.addWidget(self.auto_start_check)
        layout.addWidget(self.save_logs_check)
        return group

    def addLogsTab(self):
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        logs_layout.setSpacing(10)
        logs_layout.setContentsMargins(20, 20, 20, 20)
        
        # Contrôles améliorés pour la gestion des logs
        controls_layout = QHBoxLayout()
        
        # Ajout de la liste déroulante des équipements actifs
        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filtrer par équipement:")
        self.host_filter_combo = QComboBox()
        self.host_filter_combo.addItem("Tous les équipements")
        self.host_filter_combo.setMinimumWidth(200)
        self.host_filter_combo.currentTextChanged.connect(self.filterLogsByHost)
        
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.host_filter_combo)
        
        # Boutons d'action
        clear_logs_btn = QPushButton("Effacer les logs")
        clear_logs_btn.setObjectName("clearButton")  # Rouge danger
        export_logs_btn = QPushButton("Exporter les logs")
        export_logs_btn.setObjectName("saveButton")  # Vert success
        
        clear_logs_btn.clicked.connect(self.clearLogs)
        export_logs_btn.clicked.connect(self.saveLogs)
        
        controls_layout.addLayout(filter_layout)
        controls_layout.addStretch()
        controls_layout.addWidget(clear_logs_btn)
        controls_layout.addWidget(export_logs_btn)
        
        logs_layout.addLayout(controls_layout)
        
        # Table de logs améliorée
        self.log_table = EnhancedLogTable()
        logs_layout.addWidget(self.log_table)
        
        # Légende de couleurs pour les sévérités
        legend_group = QGroupBox("Légende des sévérités")
        legend_group.setObjectName("sectionGroup")
        legend_layout = QHBoxLayout(legend_group)
        
        # Création de labels colorés pour chaque niveau de sévérité
        severities = [
            ("Emergency (0)", "#FF0000", "#990000", True),
            ("Alert (1)", "#FF1A1A", "#CC0000", True),
            ("Critical (2)", "#FF3333", "#CC3333", True),
            ("Error (3)", "#FF6600", "#CC6600", False),
            ("Warning (4)", "#FFCC00", None, False),
            ("Notice (5)", "#FFFF00", None, False),
            ("Info (6)", "#FFFFFF", None, False),
            ("Debug (7)", "#CCCCCC", None, False)
        ]
        
        for name, color, bg, bold in severities:
            label = QLabel(name)
            style = f"color: {color}; border-radius: 3px; padding: 3px;"
            if bg:
                style += f" background-color: {bg};"
            if bold:
                style += " font-weight: bold;"
            label.setStyleSheet(style)
            legend_layout.addWidget(label)
        
        logs_layout.addWidget(legend_group)
        
        self.tab_widget.addTab(logs_widget, "Logs")

    def addStatsTab(self):
        self.stats_widget = StatsWidget()
        self.stats_widget.setContentsMargins(20, 20, 20, 20)
        self.tab_widget.addTab(self.stats_widget, "Statistiques")

    def addHostsTab(self):
        """Ajoute un onglet pour afficher les logs par hôte"""
        self.tab_widget.addTab(self.host_log_widget, "Logs par hôte")

    def applyStyles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2c3e50;
                font-family: "Segoe UI", sans-serif;
                color: #ecf0f1;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #2c3e50;
                border: 1px solid #3d566e;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 14px;
                font-weight: 500;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding-left: 10px;
                background-color: #3498db;
                color: white;
                padding: 2px 10px;
                border-radius: 3px;
                margin-left: 8px;
                font-weight: 500;
            }
            QLabel {
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 1px solid #3d566e;
                background-color: #34495e;
                border-radius: 8px;
                margin: 2px;
                padding: 4px;
            }
            QTabBar::tab {
                background: #2c3e50;
                color: #bdc3c7;
                padding: 8px 18px;
                margin: 1px 1px 0 1px;
                border: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 90px;
                min-height: 28px;
                font-size: 13px;
                font-family: "Segoe UI", sans-serif;
                font-weight: 500;
                transition: background-color 0.2s, color 0.2s;
            }
            QTabBar::tab:hover {
                background-color: #34495e;
                color: #ecf0f1;
            }
            QTabBar::tab:selected {
                background: #34495e;
                border-top: 3px solid #3498db;
                color: #ecf0f1;
                font-weight: 600;
            }
            QTabBar::tab:disabled {
                background: #7f8c8d;
                color: #95a5a6;
            }
            
            /* Styles pour les boutons */
            QPushButton {
                padding: 6px 12px;
                border-radius: 4px;
                                border: none;
                background-color: #34495e;
                color: #ecf0f1;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3d566e;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
            
            /* Styles spécifiques pour les boutons d'action */
            QPushButton#connectButton {
                background-color: #27ae60;
                color: white;
            }
            QPushButton#connectButton:hover {
                background-color: #2ecc71;
            }
            QPushButton#disconnectButton {
                background-color: #c0392b;
                color: white;
            }
            QPushButton#disconnectButton:hover {
                background-color: #e74c3c;
            }
            QPushButton#saveButton {
                background-color: #2980b9;
                color: white;
            }
            QPushButton#saveButton:hover {
                background-color: #3498db;
            }
            QPushButton#clearButton {
                background-color: #c0392b;
                color: white;
            }
            QPushButton#clearButton:hover {
                background-color: #e74c3c;
            }
            QPushButton#settingsButton {
                background-color: #16a085;
                color: white;
            }
            QPushButton#settingsButton:hover {
                background-color: #1abc9c;
            }
            
            /* Styles pour les listes et tableaux */
            QTableWidget, QTreeWidget, QListWidget {
                background-color: #1e2a36;
                alternate-background-color: #283747;
                color: #ecf0f1;
                border: 1px solid #3d566e;
                border-radius: 4px;
                selection-background-color: #3498db;
                selection-color: #ffffff;
            }
            QHeaderView::section {
                background-color: #34495e;
                color: #ecf0f1;
                padding: 5px;
                border: 1px solid #2c3e50;
            }
            
            /* Styles pour les combos et spinboxes */
            QComboBox, QSpinBox, QLineEdit {
                background-color: #1e2a36;
                color: #ecf0f1;
                border: 1px solid #3d566e;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #3d566e;
            }
            QComboBox QAbstractItemView {
                background-color: #1e2a36;
                color: #ecf0f1;
                border: 1px solid #3d566e;
                selection-background-color: #3498db;
            }
            
            /* Style pour les étiquettes spéciales */
            QLabel[title="true"] {
                font-size: 16px;
                font-weight: bold;
                color: #3498db;
            }
            QLabel[subtitle="true"] {
                font-size: 14px;
                font-weight: bold;
                color: #2ecc71;
            }
        """)

    def setupConnections(self):
        self.start_button.clicked.connect(self.startServer)
        self.stop_button.clicked.connect(self.stopServer)
        self.auto_start_check.toggled.connect(self.updateConfig)
        self.save_logs_check.toggled.connect(self.updateConfig)
        
        # Initialiser les contrôles avec les valeurs de config
        self.auto_start_check.setChecked(self.config.auto_start)
        self.save_logs_check.setChecked(self.config.save_logs)
        
        if self.config.auto_start:
            QTimer.singleShot(500, self.startServer)
    
    def updateConfig(self):
        """Met à jour la configuration depuis les contrôles de l'interface"""
        self.config.auto_start = self.auto_start_check.isChecked()
        self.config.save_logs = self.save_logs_check.isChecked()
        selected_data = self.host_combo.currentData()
        if selected_data:
            self.config.host = selected_data
        self.config.port = self.port_spin.value()
        self.config.save_config()
        self.addLogMessage("Configuration mise à jour")
            
    def startServer(self) -> None:
        """Démarre le serveur Syslog"""
        try:
            if not self.server:
                self.server = SyslogServer(config=self.config)
                self.server.signals.new_message.connect(self.onNewMessage)
                self.server.signals.log_message.connect(self.addLogMessage)
                self.server.signals.server_started.connect(self.onServerStarted)
                self.server.signals.server_stopped.connect(self.onServerStopped)
                self.server.signals.stats_updated.connect(self.onStatsUpdated)
                self.server.signals.active_hosts_updated.connect(self.onActiveHostsUpdated)
            
            # Récupérer les valeurs actuelles des contrôles
            selected_data = self.host_combo.currentData()
            if selected_data:
                self.config.host = selected_data
            self.config.port = self.port_spin.value()
            self.config.auto_start = self.auto_start_check.isChecked()
            self.config.save_logs = self.save_logs_check.isChecked()
            self.config.save_config()
            
            self.server.start()
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        except Exception as e:
            error_dialog = ModernErrorDialog(self)
            error_dialog.show_error("Erreur de démarrage", str(e))
            self.addLogMessage(f"Erreur au démarrage: {e}", error=True)
            
    def stopServer(self) -> None:
        """Arrête le serveur Syslog"""
        if self.server:
            self.server.stop()
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            
    def onServerStarted(self, host: str, port: int) -> None:
        """Callback lorsque le serveur est démarré"""
        self.statusBar().showMessage(f"Serveur en cours d'exécution sur {host}:{port}")
        self.status_label.setText("🟢 En cours d'exécution")
        self.status_label.setStyleSheet("padding: 5px; border-radius: 3px; background-color: #27ae60; color: white; font-weight: bold;")
        self.addLogMessage(f"Serveur SYSLOG démarré sur {host}:{port}")
        
    def onServerStopped(self) -> None:
        """Callback lorsque le serveur est arrêté"""
        self.statusBar().showMessage("Serveur arrêté")
        self.status_label.setText("🔴 Arrêté")
        self.status_label.setStyleSheet("padding: 5px; border-radius: 3px; background-color: #e74c3c; color: white; font-weight: bold;")
        self.addLogMessage("Serveur SYSLOG arrêté")
    
    def onNewMessage(self, timestamp: str, source: str, facility_num: int, severity_num: int, message: str) -> None:
        """Callback lorsqu'un nouveau message est reçu"""
        self.log_table.addMessage(timestamp, source, facility_num, severity_num, message)
        self.host_log_widget.addMessage(source, timestamp, source, facility_num, severity_num, message)
        
        # Mise à jour des statistiques rapides
        if self.server:
            stats = self.server.stats
            self.msg_count_label.setText(f"Messages: {stats.message_count}")
            uptime = (datetime.now() - stats.start_time).total_seconds()
            msgs_per_sec = stats.message_count / max(1, uptime)
            self.msg_rate_label.setText(f"Débit: {msgs_per_sec:.2f}/s")
    
    def onStatsUpdated(self, stats: dict) -> None:
        """Callback lorsque les statistiques sont mises à jour"""
        self.stats_widget.updateStats(stats)
        self.msg_count_label.setText(f"Messages: {stats['message_count']}")
        self.msg_rate_label.setText(f"Débit: {stats['msgs_per_second']:.2f}/s")
    
    def onActiveHostsUpdated(self, hosts: set) -> None:
        """Callback lorsque la liste des hôtes actifs est mise à jour"""
        self.active_hosts = hosts
        
        # Sauvegarder l'hôte sélectionné actuellement
        current_host = self.host_filter_combo.currentText()
        
        # Mettre à jour la liste déroulante des hôtes en préservant la sélection
        self.host_filter_combo.blockSignals(True)
        self.host_filter_combo.clear()
        self.host_filter_combo.addItem("Tous les équipements")
        
        for host in sorted(hosts):
            self.host_filter_combo.addItem(host)
        
        # Restaurer l'hôte sélectionné si possible
        if current_host != "Tous les équipements" and current_host in hosts:
            index = self.host_filter_combo.findText(current_host)
            if index >= 0:
                self.host_filter_combo.setCurrentIndex(index)
        
        self.host_filter_combo.blockSignals(False)
    
    def filterLogsByHost(self, host: str) -> None:
        """Filtre les logs pour afficher uniquement ceux de l'hôte sélectionné"""
        if host == "Tous les équipements":
            self.log_table.setFilterHost(None)
        else:
            self.log_table.setFilterHost(host)
        
    def clearLogs(self) -> None:
        """Efface tous les logs affichés"""
        reply = QMessageBox.question(
            self, 
            "Effacer les logs",
            "Êtes-vous sûr de vouloir effacer tous les logs?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.log_table.clearTable()
            self.log_table.all_rows = []  # Effacer aussi l'historique
            self.host_log_widget.clearLogs()
            self.addLogMessage("Tous les logs ont été effacés")
    
    def saveLogs(self) -> None:
        """Exporte les logs dans un fichier"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder les logs",
            os.path.join(os.path.expanduser("~"), "syslog_export.txt"),
            "Fichiers texte (*.txt);;Fichiers CSV (*.csv);;Tous les fichiers (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    headers = ["Timestamp", "Source", "Facility", "Severity", "Message"]
                    if file_path.lower().endswith('.csv'):
                        f.write(",".join([f'"{h}"' for h in headers]) + "\n")
                        for row in range(self.log_table.rowCount()):
                            row_data = []
                            for col in range(self.log_table.columnCount()):
                                item = self.log_table.item(row, col)
                                cell_text = item.text() if item else ""
                                escaped_text = cell_text.replace('"', '""')
                                row_data.append(f'"{escaped_text}"')
                            f.write(",".join(row_data) + "\n")
                    else:
                        f.write("\t".join(headers) + "\n")
                        f.write("-" * 100 + "\n")
                        for row in range(self.log_table.rowCount()):
                            row_data = []
                            for col in range(self.log_table.columnCount()):
                                item = self.log_table.item(row, col)
                                row_data.append(item.text() if item else "")
                            f.write("\t".join(row_data) + "\n")
                QMessageBox.information(self, "Export réussi", f"Les données ont été exportées vers {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde: {e}")
                self.addLogMessage(f"Erreur lors de la sauvegarde: {e}", error=True)
        
    def addLogMessage(self, message: str, error: bool = False) -> None:
        """Ajoute un message au journal de l'application"""
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        color = "#e74c3c" if error else "#3498db"  # Rouge ou bleu selon le style global
        msg = f'<span style="color: {color};">{timestamp}{message}</span>'
        self.log_text.append(msg)
        # Assure que le dernier message ajouté est visible
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def resetServerStats(self) -> None:
        """Réinitialise les statistiques du serveur"""
        if self.server:
            self.server.stats.reset()
            self.stats_widget.updateStats(self.server.stats.get_stats_dict())
            self.addLogMessage("Statistiques réinitialisées")
        
    def closeEvent(self, event) -> None:
        """Gère l'événement de fermeture de la fenêtre"""
        try:
            if self.server and self.server.running:
                reply = QMessageBox.question(
                    self, 
                    "Fermeture",
                    "Le serveur est en cours d'exécution. Voulez-vous vraiment quitter?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.server.stop()
                    event.accept()
                else:
                    event.ignore()
            else:
                event.accept()
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture: {e}")
            event.accept()

# Structure de données pour les messages SysLog
@dataclass
class SyslogMessage:
    timestamp: str
    source: str
    facility: int
    severity: int
    message: str
    raw: str

# --- Point d'entrée de l'application ---
def main() -> None:
    app = QApplication(sys.argv)
    
    # Configuration de l'application
    app.setApplicationName("SyslogServer")
    app.setApplicationVersion(APP_VERSION)
    
    # Configuration du style global de l'application
    app.setStyle("Fusion")  # Style moderne et cohérent sur toutes les plateformes
    
    # Création et affichage de la fenêtre principale
    window = SyslogServerGUI()
    window.show()
    
    # Exécution de la boucle d'événements
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()