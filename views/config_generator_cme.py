import os
import json
from datetime import datetime

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QTextEdit, QMessageBox, QFileDialog, QComboBox, QLabel, QFrame, QTabWidget,
    QHBoxLayout, QAction
)
from PyQt5.QtCore import QRegExp, Qt, QSettings, QDateTime
from PyQt5.QtGui import QRegExpValidator, QIcon
import jinja2

##############################
# VALIDATEURS
##############################
class IPAddressValidator(QRegExpValidator):
    def __init__(self, parent=None):
        pattern = r"^(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."\
                  r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."\
                  r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})\."\
                  r"(25[0-5]|2[0-4]\d|[0-1]?\d{1,2})$"
        super().__init__(QRegExp(pattern), parent)

class MacAddressValidator(QRegExpValidator):
    def __init__(self, parent=None):
        pattern = r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$"
        super().__init__(QRegExp(pattern), parent)

##############################
# DONNÉES DE CONFIGURATION
##############################
class CMEConfigData:
    DEFAULT_VALUES = {
        "max_dn": 10,
        "max_pool": 5,
        "numbering_start": 2000,
        "dhcp_pool_name": "VOICE",
        "dial_peer_sortant": 100,
        "dial_peer_entrant": 101,
        "destination_pattern": "2....",
        "ntp_server": "192.168.1.1"
    }
    
    FIRMWARE_OPTIONS = {
        "7970": ["apps70.9-2-1TH1-13.sbn", "term71.default.loads", "term70.default.loads", "SIP70.9-2-1S.loads",
                 "jar70sip.9-2-1TH1-13.sbn", "dsp70.9-2-1TH1-13.sbn", "cvm70sip.9-2-1TH1-13.sbn", "cnu70.9-2-1TH1-13.sbn"],
        "7962": ["term62.default.loads", "term42.default.loads", "SIP42.9-4-2SR3-1S.loads",
                 "jar42sip.9-4-2ES26.sbn", "dsp42.9-4-2ES26.sbn", "cvm42sip.9-4-2ES26.sbn",
                 "cnu42.9-4-2ES26.sbn", "apps42.9-4-2ES26.sbn"],
        "7965": ["apps45.9-4-2ES26.sbn", "cnu45.9-4-2ES26.sbn", "cvm45sip.9-4-2ES26.sbn",
                 "dsp45.9-4-2ES26.sbn", "jar45sip.9-4-2ES26.sbn", "SIP45.9-4-2SR3-1S.loads",
                 "term45.default.loads", "term65.default.loads"],
        "8865": ["apps9.2-1SR1.sbn", "term9.2.default.loads", "SIP9.2-1SR1.loads",
                 "jar9.2sip.9-2-1SR1.sbn", "dsp9.2-1SR1.sbn", "cvm9.2sip.9-2-1SR1.sbn",
                 "cnu9.2-1SR1.sbn"]
    }
    
    def __init__(self):
        self.telephony = {
            "loopback_interface": "",
            "source_address": "",
            "max_dn": CMEConfigData.DEFAULT_VALUES["max_dn"],
            "max_pool": CMEConfigData.DEFAULT_VALUES["max_pool"],
            "ntp_server": CMEConfigData.DEFAULT_VALUES["ntp_server"],
            "translation_value": "",
            "numbering_start": CMEConfigData.DEFAULT_VALUES["numbering_start"],
            "pool_mac_addresses": []
        }
        self.network = {
            "dhcp_pool_name": CMEConfigData.DEFAULT_VALUES["dhcp_pool_name"],
            "dhcp_network": "",
            "dhcp_default_router": "",
            "dhcp_option150": "",
            "dhcp_option42": ""
        }
        self.dial_peer = {
            "dial_peer_sortant": CMEConfigData.DEFAULT_VALUES["dial_peer_sortant"],
            "dial_peer_entrant": CMEConfigData.DEFAULT_VALUES["dial_peer_entrant"],
            "destination_pattern": CMEConfigData.DEFAULT_VALUES["destination_pattern"],
            "session_target": ""
        }
        self.firmware = {
            "phone_type": "7970",
            "tftp_server_ip": "",
            "firmware_files": [],
            "external_firmware_path": "",
            "use_external_firmware": False
        }
    
    @classmethod
    def get_firmware_tar_for_phone_type(cls, phone_type):
        # Ne plus utiliser cette méthode
        return None
    
    def to_dict(self):
        data = {
            "loopback_interface": self.telephony["loopback_interface"],
            "source_address": self.telephony["source_address"],
            "max_dn": self.telephony["max_dn"],
            "max_pool": self.telephony["max_pool"],
            "ntp_server": self.telephony["ntp_server"],
            "translation_value": self.telephony["translation_value"],
            "dial_peer_sortant": self.dial_peer["dial_peer_sortant"],
            "dial_peer_entrant": self.dial_peer["dial_peer_entrant"],
            "destination_pattern": self.dial_peer["destination_pattern"],
            "session_target": self.dial_peer["session_target"],
            "dhcp": self.network,
            "firmware": self.firmware,
            "selected_tar_file": os.path.basename(self.firmware["external_firmware_path"]) if self.firmware["external_firmware_path"] else ""
        }
        numbering_start = self.telephony["numbering_start"]
        dn_list = []
        for i in range(self.telephony["max_dn"]):
            num = numbering_start + i
            dn_list.append({"number": num, "label": str(num), "name": str(num)})
        data["dns"] = dn_list
        
        macs = self.telephony["pool_mac_addresses"]
        pool_list = []
        for i in range(self.telephony["max_pool"]):
            pool = {
                "pool_id": i + 1,
                "id_mac": macs[i] if i < len(macs) else "",
                "type": self.firmware["phone_type"],
                "dns": [dn_list[i]] if i < len(dn_list) else []
            }
            pool_list.append(pool)
        data["pools"] = pool_list
        
        # Sélectionne le bon fichier TAR selon le mode
        if self.firmware["use_external_firmware"] and self.firmware["external_firmware_path"]:
            data["selected_tar_file"] = os.path.basename(self.firmware["external_firmware_path"])
        else:
            data["selected_tar_file"] = os.path.basename(self.firmware["selected_tar_file"]) if self.firmware["selected_tar_file"] else ""
        
        return data
    
    def update_firmware_files(self):
        if self.firmware["external_firmware_path"]:
            # Si un firmware externe est sélectionné, on l'ajoute en première position
            self.firmware["firmware_files"] = [os.path.basename(self.firmware["external_firmware_path"])] + \
                                            self.FIRMWARE_OPTIONS.get(self.firmware["phone_type"], [])
        else:
            # Sinon on n'utilise que les fichiers par défaut
            self.firmware["firmware_files"] = self.FIRMWARE_OPTIONS.get(self.firmware["phone_type"], [])
    
    def to_json(self):
        return json.dumps({
            "telephony": self.telephony,
            "network": self.network,
            "dial_peer": self.dial_peer,
            "firmware": self.firmware
        }, indent=2)
    
    def from_json(self, json_str):
        try:
            data = json.loads(json_str)
            self.telephony = data.get("telephony", self.telephony)
            self.network = data.get("network", self.network)
            self.dial_peer = data.get("dial_peer", self.dial_peer)
            self.firmware = data.get("firmware", self.firmware)
            self.update_firmware_files()
            return True
        except Exception:
            return False

