import os
import sys
import platform
import ipaddress
import subprocess
import logging
import socket
import netifaces
import threading
import queue
import time
import json
import pickle
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Tuple 

# Imports pour PyQt5
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QGraphicsView, QGraphicsScene, QMenu, QMessageBox, QComboBox,
    QGraphicsObject, QInputDialog, QFileDialog, QGraphicsLineItem, QGraphicsTextItem, 
    QGraphicsDropShadowEffect, QToolBar, QAction, QLabel, QProgressBar, QTableWidget, QTableWidgetItem,
    QHeaderView, QColorDialog, QGroupBox, QFormLayout, QDialog, QCheckBox, QTextEdit,
    QFrame, QStyle, QApplication
)
from PyQt5.QtGui import (
    QBrush, QPen, QColor, QFont, QPainter, QPixmap, QLinearGradient,
    QIcon, QCursor
)
from PyQt5.QtCore import (
    QTimer, QRectF, Qt, pyqtSignal, QObject, QRunnable, QThreadPool, QLineF,
    QPropertyAnimation, QPointF, QVariantAnimation, QEasingCurve, QEvent
)
from PyQt5.QtWidgets import QGraphicsItem

##############################################
# Import des workers optimisés
##############################################
try:
    from worker.supervision_worker import (
        ping, PingWorker, PingWorkerSignals, 
        NetworkDiscoveryWorker, NetworkDiscoveryWorkerSignals,
        ScanNetworkWorker, ScanNetworkWorkerSignals
    )
except ImportError:
    # Fallback si le fichier worker n'existe pas
    def ping(ip, timeout=2):
        try:
            start_time = time.perf_counter()
            if platform.system().lower() == "windows":
                result = subprocess.run(["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 1)
            else:
                result = subprocess.run(["ping", "-c", "1", "-W", str(timeout), ip],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout + 1)
            latency = (time.perf_counter() - start_time) * 1000
            return (result.returncode == 0), latency
        except Exception as e:
            return False, 0

##############################################
# Classe personnalisée pour le QComboBox
##############################################
class CustomComboBox(QComboBox):
    popupVisible = pyqtSignal(bool)
    
    def showPopup(self):
        self.popupVisible.emit(True)
        super().showPopup()
    
    def hidePopup(self):
        self.popupVisible.emit(False)
        super().hidePopup()

##############################################
# Configuration du Logger
##############################################
def setup_logger():
    logger = logging.getLogger("SupervisionApp")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # Handler console
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # Handler fichier
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        date_str = datetime.now().strftime("%Y-%m-%d")
        fh = logging.FileHandler(f"{log_dir}/app_{date_str}.log")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger

logger = setup_logger()

##############################################
# Fonctions Utilitaires
##############################################
def validate_ip(ip):
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_name(name):
    return name.strip() != "" and all(c.isalnum() or c in ("-", "_", " ", ".") for c in name)

def get_local_ip_ranges():
    ip_ranges = []
    try:
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    if 'addr' in addr and 'netmask' in addr:
                        ip = addr['addr']
                        mask = addr['netmask']
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                            ip_ranges.append(str(network))
                        except Exception as e:
                            logger.error(f"Erreur création réseau CIDR: {e}")
    except Exception as e:
        logger.error(f"Erreur récupération interfaces: {e}")
    return ip_ranges

##############################################
# Gestion du cache pour les pings
##############################################
class PingCacheManager:
    def __init__(self, cache_ttl=60):
        self.cache = {}
        self.cache_ttl = cache_ttl

    def get(self, ip):
        if ip in self.cache:
            timestamp, result = self.cache[ip]
            if (time.time() - timestamp) < self.cache_ttl:
                return result
        return None

    def set(self, ip, result):
        self.cache[ip] = (time.time(), result)

##############################################
# Workers locaux (fallback)
##############################################
class PingWorkerSignals(QObject):
    finished = pyqtSignal(object, bool, float)

class PingWorker(QRunnable):
    def __init__(self, equipment_item, supervision_widget, timeout=1):
        super().__init__()
        self.equipment_item = equipment_item
        self.supervision_widget = supervision_widget
        self.timeout = timeout
        self.signals = PingWorkerSignals()

    def run(self):
        try:
            cached = self.supervision_widget.ping_cache.get(self.equipment_item.ip)
            if cached is not None:
                self.signals.finished.emit(self.equipment_item, cached[0], cached[1])
                return
            status, latency = ping(self.equipment_item.ip, self.timeout)
            self.supervision_widget.ping_cache.set(self.equipment_item.ip, (status, latency))
            self.signals.finished.emit(self.equipment_item, status, latency)
        except Exception as e:
            logger.error(f"Erreur dans PingWorker: {e}")
            self.signals.finished.emit(self.equipment_item, False, 0)

##############################################
# StatusBlockEnhanced
##############################################
class StatusBlockEnhanced(QGraphicsObject):
    def __init__(self, width=200, height=150, parent=None):
        super().__init__(parent)
        self.width = width
        self.height = height
        self.active = 0
        self.inactive = 0
        self.warning = 0
        self.critical = 0
        self.total_items = 0
        self.last_update = datetime.now()
        self.setFlags(self.ItemIsMovable | self.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.boundingRect()
        
        # Couleur de fond selon le statut
        if self.inactive > 0 or self.warning > 0 or self.critical > 0:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(231, 76, 60, 220))
            gradient.setColorAt(1, QColor(192, 57, 43, 220))
        else:
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0, QColor(46, 204, 113, 220))
            gradient.setColorAt(1, QColor(39, 174, 96, 220))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        
        # Bordure
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.drawRoundedRect(rect, 10, 10)
        
        # Titre
        title_rect = QRectF(5, 5, self.width - 10, 30)
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 12, QFont.Bold))  # Remplacé Segoe UI par Arial
        painter.drawText(title_rect, Qt.AlignCenter, "Statut Réseau")
        
        # Ligne de séparation
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1))
        painter.drawLine(10, 35, self.width - 10, 35)
        
        # Statistiques
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 9))  # Remplacé Segoe UI par Arial
        y_offset = 50
        painter.drawText(QRectF(10, y_offset, self.width-20, 20), Qt.AlignLeft, f"🟢 Actifs: {self.active}")
        painter.drawText(QRectF(10, y_offset + 20, self.width-20, 20), Qt.AlignLeft, f"🔴 Inactifs: {self.inactive}")
        painter.drawText(QRectF(10, y_offset + 40, self.width-20, 20), Qt.AlignLeft, f"⚠️ Alertes: {self.warning}")
        painter.drawText(QRectF(10, y_offset + 60, self.width-20, 20), Qt.AlignLeft, f"❗ Critiques: {self.critical}")
        
        # Dernière mise à jour
        update_rect = QRectF(5, self.height - 25, self.width - 10, 20)
        painter.setFont(QFont("Arial", 8))  # Remplacé Segoe UI par Arial
        painter.setPen(QColor(255, 255, 255, 150))
        update_text = f"Màj: {self.last_update.strftime('%H:%M:%S')}"
        painter.drawText(update_rect, Qt.AlignRight, update_text)

    def setStatus(self, active, inactive, warning=0, critical=0):
        self.active = active
        self.inactive = inactive
        self.warning = warning
        self.critical = critical
        self.total_items = active + inactive + warning + critical
        self.last_update = datetime.now()
        self.update()

