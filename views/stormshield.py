import sys
import time
import serial
from serial.tools import list_ports
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QTextEdit, QMessageBox, QFileDialog, QLabel, QFrame, QApplication, QGraphicsDropShadowEffect,
    QTabWidget, QComboBox, QCheckBox, QGroupBox, QSpinBox
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSettings, QThread, pyqtSignal
from PyQt5.QtGui import QColor, QFont

# INTERFACE_MAP corrigé et commenté avec les numéros de ports physiques
INTERFACE_MAP = {
    # SN210 : 5 ports physiques (port0 à port4)
    # port0: eth0 (out), port1: eth1 (in), port2: eth2 (dmz), port3: eth3 (unused), port4: eth4 (unused)
    'SN210': [
        ("eth0", "out"),    # port0
        ("eth1", "in"),     # port1
        ("eth2", "dmz"),    # port2
        ("eth3", "unused"), # port3
        ("eth4", "unused"), # port4
    ],
    # SN310 : 8 ports physiques (port0 à port7)
    # port0: eth0 (out), port1: eth1 (in), port2: eth2 (dmz1), port3: eth3 (dmz2), port4: eth4 (unused), port5: eth5 (unused), port6: eth6 (unused), port7: eth7 (unused)
    'SN310': [
        ("eth0", "out"),     # port0
        ("eth1", "in"),      # port1
        ("eth2", "dmz1"),    # port2
        ("eth3", "dmz2"),    # port3
        ("eth4", "unused"),  # port4
        ("eth5", "unused"),  # port5
        ("eth6", "unused"),  # port6
        ("eth7", "unused"),  # port7
    ],
    # SN510 : 6 ports physiques (port0 à port5)
    # port0: eth0 (out), port1: eth1 (in), port2: eth2 (dmz1), port3: eth3 (dmz2), port4: eth4 (unused), port5: eth5 (unused)
    'SN510': [
        ("eth0", "out"),     # port0
        ("eth1", "in"),      # port1
        ("eth2", "dmz1"),    # port2
        ("eth3", "dmz2"),    # port3
        ("eth4", "unused"),  # port4
        ("eth5", "unused"),  # port5
    ],
    # SN710 : 8 ports physiques (port0 à port7)
    # port0: eth0 (out), port1: eth1 (in), port2: eth2 (dmz1), port3: eth3 (dmz2), port4: eth4 (dmz3), port5: eth5 (dmz4), port6: eth6 (unused), port7: eth7 (unused)
    'SN710': [
        ("eth0", "out"),     # port0
        ("eth1", "in"),      # port1
        ("eth2", "dmz1"),    # port2
        ("eth3", "dmz2"),    # port3
        ("eth4", "dmz3"),    # port4
        ("eth5", "dmz4"),    # port5
        ("eth6", "unused"),  # port6
        ("eth7", "unused"),  # port7
    ],
    # SN910 : 10 ports physiques (port0 à port9)
    # port0: eth0 (out), port1: eth1 (in), port2: eth2 (dmz1), ..., port9: eth9 (dmz8)
    'SN910': [
        ("eth0", "out"),     # port0
        ("eth1", "in"),      # port1
        ("eth2", "dmz1"),    # port2
        ("eth3", "dmz2"),    # port3
        ("eth4", "dmz3"),    # port4
        ("eth5", "dmz4"),    # port5
        ("eth6", "dmz5"),    # port6
        ("eth7", "dmz6"),    # port7
        ("eth8", "dmz7"),    # port8
        ("eth9", "dmz8"),    # port9
    ],
}

def get_interface_display_name(eth, logical, port_number=None):
    # Ajoute le numéro de port dans le nom affiché si fourni
    if port_number is not None:
        return f"{eth} ({logical} - Port {port_number})"
    return f"{eth} ({logical})"

def get_eth_name_from_display(display):
    return display.split(" ")[0]