##############################
# GENERATEUR DE CONFIGURATION
##############################
class CMEConfigGenerator:
    def __init__(self):
        self.template_str = """
enable
configure terminal

interface loopback 10
ip address {{ loopback_interface }} 255.255.255.255
description LOOP_VOIP


ip dhcp pool {{ dhcp.dhcp_pool_name }}
  network {{ dhcp.dhcp_network }}
  default-router {{ dhcp.dhcp_default_router }}
  option 150 ip {{ dhcp.dhcp_option150 }}
  option 42 ip {{ dhcp.dhcp_option42 }}


voice service voip
  allow-connections sip to sip
  sip
    bind all source-interface {{ loopback_interface }}
    registrar server expires max 600 min 60
    rtp-port range 16384 16390

voice register global
  mode cme
  source-address {{ source_address }} port 5060
  max-dn {{ max_dn }}
  max-pool {{ max_pool }}
  date-format D/M/Y
  timezone 21
  time-format 24
  ntp {{ ntp_server }} mode directedbroadcast
  no auto-reg
  tftp-path flash:
  create profile

{% for dn in dns %}
voice register dn {{ loop.index }}
  number {{ dn.number }}
  label {{ dn.label }}
  name {{ dn.name }}
{% endfor %}

{% for pool in pools %}
voice register pool {{ pool.pool_id }}
  id mac {{ pool.id_mac }}
  type {{ pool.type }}{% if pool.dns %}
  number {{ pool.dns | map(attribute='number') | join("\\n  number ") }}{% endif %}
{% endfor %}

voice translation-rule 1
  rule 1 /^2(....\)/ /{{ translation_value }}\\1/
voice translation-rule 2
  rule 1 /^{{ translation_value }}\(....\)/ /2\\1/
voice translation-profile SORTANT
  translate calling 1
voice translation-profile ENTRANT
  translate called 2
voice class codec 1
  codec preference 1 g711alaw
  codec preference 2 g711ulaw
  codec preference 3 g729r8

dial-peer voice {{ dial_peer_sortant }} voip
  description SORTANT
  translation-profile outgoing SORTANT
  destination-pattern {{ destination_pattern }}....
  session protocol sipv2
  session target ipv4:{{ session_target }}
  voice-class codec 1
  no vad

dial-peer voice {{ dial_peer_entrant }} voip
  description ENTRANT
  translation-profile incoming ENTRANT
  incoming called-number .
  no vad

archive tar /xtract tftp://{{ firmware.tftp_server_ip }}/{{ firmware.firmware_files[0] }} flash:/Firmware/{{ firmware.phone_type }}/SIP/
{% for file in firmware.firmware_files %}
tftp-server flash:/Firmware/{{ firmware.phone_type }}/SIP/{{ file }} alias {{ file }}
{% endfor %}
"""
        self.template = jinja2.Template(self.template_str)
    
    def generate(self, config_data):
        params = config_data.to_dict()
        
        required_fields = [
            ("loopback_interface", "Interface Loopback"),
            ("source_address", "Interface Source"),
            ("translation_value", "Translation Value"),
            ("dhcp.dhcp_network", "DHCP Network"),
            ("dhcp.dhcp_default_router", "DHCP Default Router"),
            ("session_target", "Session Target"),
        ]
        
        for field, label in required_fields:
            parts = field.split('.')
            value = params
            for part in parts:
                value = value.get(part, "")
            if not value:
                raise ValueError("Champs obligatoires manquants: " + label)
        
        return self.template.render(**params)