##############################################
# ConnectionLine
##############################################
class ConnectionLine(QGraphicsLineItem):
    def __init__(self, start_item, end_item, parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.id = f"{id(self)}"
        self.is_active = True
        self.line_width = 3  # Augmenté pour meilleure visibilité
        self.line_color = QColor("#3498db")  # Couleur par défaut bleu
        self.line_style = Qt.DashLine
        self.pen = QPen(self.line_color, self.line_width, self.line_style)
        self.setPen(self.pen)
        self.setZValue(-1)
        self.update_position()
        self.update_status()  # Initialiser le statut visuel

    def update_position(self):
        try:
            start_center = self.start_item.sceneBoundingRect().center()
            end_center = self.end_item.sceneBoundingRect().center()
            new_line = QLineF(start_center, end_center)
            self.prepareGeometryChange()
            self.setLine(new_line)
        except Exception as e:
            logger.error(f"Erreur mise à jour position ligne: {e}")
    
    def update_status(self):
        """Met à jour l'apparence de la ligne selon l'état des équipements connectés"""
        try:
            # Vérifier si les deux équipements sont actifs
            if self.start_item.reachable and self.end_item.reachable:
                # Les deux sont joignables - ligne verte vive
                self.line_color = QColor("#00cc00")  # Vert vif
                self.is_active = True
            else:
                # Au moins un n'est pas joignable - ligne rouge vive
                self.line_color = QColor("#ff0000")  # Rouge vif
                self.is_active = False
            
            # Motif de pointillés plus prononcé et visible
            dash_pattern = [8, 4]  # 8px de ligne, 4px d'espace
            pen = QPen(self.line_color, self.line_width, Qt.CustomDashLine)
            pen.setDashPattern(dash_pattern)
            pen.setCapStyle(Qt.RoundCap)  # Extrémités arrondies pour un meilleur rendu
            self.setPen(pen)
        except Exception as e:
            logger.error(f"Erreur mise à jour statut ligne: {e}")
            # Appliquer un style par défaut en cas d'erreur
            self.setPen(QPen(QColor("#3498db"), self.line_width, Qt.DashLine))

    def get_save_data(self):
        return {
            'id': self.id,
            'start_item_id': self.start_item.id,
            'end_item_id': self.end_item.id,
            'line_width': self.line_width,
            'line_color': self.line_color.name(),
            'line_style': self.line_style,
            'is_active': self.is_active
        }

##############################################
# PulseEffect et BlinkEffect
##############################################
class PulseEffect(QVariantAnimation):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target
        self.setStartValue(0.8)
        self.setEndValue(1.0)
        self.setDuration(800)
        self.setLoopCount(-1)
        self.setEasingCurve(QEasingCurve.InOutQuad)
        self.valueChanged.connect(self.update_effect)
        
    def update_effect(self, value):
        if self.target and self.target.scene() is not None:
            self.target.setScale(value)

class BlinkEffect(QVariantAnimation):
    def __init__(self, target, parent=None):
        super().__init__(parent)
        self.target = target
        self.setStartValue(0.4)
        self.setEndValue(1.0)
        self.setDuration(500)
        self.setLoopCount(-1)
        self.valueChanged.connect(self.update_effect)
        
    def update_effect(self, value):
        if self.target and self.target.scene() is not None:
            self.target.setOpacity(value)

##############################################
# EquipmentItem Amélioré
##############################################
class EquipmentItem(QGraphicsObject):
    removed = pyqtSignal(object)
    connectionClicked = pyqtSignal(object)
    statusChanged = pyqtSignal(object, bool)
    doubleClicked = pyqtSignal(object)

    def __init__(self, name, ip, icon_path="resources/map/default_icon.png", width=150, height=150, parent=None, eq_id=None):
        super().__init__(parent)
        self.name = name
        self.ip = ip
        self.width = width
        self.height = height
        self.reachable = False
        self.ping_history = []
        self.ping_latency = []
        self.critical = False
        self.warning = False
        self.notes = ""
        self.detailed_info = {}
        self.last_state_change = datetime.now()
        self.uptime = 0
        self.downtime = 0
        self.custom_color = None
        self.icon_path = icon_path
        self.id = eq_id if eq_id is not None else f"{id(self)}"
        self.setFlags(self.ItemIsMovable | self.ItemIsSelectable | self.ItemSendsScenePositionChanges)
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        
        # Chargement sécurisé de l'icône
        self.load_icon(icon_path)
        
        self.add_shadow()
        self.blink_effect = BlinkEffect(self)
        self.pulse_effect = PulseEffect(self)
        self.animation_active = False
        self.setAcceptHoverEvents(True)

    def load_icon(self, icon_path):
        """Charge l'icône de manière sécurisée"""
        try:
            if icon_path and os.path.exists(icon_path):
                self.pixmap = QPixmap(icon_path)
                if self.pixmap.isNull():
                    logger.warning(f"Impossible de charger l'icône: {icon_path}")
                    self.create_default_icon()
            else:
                # Essayer le chemin par défaut
                default_path = os.path.join(os.path.dirname(__file__), "..", "resources", "map", "default_icon.png")
                if os.path.exists(default_path):
                    self.pixmap = QPixmap(default_path)
                    if self.pixmap.isNull():
                        self.create_default_icon()
                else:
                    self.create_default_icon()
        except Exception as e:
            logger.error(f"Erreur lors du chargement de l'icône {icon_path}: {e}")
            self.create_default_icon()

    def create_default_icon(self):
        """Crée une icône par défaut si aucune n'est disponible"""
        self.pixmap = QPixmap(64, 64)
        self.pixmap.fill(QColor("#3498db"))

    def add_shadow(self):
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(15)
            shadow.setOffset(3, 3)
            shadow.setColor(QColor(0, 0, 0, 120))
            self.setGraphicsEffect(shadow)
        except Exception as e:
            logger.warning(f"Impossible d'ajouter l'ombre: {e}")

    def boundingRect(self):
        return QRectF(-5, -5, self.width + 10, self.height + 10)

    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing, True)
        base_rect = QRectF(0, 0, self.width, self.height)
        
        # Gradient de fond selon l'état
        if not self.reachable:
            gradient = QLinearGradient(0, 0, 0, self.height)
            gradient.setColorAt(0, QColor(231, 76, 60, 220))
            gradient.setColorAt(1, QColor(192, 57, 43, 220))
        elif self.isSelected():
            gradient = QLinearGradient(0, 0, 0, self.height)
            gradient.setColorAt(0, QColor(52, 152, 219, 200))
            gradient.setColorAt(1, QColor(41, 128, 185, 200))
        else:
            gradient = QLinearGradient(0, 0, 0, self.height)
            if self.custom_color:
                gradient.setColorAt(0, QColor(self.custom_color.red(), self.custom_color.green(), self.custom_color.blue(), 180))
                gradient.setColorAt(1, QColor(int(self.custom_color.red()*0.8), int(self.custom_color.green()*0.8), int(self.custom_color.blue()*0.8), 180))
            else:
                gradient.setColorAt(0, QColor(46, 204, 113, 180))
                gradient.setColorAt(1, QColor(39, 174, 96, 180))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(base_rect, 10, 10)
        
        # Bordure de sélection
        if self.isSelected():
            painter.setPen(QPen(QColor("#f1c40f"), 2, Qt.SolidLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(base_rect, 10, 10)
        
        # Icône
        icon_rect = QRectF(10, 10, self.width - 20, 80)
        if not self.pixmap.isNull():
            scaled = self.pixmap.scaled(int(icon_rect.width()), int(icon_rect.height()),
                                        Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width - scaled.width()) / 2
            painter.drawPixmap(int(x), 10, scaled)
        
        # Nom
        text_rect = QRectF(5, 90, self.width - 10, 30)
        painter.setPen(QColor(0, 0, 0, 100))
        painter.setFont(QFont("Arial", 10, QFont.Bold))  # Remplacé Segoe UI par Arial
        painter.drawText(text_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, self.name)
        painter.setPen(Qt.white)
        painter.drawText(text_rect, Qt.AlignCenter, self.name)
        
        # IP
        ip_rect = QRectF(5, 110, self.width - 10, 20)
        painter.setFont(QFont("Arial", 8))  # Remplacé Segoe UI par Arial
        painter.drawText(ip_rect, Qt.AlignCenter, self.ip)
        
        # Statut
        status_rect = QRectF(0, 130, self.width, 20)
        if not self.reachable:
            status_text = "Hors ligne"
            status_icon = "❌"
        elif self.critical:
            status_text = "CRITIQUE"
            status_icon = "❗"
        elif self.warning:
            status_text = "ALERTE"
            status_icon = "⚠️"
        else:
            status_text = "En ligne"
            status_icon = "✅"
        
        painter.setPen(QColor(0, 0, 0, 100))
        painter.setFont(QFont("Arial", 12, QFont.Bold))  # Remplacé Segoe UI par Arial
        painter.drawText(status_rect.adjusted(1, 1, 1, 1), Qt.AlignCenter, f"{status_icon} {status_text}")
        
        status_color = QColor("#e74c3c") if not self.reachable else QColor("#2ecc71")
        painter.setPen(status_color)
        painter.drawText(status_rect, Qt.AlignCenter, f"{status_icon} {status_text}")

    def update_status(self, reachable):
        self.reachable = reachable
        self.ping_history.append((datetime.now(), reachable))
        self.last_state_change = datetime.now()
        
        # Animation
        try:
            self.animation = QPropertyAnimation(self, b"opacity")
            self.animation.setDuration(500)
            self.animation.setStartValue(0.5)
            self.animation.setEndValue(1.0)
            self.animation.start()
            
            if not reachable:
                self.blink_effect.start()
            else:
                self.blink_effect.stop()
                self.setOpacity(1.0)
        except Exception as e:
            logger.warning(f"Erreur animation: {e}")
        
        self.update()

    def mousePressEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.connectionClicked.emit(self)
            event.accept()
        else:
            super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """Menu contextuel sécurisé - sans ping ni changement de couleur"""
        try:
            menu = QMenu()
            
            # Actions principales
            details_action = menu.addAction("📊 Afficher les détails")
            details_action.triggered.connect(self.show_details_safe)
            
            history_action = menu.addAction("📈 Historique")
            history_action.triggered.connect(self.show_ping_history_safe)
            
            menu.addSeparator()
            
            # Actions de modification
            rename_action = menu.addAction("✏️ Renommer")
            rename_action.triggered.connect(self.rename_equipment_safe)
            
            change_icon_action = menu.addAction("🎨 Changer l'icône")
            change_icon_action.triggered.connect(self.change_icon_from_menu_safe)
            
            menu.addSeparator()
            
            # Actions dangereuses
            delete_action = menu.addAction("🗑️ Supprimer")
            delete_action.triggered.connect(self.remove_equipment_safe)
            
            # Styles pour le menu
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2c3e50;
                    border: 1px solid #3498db;
                    border-radius: 6px;
                    padding: 4px;
                }
                QMenu::item {
                    background-color: transparent;
                    padding: 8px 16px;
                    border-radius: 4px;
                    color: #ecf0f1;
                }
                QMenu::item:selected {
                    background-color: #3498db;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #34495e;
                    margin: 4px 8px;
                }
            """)
            
            menu.exec_(event.screenPos())
            
        except Exception as e:
            logger.error(f"Erreur menu contextuel: {e}")
            QMessageBox.critical(None, "Erreur", f"Erreur menu: {str(e)}")

    def show_details_safe(self):
        try:
            self.show_details()
        except Exception as e:
            logger.error(f"Erreur affichage détails: {e}")
            QMessageBox.warning(None, "Erreur", f"Impossible d'afficher les détails: {str(e)}")

    def show_ping_history_safe(self):
        try:
            if not self.ping_history:
                QMessageBox.information(None, "Historique", "Aucun historique disponible.")
                return
            
            dialog = QDialog()
            dialog.setWindowTitle(f"Historique - {self.name}")
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            
            table = QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Heure", "Statut", "Latence (ms)"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            
            table.setRowCount(len(self.ping_history))
            for i, (timestamp, status) in enumerate(self.ping_history):
                table.setItem(i, 0, QTableWidgetItem(timestamp.strftime("%H:%M:%S")))
                status_item = QTableWidgetItem("En ligne" if status else "Hors ligne")
                status_item.setForeground(QBrush(QColor("#2ecc71" if status else "#e74c3c")))
                table.setItem(i, 1, status_item)
                
                latency = ""
                if i < len(self.ping_latency) and status:
                    latency = f"{self.ping_latency[i]:.2f}"
                table.setItem(i, 2, QTableWidgetItem(latency))
            
            layout.addWidget(table)
            
            close_btn = QPushButton("Fermer")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Erreur historique: {e}")
            QMessageBox.warning(None, "Erreur", f"Impossible d'afficher l'historique: {str(e)}")

    def rename_equipment_safe(self):
        try:
            new_name, ok = QInputDialog.getText(None, "Renommer", "Nouveau nom :", text=self.name)
            if ok and new_name.strip():
                self.name = new_name.strip()
                self.update()
                logger.info(f"Équipement renommé en : {self.name}")
        except Exception as e:
            logger.error(f"Erreur renommage: {e}")
            QMessageBox.warning(None, "Erreur", f"Impossible de renommer: {str(e)}")

    def change_icon_from_menu_safe(self):
        try:
            scene_views = self.scene().views()
            if scene_views:
                view = scene_views[0]
                supervision_widget = view.parent()
                if hasattr(supervision_widget, 'change_equipment_icon'):
                    supervision_widget.change_equipment_icon(self)
        except Exception as e:
            logger.error(f"Erreur changement icône: {e}")
            QMessageBox.warning(None, "Erreur", f"Impossible de changer l'icône: {str(e)}")

    def remove_equipment_safe(self):
        """Suppression sécurisée de l'équipement - compatible avec ModernMessageBox"""
        try:
            # Utiliser une approche simple sans arguments optionnels
            message_box = QMessageBox()
            message_box.setWindowTitle("Confirmer")
            message_box.setText(f"Supprimer '{self.name}' ?")
            message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            message_box.setDefaultButton(QMessageBox.No)
            message_box.setIcon(QMessageBox.Question)
            
            reply = message_box.exec_()
            
            if reply == QMessageBox.Yes:
                logger.info(f"Suppression de l'équipement confirmée: {self.name}")
                # Émettre le signal removed pour que le SupervisionWidget puisse gérer la suppression
                self.removed.emit(self)
        except Exception as e:
            logger.error(f"Erreur suppression: {e}")
            QMessageBox.warning(None, "Erreur", f"Impossible de supprimer: {str(e)}")

    def show_details(self):
        try:
            dialog = QDialog()
            dialog.setWindowTitle(f"Détails - {self.name}")
            dialog.resize(500, 400)
            
            layout = QVBoxLayout(dialog)
            
            # Informations
            info_group = QGroupBox("Informations")
            info_layout = QFormLayout(info_group)
            
            name_edit = QLineEdit(self.name)
            ip_edit = QLineEdit(self.ip)
            
            status_text = "🟢 En ligne" if self.reachable else "🔴 Hors ligne"
            status_label = QLabel(status_text)
            
            info_layout.addRow("Nom:", name_edit)
            info_layout.addRow("IP:", ip_edit)
            info_layout.addRow("Statut:", status_label)
            
            layout.addWidget(info_group)
            
            # Notes
            notes_group = QGroupBox("Notes")
            notes_layout = QVBoxLayout(notes_group)
            notes_edit = QTextEdit(self.notes)
            notes_layout.addWidget(notes_edit)
            layout.addWidget(notes_group)
            
            # Boutons
            buttons_layout = QHBoxLayout()
            save_btn = QPushButton("💾 Sauvegarder")
            close_btn = QPushButton("❌ Fermer")
            buttons_layout.addWidget(save_btn)
            buttons_layout.addWidget(close_btn)
            layout.addLayout(buttons_layout)
            
            def save_changes():
                if validate_name(name_edit.text()) and validate_ip(ip_edit.text()):
                    self.name = name_edit.text().strip()
                    self.ip = ip_edit.text().strip()
                    self.notes = notes_edit.toPlainText()
                    self.update()
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "Erreur", "Nom ou IP invalide!")
            
            save_btn.clicked.connect(save_changes)
            close_btn.clicked.connect(dialog.reject)
            
            dialog.exec_()
            
        except Exception as e:
            logger.error(f"Erreur détails: {e}")

    def remove_equipment(self):
        try:
            self.removed.emit(self)
            if self.scene():
                self.scene().removeItem(self)
        except Exception as e:
            logger.error(f"Erreur suppression simple: {e}")