class SerialWorker(QThread):
    status_update = pyqtSignal(str)
    command_complete = pyqtSignal(bool)
    
    def __init__(self, port, commands, delay=1):
        super().__init__()
        self.port = port
        self.commands = commands
        self.delay = delay
        self.running = True
        self.serial_conn = None
    
    def run(self):
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                timeout=1
            )
            
            if not self.serial_conn.is_open:
                self.serial_conn.open()
                
            self.status_update.emit("Connexion série établie")
            
            for cmd in self.commands:
                if not self.running:
                    break
                    
                self.status_update.emit(f"Envoi: {cmd}")
                self.serial_conn.write((cmd + "\r\n").encode())
                time.sleep(self.delay)
                
                # Lire la réponse
                if self.serial_conn.in_waiting:
                    response = self.serial_conn.read(self.serial_conn.in_waiting)
                    self.status_update.emit(f"Réponse: {response.decode('utf-8', errors='ignore')}")
            
            self.command_complete.emit(True)
            
        except Exception as e:
            self.status_update.emit(f"Erreur: {str(e)}")
            self.command_complete.emit(False)
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
    
    def stop(self):
        self.running = False
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()

class StormshieldConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("NetOpsKit", "Stormshield")
        self.initUI()
        self.add_graphical_effects()
        self.load_saved_settings()

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Section configuration de base
        basic_group = QGroupBox("Configuration de base")
        basic_layout = QFormLayout(basic_group)
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(list(INTERFACE_MAP.keys()))
        self.model_combo.currentTextChanged.connect(self.update_interface_options)
        basic_layout.addRow("Modèle:", self.model_combo)
        
        self.hostname_edit = self.create_input_field("Nom du firewall:", basic_layout, tooltip="Nom qui sera assigné au firewall")
        self.password_edit = self.create_input_field("Mot de passe admin:", basic_layout, is_password=True, tooltip="Mot de passe administrateur")
        
        # Options DHCP
        self.use_dhcp = QCheckBox("Utiliser DHCP pour OUT")
        self.use_dhcp.setChecked(False)
        self.use_dhcp.toggled.connect(self.toggle_ip_fields)
        basic_layout.addRow("", self.use_dhcp)
        
        # Configuration IP
        self.ip_out_edit = self.create_input_field("Adresse IP OUT:", basic_layout, tooltip="Format: 192.168.1.1/24")
        self.gateway_edit = self.create_input_field("Passerelle par défaut:", basic_layout)
        self.dns1_edit = self.create_input_field("DNS Primaire:", basic_layout)
        self.dns2_edit = self.create_input_field("DNS Secondaire:", basic_layout)
        
        main_layout.addWidget(basic_group)
        
        # Section interfaces
        interfaces_group = QGroupBox("Configuration des interfaces")
        interfaces_layout = QFormLayout(interfaces_group)
        
        self.interface_combo = QComboBox()
        interfaces_layout.addRow("Interface:", self.interface_combo)
        
        main_layout.addWidget(interfaces_group)
        
        # Section connexion série
        serial_group = QGroupBox("Connexion série")
        serial_layout = QFormLayout(serial_group)
        
        self.com_port_combo = QComboBox()
        self.refresh_com_btn = QPushButton("Rafraîchir")
        self.refresh_com_btn.clicked.connect(self.refresh_com_ports)
        
        port_layout = QHBoxLayout()
        port_layout.addWidget(self.com_port_combo)
        port_layout.addWidget(self.refresh_com_btn)
        
        serial_layout.addRow("Port COM:", port_layout)
        main_layout.addWidget(serial_group)
        
        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Prévisualiser")
        self.preview_btn.clicked.connect(self.preview_config)
        
        self.execute_btn = QPushButton("Exécuter")
        self.execute_btn.clicked.connect(self.execute_config)
        
        self.save_btn = QPushButton("Sauvegarder")
        self.save_btn.clicked.connect(self.save_config)
        
        action_layout.addWidget(self.preview_btn)
        action_layout.addWidget(self.execute_btn)
        action_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(action_layout)
        
        # Console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(150)
        self.console.setStyleSheet("background-color: #2b2b2b; color: #e6e6e6;")
        main_layout.addWidget(self.console)
        
        # Initialiser les listes
        self.refresh_com_ports()
        self.update_interface_options()

    def create_input_field(self, label_text, form_layout, is_password=False, tooltip="", enabled=True):
        input_field = QLineEdit()
        if is_password:
            input_field.setEchoMode(QLineEdit.Password)
        if tooltip:
            input_field.setToolTip(tooltip)
        input_field.setEnabled(enabled)
        form_layout.addRow(label_text, input_field)
        return input_field

    def update_interface_options(self):
        model = self.model_combo.currentText()
        self.interface_combo.clear()
        
        if model in INTERFACE_MAP:
            for i, (eth, logical) in enumerate(INTERFACE_MAP[model]):
                display_name = get_interface_display_name(eth, logical, i)
                self.interface_combo.addItem(display_name, eth)

    def refresh_com_ports(self):
        self.com_port_combo.clear()
        ports = list_ports.comports()
        if ports:
            for port in ports:
                self.com_port_combo.addItem(f"{port.device} ({port.description})", port.device)
            self.update_console(f"{len(ports)} ports COM détectés")
        else:
            self.update_console("Aucun port COM détecté")

    def add_graphical_effects(self):
        shadow_buttons = [self.preview_btn, self.execute_btn, self.save_btn]
        for button in shadow_buttons:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(10)
            shadow.setColor(QColor(0, 0, 0, 80))
            shadow.setOffset(3, 3)
            button.setGraphicsEffect(shadow)

    def validate_inputs(self):
        required_fields = [
            (self.hostname_edit.text(), "Nom du firewall"),
            (self.password_edit.text(), "Mot de passe admin")
        ]
        
        # Vérifier si DHCP est désactivé, les champs IP sont requis
        if not self.use_dhcp.isChecked():
            required_fields.extend([
                (self.ip_out_edit.text(), "Adresse IP OUT"),
                (self.gateway_edit.text(), "Passerelle par défaut")
            ])
            
        missing = [field for value, field in required_fields if not value.strip()]
        
        if missing:
            # Solution : Utiliser une variable intermédiaire pour éviter le backslash dans la f-string
            missing_fields = "\n- ".join(missing)
            QMessageBox.warning(self, "Champs manquants", 
                              f"Veuillez remplir les champs suivants :\n- {missing_fields}")
            return False
            
        return True

    def preview_config(self):
        if not self.validate_inputs():
            return
            
        commands = self.generate_commands()
        self.console.clear()
        self.update_console("--- Commandes qui seront exécutées ---")
        for cmd in commands:
            self.update_console(cmd)

    def generate_commands(self):
        commands = []
        
        # Commandes de base
        commands.append(f"CONFIG HOSTNAME={self.hostname_edit.text()}")
        commands.append(f"CONFIG PASSWD={self.password_edit.text()}")
        
        # Configuration IP
        model = self.model_combo.currentText()
        eth_out = "eth0"  # Par défaut
        
        if model in INTERFACE_MAP and INTERFACE_MAP[model]:
            # Trouver l'interface OUT
            for eth, logical in INTERFACE_MAP[model]:
                if logical == "out":
                    eth_out = eth
                    break
        
        if self.use_dhcp.isChecked():
            commands.append(f"CONFIG INTERFACE {eth_out} DHCP=1")
        else:
            commands.append(f"CONFIG INTERFACE {eth_out} ADDRESS={self.ip_out_edit.text()}")
            commands.append(f"CONFIG ROUTE GATEWAY={self.gateway_edit.text()}")
            
            # DNS
            if self.dns1_edit.text():
                commands.append(f"CONFIG DNS PRIMARY={self.dns1_edit.text()}")
            if self.dns2_edit.text():
                commands.append(f"CONFIG DNS SECONDARY={self.dns2_edit.text()}")
        
        # Activation du firewall
        commands.append("CONFIG ACTIVATE=1")
        
        return commands

    def toggle_ip_fields(self):
        use_dhcp = self.use_dhcp.isChecked()
        self.ip_out_edit.setEnabled(not use_dhcp)
        self.gateway_edit.setEnabled(not use_dhcp)
        self.dns1_edit.setEnabled(not use_dhcp)
        self.dns2_edit.setEnabled(not use_dhcp)

    def execute_config(self):
        if not self.validate_inputs():
            return
            
        port = self.com_port_combo.currentData()
        if not port:
            QMessageBox.warning(self, "Port COM manquant", "Veuillez sélectionner un port COM.")
            return
            
        commands = self.generate_commands()
        
        reply = QMessageBox.question(self, "Confirmation", 
                                   f"Êtes-vous sûr de vouloir exécuter la configuration sur le port {port}?", 
                                   QMessageBox.Yes | QMessageBox.No)
                                   
        if reply == QMessageBox.Yes:
            self.console.clear()
            self.update_console(f"Exécution de la configuration sur le port {port}...")
            
            self.worker = SerialWorker(port, commands)
            self.worker.status_update.connect(self.update_console)
            self.worker.command_complete.connect(self.handle_completion)
            self.worker.start()
            
            # Désactiver les boutons pendant l'exécution
            self.execute_btn.setEnabled(False)
            self.preview_btn.setEnabled(False)

    def update_console(self, text):
        self.console.append(text)
        # Auto scroll
        cursor = self.console.textCursor()
        cursor.movePosition(cursor.End)
        self.console.setTextCursor(cursor)

    def handle_completion(self, success):
        self.execute_btn.setEnabled(True)
        self.preview_btn.setEnabled(True)
        
        if success:
            self.update_console("Configuration terminée avec succès!")
            QMessageBox.information(self, "Succès", "Configuration terminée avec succès!")
        else:
            self.update_console("Erreur lors de la configuration!")
            QMessageBox.warning(self, "Erreur", "Erreur lors de la configuration. Veuillez vérifier la console.")

    def save_config(self):
        if not self.validate_inputs():
            return
            
        commands = self.generate_commands()
        config_text = "\n".join(commands)
        
        filename, _ = QFileDialog.getSaveFileName(self, "Sauvegarder la configuration",
                                               f"{self.hostname_edit.text()}_config.txt",
                                               "Fichiers texte (*.txt)")
        if filename:
            with open(filename, 'w') as f:
                f.write(config_text)
            self.update_console(f"Configuration sauvegardée dans {filename}")
            QMessageBox.information(self, "Sauvegarde", f"Configuration sauvegardée dans {filename}")

    def clear_config(self):
        self.hostname_edit.clear()
        self.password_edit.clear()
        self.ip_out_edit.clear()
        self.gateway_edit.clear()
        self.dns1_edit.clear()
        self.dns2_edit.clear()
        self.console.clear()
        self.update_console("Configuration effacée.")

    def copy_to_clipboard(self):
        if not self.validate_inputs():
            return
            
        commands = self.generate_commands()
        config_text = "\n".join(commands)
        
        clipboard = QApplication.clipboard()
        clipboard.setText(config_text)
        self.update_console("Configuration copiée dans le presse-papiers.")

    def load_saved_settings(self):
        self.hostname_edit.setText(self.settings.value("hostname", ""))
        self.ip_out_edit.setText(self.settings.value("ip_out", ""))
        self.gateway_edit.setText(self.settings.value("gateway", ""))
        self.dns1_edit.setText(self.settings.value("dns1", ""))
        self.dns2_edit.setText(self.settings.value("dns2", ""))
        
        model = self.settings.value("model", "")
        if model and self.model_combo.findText(model) >= 0:
            self.model_combo.setCurrentText(model)
        
        use_dhcp = self.settings.value("use_dhcp", False, type=bool)
        self.use_dhcp.setChecked(use_dhcp)
        self.toggle_ip_fields()

    def save_current_settings(self):
        self.settings.setValue("hostname", self.hostname_edit.text())
        self.settings.setValue("ip_out", self.ip_out_edit.text())
        self.settings.setValue("gateway", self.gateway_edit.text())
        self.settings.setValue("dns1", self.dns1_edit.text()) 
        self.settings.setValue("dns2", self.dns2_edit.text())
        self.settings.setValue("model", self.model_combo.currentText())
        self.settings.setValue("use_dhcp", self.use_dhcp.isChecked())

    def closeEvent(self, event):
        self.save_current_settings()
        event.accept()