##############################
# INTERFACE PRINCIPALE
##############################
class CMEConfigWidget(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config_data = CMEConfigData()
        self.config_generator = CMEConfigGenerator()
        self.tftp_widget = None  # Utilisation du TFTP distant uniquement
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle("Générateur de configuration CME")
        self.setMinimumSize(800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        self.tabs = QTabWidget()
        self.tabs.setObjectName("cmeTabWidget")
        main_layout.addWidget(self.tabs)
        
        self.telephony_tab = QWidget()
        self.initTelephonyTab()
        self.tabs.addTab(self.telephony_tab, "Téléphonie")
        
        self.network_tab = QWidget()
        self.initNetworkTab()
        self.tabs.addTab(self.network_tab, "Réseau")
        
        self.dial_peer_tab = QWidget()
        self.initDialPeerTab()
        self.tabs.addTab(self.dial_peer_tab, "Dial Peer")
        
        self.firmware_tab = QWidget()
        self.initFirmwareTab()
        self.tabs.addTab(self.firmware_tab, "Firmware")
        
        button_layout = QHBoxLayout()
        self.generate_button = QPushButton("Générer la configuration CME")
        self.generate_button.setObjectName("generateButton")
        button_layout.addWidget(self.generate_button)
        
        self.save_button = QPushButton("Sauvegarder la configuration")
        self.save_button.setObjectName("saveButton")
        button_layout.addWidget(self.save_button)
        
        self.clear_form_button = QPushButton("Effacer")
        button_layout.addWidget(self.clear_form_button)
        
        main_layout.addLayout(button_layout)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setObjectName("resultText")
        main_layout.addWidget(self.result_text)
        
        self.generate_button.clicked.connect(self.generateConfig)
        self.save_button.clicked.connect(self.saveConfig)
        self.clear_form_button.clicked.connect(self.clearForm)
        
        self.setDefaultValues()

    def initTelephonyTab(self):
        layout = QFormLayout()
        ip_validator = IPAddressValidator()
        
        self.loopback_interface_edit = QLineEdit()
        self.loopback_interface_edit.setValidator(ip_validator)
        self.loopback_interface_edit.setPlaceholderText("192.168.1.10")
        layout.addRow(QLabel("Interface Loopback:"), self.loopback_interface_edit)
        
        self.source_address_edit = QLineEdit()
        self.source_address_edit.setValidator(ip_validator)
        self.source_address_edit.setPlaceholderText("192.168.1.1")
        layout.addRow(QLabel("Interface Source:"), self.source_address_edit)
        
        self.ntp_server_edit = QLineEdit()
        self.ntp_server_edit.setValidator(ip_validator)
        self.ntp_server_edit.setPlaceholderText("192.168.1.1")
        layout.addRow(QLabel("NTP Server:"), self.ntp_server_edit)

        self.translation_value_edit = QLineEdit()
        self.translation_value_edit.setPlaceholderText("5")
        layout.addRow(QLabel("Translation Value:"), self.translation_value_edit)
        
        self.max_dn_edit = QLineEdit()
        self.max_dn_edit.setPlaceholderText("10")
        layout.addRow(QLabel("Max DN:"), self.max_dn_edit)
        
        self.max_pool_edit = QLineEdit()
        self.max_pool_edit.setPlaceholderText("5")
        layout.addRow(QLabel("Max Pool:"), self.max_pool_edit)
        
        self.numbering_start_edit = QLineEdit()
        self.numbering_start_edit.setPlaceholderText("2000")
        layout.addRow(QLabel("Numérotation commence par:"), self.numbering_start_edit)
        
        self.pool_mac_addresses_edit = QLineEdit()
        self.pool_mac_addresses_edit.setPlaceholderText("ex:AA:BB:CC:DD:EE:FF,11:22:33:44:55:66")
        layout.addRow(QLabel("Pool MAC Addresses:"), self.pool_mac_addresses_edit)
        
        self.telephony_tab.setLayout(layout)
    
    def initNetworkTab(self):
        layout = QFormLayout()
        ip_validator = IPAddressValidator()
        
        self.dhcp_pool_name_edit = QLineEdit()
        self.dhcp_pool_name_edit.setPlaceholderText("VOICE")
        layout.addRow(QLabel("DHCP Pool Name:"), self.dhcp_pool_name_edit)
        
        self.dhcp_network_edit = QLineEdit()
        self.dhcp_network_edit.setPlaceholderText("192.168.1.0/24")
        layout.addRow(QLabel("DHCP Network:"), self.dhcp_network_edit)
        
        self.dhcp_default_router_edit = QLineEdit()
        self.dhcp_default_router_edit.setValidator(ip_validator)
        self.dhcp_default_router_edit.setPlaceholderText("192.168.1.254")
        layout.addRow(QLabel("DHCP Default Router:"), self.dhcp_default_router_edit)
        
        self.dhcp_option150_edit = QLineEdit()
        self.dhcp_option150_edit.setValidator(ip_validator)
        self.dhcp_option150_edit.setPlaceholderText("10.10.10.10")
        layout.addRow(QLabel("DHCP Option 150 IP:"), self.dhcp_option150_edit)
        
        self.dhcp_option42_edit = QLineEdit()
        self.dhcp_option42_edit.setValidator(ip_validator)
        self.dhcp_option42_edit.setPlaceholderText("10.10.10")
        layout.addRow(QLabel("DHCP Option 42 IP:"), self.dhcp_option42_edit)
        
        self.network_tab.setLayout(layout)
    
    def initDialPeerTab(self):
        layout = QFormLayout()
        
        self.dial_peer_sortant_edit = QLineEdit()
        self.dial_peer_sortant_edit.setPlaceholderText("100")
        layout.addRow(QLabel("Dial Peer Sortant:"), self.dial_peer_sortant_edit)
        
        self.dial_peer_entrant_edit = QLineEdit()
        self.dial_peer_entrant_edit.setPlaceholderText("101")
        layout.addRow(QLabel("Dial Peer Entrant:"), self.dial_peer_entrant_edit)
        
        self.destination_pattern_edit = QLineEdit()
        self.destination_pattern_edit.setPlaceholderText("862...")
        layout.addRow(QLabel("Destination Pattern:"), self.destination_pattern_edit)
        
        self.session_target_edit = QLineEdit()
        self.session_target_edit.setPlaceholderText("192.168.1.100")
        layout.addRow(QLabel("SIP distant:"), self.session_target_edit)
        
        self.dial_peer_tab.setLayout(layout)
    
    def initFirmwareTab(self):
        layout = QFormLayout()
        ip_validator = IPAddressValidator()
        
        # Type de téléphone et IP TFTP
        self.firmware_phone_type_combo = QComboBox()
        self.firmware_phone_type_combo.addItems(CMEConfigData.FIRMWARE_OPTIONS.keys())
        self.firmware_phone_type_combo.currentTextChanged.connect(self.updateFirmwareFiles)
        layout.addRow(QLabel("Type de Téléphone CISCO:"), self.firmware_phone_type_combo)
        
        self.tftp_server_ip_edit = QLineEdit()
        self.tftp_server_ip_edit.setValidator(ip_validator)
        self.tftp_server_ip_edit.setPlaceholderText("192.168.1.1")
        layout.addRow(QLabel("TFTP Server IP:"), self.tftp_server_ip_edit)
        
        # Section firmware externe avec layout horizontal
        firmware_row_widget = QWidget()
        firmware_row_layout = QHBoxLayout(firmware_row_widget)
        firmware_row_layout.setContentsMargins(0, 0, 0, 0)
        
        self.external_firmware_path_edit = QLineEdit()
        self.external_firmware_path_edit.setReadOnly(True)
        self.external_firmware_path_edit.setPlaceholderText("Aucun firmware externe sélectionné")
        firmware_row_layout.addWidget(self.external_firmware_path_edit)
        
        browse_btn = QPushButton("Parcourir...")
        browse_btn.setFixedWidth(160)  # Largeur augmentée
        browse_btn.setFixedHeight(32)  # Hauteur augmentée
        browse_btn.clicked.connect(self.browseFirmwareFile)
        firmware_row_layout.addWidget(browse_btn)
        
        layout.addRow(QLabel("Firmware externe:"), firmware_row_widget)
        
        # Liste des fichiers firmware
        self.firmware_files_edit = QTextEdit()
        self.firmware_files_edit.setReadOnly(True)
        layout.addRow(QLabel("Fichiers firmware requis:"), self.firmware_files_edit)
        
        self.firmware_tab.setLayout(layout)
        
        # Mise à jour initiale des fichiers firmware
        self.updateFirmwareFiles(self.firmware_phone_type_combo.currentText())

    def browseFirmwareFile(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un firmware externe",
            "",
            "Fichiers TAR (*.tar);;Tous les fichiers (*)"
        )
        if file_name:
            self.external_firmware_path_edit.setText(file_name)
            self.config_data.firmware["external_firmware_path"] = file_name
            self.config_data.firmware["use_external_firmware"] = True
            self.updateFirmwareFiles(self.firmware_phone_type_combo.currentText())

    def updateFirmwareFiles(self, phone_type):
        self.config_data.firmware["phone_type"] = phone_type
        self.config_data.update_firmware_files()
        self.firmware_files_edit.setPlainText("\n".join(self.config_data.firmware["firmware_files"]))

    def safe_int_convert(self, value, default=0):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def getDataFromUI(self):
        self.config_data.telephony["loopback_interface"] = self.loopback_interface_edit.text()
        self.config_data.telephony["source_address"] = self.source_address_edit.text()
        self.config_data.telephony["ntp_server"] = self.ntp_server_edit.text()
        self.config_data.telephony["translation_value"] = self.translation_value_edit.text()
        
        self.config_data.telephony["max_dn"] = self.safe_int_convert(self.max_dn_edit.text(), 10)
        self.config_data.telephony["max_pool"] = self.safe_int_convert(self.max_pool_edit.text(), 5)
        self.config_data.telephony["numbering_start"] = self.safe_int_convert(self.numbering_start_edit.text(), 2000)
        
        mac_text = self.pool_mac_addresses_edit.text()
        self.config_data.telephony["pool_mac_addresses"] = [m.strip() for m in mac_text.split(",") if m.strip()]
        
        self.config_data.network["dhcp_pool_name"] = self.dhcp_pool_name_edit.text()
        self.config_data.network["dhcp_network"] = self.dhcp_network_edit.text()
        self.config_data.network["dhcp_default_router"] = self.dhcp_default_router_edit.text()
        self.config_data.network["dhcp_option150"] = self.dhcp_option150_edit.text()
        self.config_data.network["dhcp_option42"] = self.dhcp_option42_edit.text()
        
        self.config_data.dial_peer["dial_peer_sortant"] = self.safe_int_convert(self.dial_peer_sortant_edit.text(), 100)
        self.config_data.dial_peer["dial_peer_entrant"] = self.safe_int_convert(self.dial_peer_entrant_edit.text(), 101)
        self.config_data.dial_peer["destination_pattern"] = self.destination_pattern_edit.text()
        self.config_data.dial_peer["session_target"] = self.session_target_edit.text()
        
        self.config_data.firmware["phone_type"] = self.firmware_phone_type_combo.currentText()
        self.config_data.firmware["tftp_server_ip"] = self.tftp_server_ip_edit.text()
        
        self.config_data.update_firmware_files()
    
    def setDataToUI(self):
        self.loopback_interface_edit.setText(self.config_data.telephony.get("loopback_interface", ""))
        self.source_address_edit.setText(self.config_data.telephony.get("source_address", ""))
        self.max_dn_edit.setText(str(self.config_data.telephony.get("max_dn", "")))
        self.max_pool_edit.setText(str(self.config_data.telephony.get("max_pool", "")))
        self.ntp_server_edit.setText(self.config_data.telephony.get("ntp_server", ""))
        self.translation_value_edit.setText(self.config_data.telephony.get("translation_value", ""))
        self.numbering_start_edit.setText(str(self.config_data.telephony.get("numbering_start", "")))
        self.pool_mac_addresses_edit.setText(", ".join(self.config_data.telephony.get("pool_mac_addresses", [])))
        
        self.dhcp_pool_name_edit.setText(self.config_data.network.get("dhcp_pool_name", ""))
        self.dhcp_network_edit.setText(self.config_data.network.get("dhcp_network", ""))
        self.dhcp_default_router_edit.setText(self.config_data.network.get("dhcp_default_router", ""))
        self.dhcp_option150_edit.setText(self.config_data.network.get("dhcp_option150", ""))
        self.dhcp_option42_edit.setText(self.config_data.network.get("dhcp_option42", ""))
        
        self.dial_peer_sortant_edit.setText(str(self.config_data.dial_peer.get("dial_peer_sortant", "")))
        self.dial_peer_entrant_edit.setText(str(self.config_data.dial_peer.get("dial_peer_entrant", "")))
        self.destination_pattern_edit.setText(self.config_data.dial_peer.get("destination_pattern", ""))
        self.session_target_edit.setText(self.config_data.dial_peer.get("session_target", ""))
        
        phone_type = self.config_data.firmware.get("phone_type", "7970")
        self.firmware_phone_type_combo.setCurrentText(phone_type)
        self.tftp_server_ip_edit.setText(self.config_data.firmware.get("tftp_server_ip", ""))
        self.updateFirmwareFiles(phone_type)
    
    def setDefaultValues(self):
        self.loopback_interface_edit.clear()
        self.source_address_edit.clear()
        self.ntp_server_edit.clear()
        self.translation_value_edit.clear()
        self.max_dn_edit.clear()
        self.max_pool_edit.clear()
        self.numbering_start_edit.clear()
        self.pool_mac_addresses_edit.clear()
        
        self.dhcp_pool_name_edit.clear()
        self.dhcp_network_edit.clear()
        self.dhcp_default_router_edit.clear()
        self.dhcp_option150_edit.clear()
        self.dhcp_option42_edit.clear()
        
        self.dial_peer_sortant_edit.clear()
        self.dial_peer_entrant_edit.clear()
        self.destination_pattern_edit.clear()
        self.session_target_edit.clear()
        
        self.tftp_server_ip_edit.clear()
        self.external_firmware_path_edit.clear()
        self.config_data.firmware["external_firmware_path"] = ""
        self.config_data.firmware["use_external_firmware"] = False
        self.updateFirmwareFiles(self.firmware_phone_type_combo.currentText())
    
    def clearForm(self):
        self.setDefaultValues()
        self.result_text.clear()
        self.config_data = CMEConfigData()
        self.statusBar().showMessage("Formulaire effacé", 3000)
    
    def generateConfig(self):
        try:
            self.getDataFromUI()
            
            required_fields = [
                (self.config_data.telephony.get("loopback_interface"), "Interface Loopback"),
                (self.config_data.telephony.get("source_address"), "Interface Source"),
                (self.config_data.telephony.get("translation_value"), "Translation Value"),
                (self.config_data.network.get("dhcp_network"), "DHCP Network"),
                (self.config_data.network.get("dhcp_default_router"), "DHCP Default Router"),
                (self.config_data.dial_peer.get("session_target"), "Session Target"),
            ]
            
            missing_fields = [label for value, label in required_fields if not value]
            if missing_fields:
                error_msg = "Champs obligatoires manquants :\n" + "\n".join(missing_fields)
                QMessageBox.warning(self, "Champs Incomplets", error_msg)
                return
            
            config_generated = self.config_generator.generate(self.config_data)
            self.result_text.setPlainText(config_generated)
            self.statusBar().showMessage("Configuration générée avec succès", 3000)
            
        except ValueError as e:
            QMessageBox.warning(self, "Erreur de génération", str(e))
            self.statusBar().showMessage("Erreur de génération", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Erreur inattendue", f"Une erreur inattendue s'est produite: {e}")
            self.statusBar().showMessage("Erreur inattendue", 3000)
    
    def saveConfig(self):
        config_text = self.result_text.toPlainText()
        if not config_text:
            QMessageBox.warning(self, "Avertissement", "Aucune configuration à sauvegarder.")
            return
        
        default_name = f"cme_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        file_name, _ = QFileDialog.getSaveFileName(
            self, 
            "Sauvegarder la configuration", 
            default_name,
            "Fichiers texte (*.txt);;Tous les fichiers (*)"
        )
        
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(config_text)
                QMessageBox.information(self, "Succès", "La configuration a été sauvegardée avec succès.")
                self.statusBar().showMessage(f"Configuration sauvegardée dans {file_name}", 3000)
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la sauvegarde : {e}")
                self.statusBar().showMessage("Erreur lors de la sauvegarde", 3000)