##############################################
# SupervisionWidget (Interface Principale)
##############################################
class SupervisionWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.equipment_items = {}
        self.connection_lines = {}
        self.connection_start_item = None
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(20)
        self.ping_cache = PingCacheManager(cache_ttl=30)
        self.combo_box_active = False
        self.controls_expanded = False
        self.network_scan_worker = None
        
        self.initUI()
        self.setup_timers()
        self.setup_auto_save()

    def setup_timers(self):
        """Configuration des timers"""
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(5000)
        
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.update_connections)
        self.connection_timer.start(200)

    def setup_auto_save(self):
        """Configuration de la sauvegarde automatique"""
        self.auto_save_path = os.path.join(os.path.dirname(__file__), "data", "autosave.netmap")
        os.makedirs(os.path.dirname(self.auto_save_path), exist_ok=True)
        
        if os.path.exists(self.auto_save_path):
            try:
                self.load_map(self.auto_save_path)
            except Exception as e:
                logger.error(f"Erreur chargement sauvegarde: {e}")
        
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.start(60000)

    def initUI(self):
        main_layout = QVBoxLayout(self)
        
        # Contrôles
        self.controls_container = QWidget()
        self.controls_container.setMinimumHeight(30)
        controls_container_layout = QVBoxLayout(self.controls_container)
        controls_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # En-tête
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        self.toggle_label = QLabel("⯆ Panneau de contrôle")
        self.toggle_label.setStyleSheet("""
            QLabel {
                color: #3498db;
                font-weight: bold;
                padding: 5px;
                border-radius: 4px;
                background-color: rgba(52, 152, 219, 0.1);
            }
            QLabel:hover {
                background-color: rgba(52, 152, 219, 0.2);
            }
        """)
        self.toggle_label.setCursor(QCursor(Qt.PointingHandCursor))
        self.toggle_label.mousePressEvent = self.toggle_controls_event
        header_layout.addWidget(self.toggle_label)
        controls_container_layout.addWidget(header_widget)
        
        # Panneau de contrôles
        self.controls_frame = QFrame()
        self.controls_frame.setFrameShape(QFrame.StyledPanel)
        self.controls_frame.setVisible(False)
        self.controls_frame.setMaximumHeight(0)
        controls_layout = QVBoxLayout(self.controls_frame)
        
        # Contrôles d'équipement
        equipment_controls = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nom de l'équipement")
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("IP (ou sous-réseau)")
        self.icon_combo = CustomComboBox()
        self.icon_combo.addItems(["PC", "Routeur", "Switch", "Switch L3", "Firewall", "Default"])
        self.icon_combo.popupVisible.connect(self.on_combo_popup_visible)
        self.icon_combo.currentTextChanged.connect(self.on_icon_selection_changed)
        self.add_button = QPushButton("Ajouter")
        self.add_button.clicked.connect(self.add_equipment)
        self.scan_button = QPushButton("Scanner Réseau")
        self.scan_button.clicked.connect(self.start_network_discovery)
        
        equipment_controls.addWidget(self.name_edit)
        equipment_controls.addWidget(self.ip_edit)
        equipment_controls.addWidget(self.icon_combo)
        equipment_controls.addWidget(self.add_button)
        equipment_controls.addWidget(self.scan_button)
        controls_layout.addLayout(equipment_controls)
        
        # Barre de progression
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("Prêt")
        self.progress_bar.setValue(0)
        self.cancel_scan_button = QPushButton("❌")
        self.cancel_scan_button.setToolTip("Annuler le scan")
        self.cancel_scan_button.setFixedSize(30, 30)
        self.cancel_scan_button.clicked.connect(self.cancel_network_scan)
        self.cancel_scan_button.setVisible(False)
        progress_layout.addWidget(self.progress_bar, 1)
        progress_layout.addWidget(self.cancel_scan_button, 0)
        controls_layout.addLayout(progress_layout)
        
        controls_container_layout.addWidget(self.controls_frame)
        main_layout.addWidget(self.controls_container)
        
        # Scène graphique
        self.scene = QGraphicsScene()
        self.scene.setBackgroundBrush(Qt.transparent)
        self.scene.setSceneRect(0, 0, 800, 600)
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        main_layout.addWidget(self.view)
        
        # Bloc de statut
        self.status_block = StatusBlockEnhanced(width=200, height=150)
        self.scene.addItem(self.status_block)
        self.status_block.setPos(580, 10)
        
        # Mouse tracking
        self.controls_container.setMouseTracking(True)
        self.controls_container.enterEvent = self.controls_hover_enter
        self.controls_container.leaveEvent = self.controls_hover_leave

    def on_combo_popup_visible(self, visible):
        self.combo_box_active = visible

    def controls_hover_enter(self, event):
        if not self.controls_expanded:
            self.toggle_controls(True)

    def controls_hover_leave(self, event):
        QTimer.singleShot(300, self.check_controls_leave)

    def check_controls_leave(self):
        if (self.controls_container.underMouse() or 
            self.icon_combo.underMouse() or 
            self.combo_box_active):
            return
        if self.controls_expanded:
            self.toggle_controls(False)

    def toggle_controls_event(self, event):
        self.toggle_controls()

    def toggle_controls(self, expand=None):
        target_expanded = expand if expand is not None else not self.controls_expanded
        
        try:
            self.controls_animation = QPropertyAnimation(self.controls_frame, b"maximumHeight")
            self.controls_animation.setDuration(250)
            self.controls_animation.setEasingCurve(QEasingCurve.OutCubic)
            
            if not target_expanded:
                self.controls_animation.setStartValue(self.controls_frame.height())
                self.controls_animation.setEndValue(0)
                self.controls_animation.finished.connect(lambda: self.controls_frame.setVisible(False))
                self.toggle_label.setText("⯆ Panneau de contrôle")
                self.controls_expanded = False
            else:
                self.controls_frame.setVisible(True)
                original_height = self.controls_frame.sizeHint().height()
                self.controls_animation.setStartValue(0)
                self.controls_animation.setEndValue(original_height)
                self.toggle_label.setText("⯅ Panneau de contrôle")
                self.controls_expanded = True
                
            self.controls_animation.start()
        except Exception as e:
            logger.error(f"Erreur animation contrôles: {e}")

    def on_icon_selection_changed(self, icon_text):
        logger.debug(f"Icône sélectionnée : {icon_text}")

    def get_icon_path(self, icon_choice):
        """Retourne le chemin vers l'icône sélectionnée"""
        base_path = os.path.join(os.path.dirname(__file__), "..", "resources", "map")
        
        icon_mapping = {
            "PC": "pc_icon.png",
            "Routeur": "routeur.png", 
            "Switch": "switch.png",
            "Switch L3": "SW3.png",
            "Firewall": "firewall.png",
            "Default": "default_icon.png"
        }
        
        icon_filename = icon_mapping.get(icon_choice, "default_icon.png")
        icon_path = os.path.join(base_path, icon_filename)
        
        if not os.path.exists(icon_path):
            logger.warning(f"Icône introuvable : {icon_path}")
            icon_path = os.path.join(base_path, "default_icon.png")
            
        return icon_path

    def add_equipment(self):
        try:
            name = self.name_edit.text().strip()
            ip = self.ip_edit.text().strip()
            icon_choice = self.icon_combo.currentText()
            
            if not validate_name(name):
                QMessageBox.critical(self, "Erreur", "Nom invalide.")
                return
            if not validate_ip(ip):
                QMessageBox.critical(self, "Erreur", "IP invalide.")
                return
            
            icon_path = self.get_icon_path(icon_choice)
            
            equipment = EquipmentItem(name, ip, icon_path)
            equipment.connectionClicked.connect(self.on_equipment_connection_clicked)
            equipment.removed.connect(self.remove_equipment)
            equipment.statusChanged.connect(self.update_status_text)
            equipment.doubleClicked.connect(self.show_equipment_details)
            
            # Position au centre
            scene_rect = self.scene.sceneRect()
            x = (scene_rect.width() - equipment.width) / 2
            y = (scene_rect.height() - equipment.height) / 2
            equipment.setPos(x, y)
            
            self.scene.addItem(equipment)
            self.equipment_items[equipment.id] = equipment
            
            # Reset des champs
            self.name_edit.clear()
            self.ip_edit.clear()
            self.icon_combo.setCurrentText("Default")
            
            self.update_status_text()
            self.ping_equipment(equipment)
            self.auto_save()
            
            logger.info(f"Équipement ajouté : {name} ({ip})")
            
        except Exception as e:
            logger.error(f"Erreur ajout équipement: {e}")
            QMessageBox.critical(self, "Erreur", f"Impossible d'ajouter l'équipement: {str(e)}")

    def ping_equipment(self, equipment):
        """Lance un ping pour un équipement"""
        try:
            worker = PingWorker(equipment, self)
            worker.signals.finished.connect(self.on_ping_finished)
            self.threadpool.start(worker)
        except Exception as e:
            logger.error(f"Erreur ping équipement: {e}")

    def on_ping_finished(self, equipment, status, latency):
        """Callback après ping"""
        try:
            equipment.update_status(status)
            if status and latency:
                equipment.ping_latency.append(latency)
                if len(equipment.ping_latency) > 10:
                    equipment.ping_latency.pop(0)
            self.update_status_text()
            self.update_connection_status(equipment)  # Mise à jour des connexions de cet équipement
        except Exception as e:
            logger.error(f"Erreur callback ping: {e}")

    def update_connection_status(self, equipment):
        """Met à jour le statut visuel des connexions liées à un équipement"""
        try:
            # Parcourir toutes les connexions pour trouver celles liées à cet équipement
            for line in self.connection_lines.values():
                if line.start_item == equipment or line.end_item == equipment:
                    # Mettre à jour le statut visuel de la ligne
                    line.update_status()
        except Exception as e:
            logger.error(f"Erreur mise à jour statut connexions: {e}")

    def refresh_status(self):
        """Actualise le statut de tous les équipements"""
        try:
            for equipment in list(self.equipment_items.values()):
                self.ping_equipment(equipment)
        except Exception as e:
            logger.error(f"Erreur refresh statut: {e}")

    def update_status_text(self):
        """Met à jour le bloc de statut"""
        try:
            active = sum(1 for e in self.equipment_items.values() if e.reachable)
            inactive = sum(1 for e in self.equipment_items.values() if not e.reachable)
            self.status_block.setStatus(active, inactive, 0, 0)
            
            if not (self.progress_bar.text() == "Scan en cours..." or 
                   self.progress_bar.text().startswith("Scan: ")):
                self.progress_bar.setFormat(f"Màj: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            logger.error(f"Erreur mise à jour statut: {e}")

    def remove_equipment(self, equipment):
        """Supprime un équipement - corrigée pour éviter les bugs"""
        try:
            if equipment is None:
                logger.error("Tentative de suppression d'un équipement null")
                return
                
            if equipment.id in self.equipment_items:
                logger.info(f"Début de suppression de l'équipement {equipment.name} (ID: {equipment.id})")
                
                # 1. Supprimer les connexions associées
                lines_to_remove = []
                for line_id, line in list(self.connection_lines.items()):
                    try:
                        if (line.start_item == equipment or line.end_item == equipment):
                            logger.debug(f"Suppression connexion {line_id}")
                            if line.scene() is not None:
                                self.scene.removeItem(line)
                            lines_to_remove.append(line_id)
                    except Exception as e:
                        logger.warning(f"Erreur lors de la suppression de ligne {line_id}: {e}")
                        lines_to_remove.append(line_id)
                
                # 2. Nettoyer les références aux lignes
                for line_id in lines_to_remove:
                    if line_id in self.connection_lines:
                        del self.connection_lines[line_id]
                
                # 3. Supprimer l'équipement de la scène
                try:
                    if equipment.scene() is not None:
                        self.scene.removeItem(equipment)
                except Exception as e:
                    logger.error(f"Erreur suppression de la scène: {e}")
                
                # 4. Supprimer de notre dictionnaire 
                if equipment.id in self.equipment_items:
                    del self.equipment_items[equipment.id]
                
                # 5. Mettre à jour l'interface
                self.update_status_text()
                self.auto_save()
                
                logger.info(f"Équipement supprimé avec succès: {equipment.name}")
            else:
                logger.warning(f"Tentative de suppression d'un équipement non référencé: {equipment.id}")
                
        except Exception as e:
            logger.error(f"Erreur critique suppression équipement: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la suppression: {str(e)}")

    def on_equipment_connection_clicked(self, equipment):
        """Gère les clics pour créer des connexions"""
        try:
            if self.connection_start_item is None:
                self.connection_start_item = equipment
                equipment.setOpacity(0.7)
                logger.info(f"Point de départ : {equipment.name}")
            else:
                if equipment == self.connection_start_item:
                    self.connection_start_item.setOpacity(1.0)
                    self.connection_start_item = None
                    logger.info("Connexion annulée")
                    return
                
                connection_line = ConnectionLine(self.connection_start_item, equipment)
                self.scene.addItem(connection_line)
                self.connection_lines[connection_line.id] = connection_line
                
                logger.info(f"Connexion créée : {self.connection_start_item.name} - {equipment.name}")
                
                self.connection_start_item.setOpacity(1.0)
                self.connection_start_item = None
                self.auto_save()
                
        except Exception as e:
            logger.error(f"Erreur connexion: {e}")

    def update_connections(self):
        """Met à jour les positions des connexions"""
        try:
            for line in list(self.connection_lines.values()):
                if not line.scene():
                    if line.id in self.connection_lines:
                        del self.connection_lines[line.id]
                else:
                    line.update_position()
        except Exception as e:
            logger.error(f"Erreur mise à jour connexions: {e}")

    def change_equipment_icon(self, equipment):
        """Change l'icône d'un équipement"""
        try:
            icons = ["PC", "Routeur", "Switch", "Switch L3",  "Firewall", "Default"]
            current_icon = "Default"
            
            # Déterminer l'icône actuelle
            for icon_name, filename in [("PC", "pc_icon.png"), ("Routeur", "routeur.png"), 
                                       ("Switch", "switch.png"),("Firewall", "firewall.png"),]:
                if filename in equipment.icon_path:
                    current_icon = icon_name
                    break
            
            current_index = icons.index(current_icon) if current_icon in icons else 0
            
            icon, ok = QInputDialog.getItem(self, "Changer l'icône", "Choisir :", 
                                           icons, current_index, False)
            
            if ok and icon:
                new_icon_path = self.get_icon_path(icon)
                equipment.icon_path = new_icon_path
                equipment.load_icon(new_icon_path)
                equipment.update()
                self.auto_save()
                logger.info(f"Icône changée : {equipment.name} -> {icon}")
                
        except Exception as e:
            logger.error(f"Erreur changement icône: {e}")
            QMessageBox.warning(self, "Erreur", f"Impossible de changer l'icône: {str(e)}")

    def show_equipment_details(self, equipment):
        """Affiche les détails d'un équipement"""
        try:
            equipment.show_details()
        except Exception as e:
            logger.error(f"Erreur affichage détails: {e}")

    def start_network_discovery(self):
        """Lance la découverte réseau"""
        try:
            subnet = self.ip_edit.text().strip() or "192.168.1.0/24"
            
            # Utiliser le worker du fichier externe si disponible
            try:
                from worker.supervision_worker import NetworkDiscoveryWorker
                self.network_scan_worker = NetworkDiscoveryWorker(subnet)
                
                # Connecter les signaux
                self.network_scan_worker.signals.discovered.connect(self.on_device_discovered)
                self.network_scan_worker.signals.progress.connect(self.on_scan_progress)
                self.network_scan_worker.signals.finished.connect(self.on_scan_finished)
                
            except ImportError:
                # Fallback local simplifié
                QMessageBox.warning(self, "Erreur", "Module de scan non disponible")
                return
            
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Scan en cours...")
            self.cancel_scan_button.setVisible(True)
            self.scan_button.setEnabled(False)
            
            # Démarrer le worker
            self.threadpool.start(self.network_scan_worker)
            logger.info(f"Scan réseau lancé : {subnet}")
            
        except Exception as e:
            logger.error(f"Erreur scan réseau: {e}")
            QMessageBox.critical(self, "Erreur", f"Impossible de lancer le scan: {str(e)}")

    def on_device_discovered(self, ip):
        """Callback quand un appareil est découvert"""
        try:
            logger.info(f"Appareil découvert: {ip}")
            
            # Vérifier si l'IP existe déjà
            for equipment in self.equipment_items.values():
                if equipment.ip == ip:
                    logger.debug(f"IP {ip} déjà présente, ignorée")
                    return
            
            # Créer automatiquement l'équipement
            name = f"Device_{ip.split('.')[-1]}"
            icon_path = self.get_icon_path("Default")
            
            equipment = EquipmentItem(name, ip, icon_path)
            equipment.connectionClicked.connect(self.on_equipment_connection_clicked)
            equipment.removed.connect(self.remove_equipment)
            equipment.statusChanged.connect(self.update_status_text)
            equipment.doubleClicked.connect(self.show_equipment_details)
            
            # Position aléatoire pour éviter les superpositions
            import random
            scene_rect = self.scene.sceneRect()
            x = random.randint(50, int(scene_rect.width() - equipment.width - 50))
            y = random.randint(50, int(scene_rect.height() - equipment.height - 50))
            equipment.setPos(x, y)
            
            self.scene.addItem(equipment)
            self.equipment_items[equipment.id] = equipment
            
            # Lancer un ping immédiat
            self.ping_equipment(equipment)
            
        except Exception as e:
            logger.error(f"Erreur ajout appareil découvert: {e}")

    def on_scan_progress(self, current, total):
        """Callback de progression du scan"""
        try:
            if total > 0:
                percentage = int((current / total) * 100)
                self.progress_bar.setValue(percentage)
                self.progress_bar.setFormat(f"Scan: {current}/{total} ({percentage}%)")
        except Exception as e:
            logger.error(f"Erreur mise à jour progression: {e}")

    def on_scan_finished(self):
        """Callback de fin de scan"""
        try:
            self.progress_bar.setValue(100)
            self.progress_bar.setFormat("Scan terminé")
            self.cancel_scan_button.setVisible(False)
            self.scan_button.setEnabled(True)
            self.network_scan_worker = None
            
            # Mettre à jour les statuts et sauvegarder
            self.update_status_text()
            self.auto_save()
            
            # Réinitialiser après 3 secondes
            QTimer.singleShot(3000, lambda: self.progress_bar.setFormat("Prêt"))
            
            discovered_count = len([eq for eq in self.equipment_items.values()])
            logger.info(f"Scan terminé. {discovered_count} équipements au total.")
            
        except Exception as e:
            logger.error(f"Erreur fin de scan: {e}")

    def cancel_network_scan(self):
        """Annule le scan réseau"""
        try:
            if self.network_scan_worker and hasattr(self.network_scan_worker, 'stop'):
                self.network_scan_worker.stop()
            
            self.network_scan_worker = None
            self.progress_bar.setValue(0)
            self.progress_bar.setFormat("Scan annulé")
            self.cancel_scan_button.setVisible(False)
            self.scan_button.setEnabled(True)
            
            QTimer.singleShot(2000, lambda: self.progress_bar.setFormat("Prêt"))
            logger.info("Scan annulé")
            
        except Exception as e:
            logger.error(f"Erreur annulation scan: {e}")

    def auto_save(self):
        """Sauvegarde automatique"""
        try:
            self.save_map(self.auto_save_path)
            logger.debug("Sauvegarde automatique OK")
        except Exception as e:
            logger.error(f"Erreur sauvegarde auto: {e}")

    def save_map(self, file_path):
        """Sauvegarde la carte"""
        try:
            save_data = {"equipment": {}, "connections": {}}
            
            for eq_id, eq in self.equipment_items.items():
                save_data["equipment"][eq_id] = {
                    "name": eq.name,
                    "ip": eq.ip,
                    "icon_path": eq.icon_path,
                    "pos_x": eq.pos().x(),
                    "pos_y": eq.pos().y(),
                    "notes": eq.notes,
                    "custom_color": eq.custom_color.name() if eq.custom_color else None
                }
            
            for line_id, line in self.connection_lines.items():
                save_data["connections"][line_id] = line.get_save_data()
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                pickle.dump(save_data, f)
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur sauvegarde: {e}")
            return False

    def load_map(self, file_path):
        """Charge une carte"""
        try:
            if not os.path.exists(file_path):
                return False

            with open(file_path, "rb") as f:
                save_data = pickle.load(f)

            # Nettoyer
            for eq in list(self.equipment_items.values()):
                self.scene.removeItem(eq)
            for line in list(self.connection_lines.values()):
                self.scene.removeItem(line)

            self.equipment_items = {}
            self.connection_lines = {}
            equipment_lookup = {}

            # Charger les équipements
            for eq_id, data in save_data["equipment"].items():
                eq = EquipmentItem(data["name"], data["ip"], data["icon_path"], eq_id=eq_id)
                eq.setPos(data["pos_x"], data["pos_y"])
                eq.notes = data.get("notes", "")
                if data.get("custom_color"):
                    eq.custom_color = QColor(data["custom_color"])
                
                eq.connectionClicked.connect(self.on_equipment_connection_clicked)
                eq.removed.connect(self.remove_equipment)
                eq.statusChanged.connect(self.update_status_text)
                eq.doubleClicked.connect(self.show_equipment_details)
                
                self.scene.addItem(eq)
                self.equipment_items[eq_id] = eq
                equipment_lookup[eq_id] = eq

            # Charger les connexions
            for line_id, data in save_data.get("connections", {}).items():
                start_id = data["start_item_id"]
                end_id = data["end_item_id"]
                if start_id in equipment_lookup and end_id in equipment_lookup:
                    line = ConnectionLine(equipment_lookup[start_id], equipment_lookup[end_id])
                    line.id = line_id
                    self.scene.addItem(line)
                    self.connection_lines[line_id] = line

            self.update_status_text()
            self.refresh_status()
            
            logger.info(f"Carte chargée: {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur chargement: {e}")
            return False

    def keyPressEvent(self, event):
        """Gestion des raccourcis clavier avec boîte de dialogue compatible"""
        try:
            if event.key() == Qt.Key_Delete:
                selected_items = [item for item in self.scene.selectedItems() 
                                if isinstance(item, EquipmentItem)]
                
                if selected_items:
                    # Utiliser une approche simple sans arguments optionnels
                    message_box = QMessageBox()
                    message_box.setWindowTitle("Supprimer")
                    message_box.setText(f"Supprimer {len(selected_items)} équipement(s) ?")
                    message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                    message_box.setDefaultButton(QMessageBox.No)
                    message_box.setIcon(QMessageBox.Question)
                    
                    reply = message_box.exec_()
                    
                    if reply == QMessageBox.Yes:
                        for item in selected_items:
                            self.remove_equipment(item)
            
            elif event.key() == Qt.Key_F5:
                self.refresh_status()
                self.progress_bar.setFormat("Actualisation...")
                QTimer.singleShot(2000, lambda: self.progress_bar.setFormat("Prêt"))
            
            super().keyPressEvent(event)
            
        except Exception as e:
            logger.error(f"Erreur gestion touches: {e}")

def get_application_root():
    """Retourne le chemin racine de l'application"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
