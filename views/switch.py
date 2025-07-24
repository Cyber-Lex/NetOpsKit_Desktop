from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QTextEdit,
    QMessageBox, QFileDialog, QComboBox, QLabel, QListWidget, QListWidgetItem,
    QHBoxLayout, QFrame, QGraphicsDropShadowEffect, QApplication, QGroupBox,
    QTabWidget, QCheckBox, QSpinBox, QSplitter, QDialog, QSizePolicy, QTableWidget, 
    QHeaderView, QDialogButtonBox, QTableWidgetItem, QScrollArea
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSettings, pyqtSignal
from PyQt5.QtGui import QColor, QIcon
import jinja2
from datetime import datetime
import sys
import re
import json

class SwitchConfigWidget(QWidget):
    # Dictionnaire des modèles de switch et leurs ports
    MODELS_PORTS = {
         # Catalyst 2900 Series
        "Cisco Catalyst 2960 (24 ports)": [f"Fa0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960 (48 ports)": [f"Fa0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960G (24 ports SFP)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960S (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960S (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960-X (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960-X (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960-XR (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960-XR (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960-L (24 ports)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960-L (48 ports)": [f"Gi0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960-Plus (24 ports)": [f"Fa0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960-Plus (48 ports)": [f"Fa0/{i}" for i in range(1, 49)],
        
        # Catalyst 3000 Series
        "Cisco Catalyst 3560 (24 ports)": [f"Fa0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3560 (48 ports)": [f"Fa0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3560E (24 ports)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3560E (48 ports)": [f"Gi0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3560G (24 ports SFP)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3560X (24 ports, Layer 3)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3560X (48 ports, Layer 3)": [f"Gi0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3560-CX (8 ports, Layer 3)": [f"Gi0/{i}" for i in range(1, 9)],
        "Cisco Catalyst 3560-CX (12 ports, Layer 3)": [f"Gi0/{i}" for i in range(1, 13)],
        "Cisco Catalyst 3650 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3650 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3750 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3750 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3750-E (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3750-E (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3750-X (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3750-X (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3850 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3850 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3850 (24 ports SFP, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 25)],
        
        # Catalyst 4000 Series
        "Cisco Catalyst 4500 (24 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 25)],
        "Cisco Catalyst 4500 (48 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 49)],
        "Cisco Catalyst 4500-X (16 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 17)],
        "Cisco Catalyst 4500-X (24 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 25)],
        "Cisco Catalyst 4500-X (32 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 33)],
        "Cisco Catalyst 4500-X (40 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 41)],
        "Cisco Catalyst 4900M (8 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 9)],
        "Cisco Catalyst 4948 (48 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 49)],
        "Cisco Catalyst 4948E (48 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 49)],
        
        # Catalyst 6000 Series
        "Cisco Catalyst 6500 (24 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 25)],
        "Cisco Catalyst 6500 (48 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 49)],
        "Cisco Catalyst 6500 (24 ports SFP, Layer 3)": [f"SFP1/1/{i}" for i in range(1, 25)],
        "Cisco Catalyst 6800 (24 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 25)],
        "Cisco Catalyst 6800 (48 ports, Layer 3)": [f"Gi1/1/{i}" for i in range(1, 49)],
        "Cisco Catalyst 6800 (24 ports SFP+, Layer 3)": [f"Te1/1/{i}" for i in range(1, 25)],
        
        # Catalyst 9000 Series (nouvelle génération)
        "Cisco Catalyst 9200 (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9200 (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9200 (24 ports SFP)": [f"SFP1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9200L (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9200L (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9300 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9300 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9300 (24 ports SFP, Layer 3)": [f"SFP1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9300L (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9300L (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9300X (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9300X (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9400 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9400 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9400 (24 ports SFP, Layer 3)": [f"SFP1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9500 (16 ports SFP+, Layer 3)": [f"Te1/0/{i}" for i in range(1, 17)],
        "Cisco Catalyst 9500 (24 ports SFP+, Layer 3)": [f"Te1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9500 (40 ports SFP+, Layer 3)": [f"Te1/0/{i}" for i in range(1, 41)],
        "Cisco Catalyst 9500 (24 ports QSFP, Layer 3)": [f"Hu1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9600 (24 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9600 (48 ports, Layer 3)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 9600 (24 ports SFP+, Layer 3)": [f"Te1/0/{i}" for i in range(1, 25)],
        
        # Catalyst C-series (ajoutés)
        "Cisco Catalyst C9200L-24T-4G (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst C9200L-48T-4G (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst C9300-24T (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst C9300-48T (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst C9400-LC-24XS (24 ports SFP+)": [f"Te1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst C9400-LC-48UX (48 ports MultiGig)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst C9500-16X (16 ports SFP+)": [f"Te1/0/{i}" for i in range(1, 17)],
        "Cisco Catalyst C9500-24Y4C (24 ports SFP28)": [f"Te1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst C9500-32C (32 ports QSFP)": [f"Hu1/0/{i}" for i in range(1, 33)],
        "Cisco Catalyst C9600-LC-24C (24 ports QSFP)": [f"Hu1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst C9600-LC-48YL (48 ports SFP+)": [f"Te1/0/{i}" for i in range(1, 49)],

        # Catalyst 2960-C Series (ajout)
        "Cisco Catalyst 2960C-8TC-L (8 ports)": [f"Gi0/{i}" for i in range(1, 9)],
        "Cisco Catalyst 2960C-12PC-L (12 ports)": [f"Gi0/{i}" for i in range(1, 13)],
        "Cisco Catalyst 2960C-8PC-L (8 ports)": [f"Gi0/{i}" for i in range(1, 9)],
        "Cisco Catalyst 2960C-12TC-L (12 ports)": [f"Gi0/{i}" for i in range(1, 13)],

        # Autres modèles Catalyst non référencés (exemples courants)
        "Cisco Catalyst 1000 (8 ports)": [f"Gi0/{i}" for i in range(1, 9)],
        "Cisco Catalyst 1000 (16 ports)": [f"Gi0/{i}" for i in range(1, 17)],
        "Cisco Catalyst 1000 (24 ports)": [f"Gi0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 1000 (48 ports)": [f"Gi0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 2960XR (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 2960XR (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3560CX (8 ports)": [f"Gi0/{i}" for i in range(1, 9)],
        "Cisco Catalyst 3560CX (12 ports)": [f"Gi0/{i}" for i in range(1, 13)],
        "Cisco Catalyst 3650-24TD (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3650-48TD (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 3850-24T (24 ports)": [f"Gi1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 3850-48T (48 ports)": [f"Gi1/0/{i}" for i in range(1, 49)],
        "Cisco Catalyst 4500X-16 (16 ports)": [f"Te1/1/{i}" for i in range(1, 17)],
        "Cisco Catalyst 4500X-32 (32 ports)": [f"Te1/1/{i}" for i in range(1, 33)],
        "Cisco Catalyst 9500-40X (40 ports)": [f"Te1/0/{i}" for i in range(1, 41)],
        "Cisco Catalyst 9500-24Y4C (24 ports SFP28)": [f"Te1/0/{i}" for i in range(1, 25)],
        "Cisco Catalyst 9600-48Y (48 ports)": [f"Te1/0/{i}" for i in range(1, 49)],
    }
    configChanged = pyqtSignal()  # Signal émis lors d'un changement de configuration

    # Liste des modèles compatibles Layer 3 (ajoutez ici tous les modèles L3 de votre dictionnaire)
    LAYER3_MODELS = [
  # 2960 X / XR
    "Cisco Catalyst 2960-X (24 ports)",
    "Cisco Catalyst 2960-X (48 ports)",
    "Cisco Catalyst 2960-XR (24 ports, Layer 3)",
    "Cisco Catalyst 2960-XR (48 ports, Layer 3)",

    # 3560 CX / X
    "Cisco Catalyst 3560-CX (8 ports, Layer 3)",
    "Cisco Catalyst 3560-CX (12 ports, Layer 3)",
    "Cisco Catalyst 3560X (24 ports, Layer 3)",
    "Cisco Catalyst 3560X (48 ports, Layer 3)",

    # 3650
    "Cisco Catalyst 3650 (24 ports, Layer 3)",
    "Cisco Catalyst 3650 (48 ports, Layer 3)",

    # 3750  (et dérivés E / X)
    "Cisco Catalyst 3750 (24 ports, Layer 3)",
    "Cisco Catalyst 3750 (48 ports, Layer 3)",
    "Cisco Catalyst 3750-E (24 ports, Layer 3)",
    "Cisco Catalyst 3750-E (48 ports, Layer 3)",
    "Cisco Catalyst 3750-X (24 ports, Layer 3)",
    "Cisco Catalyst 3750-X (48 ports, Layer 3)",

    # 3850
    "Cisco Catalyst 3850 (24 ports, Layer 3)",
    "Cisco Catalyst 3850 (48 ports, Layer 3)",
    "Cisco Catalyst 3850 (24 ports SFP, Layer 3)",

    # 4xxx
    "Cisco Catalyst 4500 (24 ports, Layer 3)",
    "Cisco Catalyst 4500 (48 ports, Layer 3)",
    "Cisco Catalyst 4500-X (16 ports SFP+, Layer 3)",
    "Cisco Catalyst 4500-X (24 ports SFP+, Layer 3)",
    "Cisco Catalyst 4500-X (32 ports SFP+, Layer 3)",
    "Cisco Catalyst 4500-X (40 ports SFP+, Layer 3)",
    "Cisco Catalyst 4900M (8 ports SFP+, Layer 3)",
    "Cisco Catalyst 4948 (48 ports, Layer 3)",
    "Cisco Catalyst 4948E (48 ports, Layer 3)",

    # 6xxx
    "Cisco Catalyst 6500 (24 ports, Layer 3)",
    "Cisco Catalyst 6500 (48 ports, Layer 3)",
    "Cisco Catalyst 6500 (24 ports SFP, Layer 3)",
    "Cisco Catalyst 6800 (24 ports, Layer 3)",
    "Cisco Catalyst 6800 (48 ports, Layer 3)",
    "Cisco Catalyst 6800 (24 ports SFP+, Layer 3)",

    # 9xxx (série 9000)
    "Cisco Catalyst 9300 (24 ports, Layer 3)",
    "Cisco Catalyst 9300 (48 ports, Layer 3)",
    "Cisco Catalyst 9300 (24 ports SFP, Layer 3)",
    "Cisco Catalyst 9300L (24 ports, Layer 3)",
    "Cisco Catalyst 9300L (48 ports, Layer 3)",
    "Cisco Catalyst 9300X (24 ports, Layer 3)",
    "Cisco Catalyst 9300X (48 ports, Layer 3)",
    "Cisco Catalyst 9400 (24 ports, Layer 3)",
    "Cisco Catalyst 9400 (48 ports, Layer 3)",
    "Cisco Catalyst 9400 (24 ports SFP, Layer 3)",
    "Cisco Catalyst 9500 (16 ports SFP+, Layer 3)",
    "Cisco Catalyst 9500 (24 ports SFP+, Layer 3)",
    "Cisco Catalyst 9500 (40 ports SFP+, Layer 3)",
    "Cisco Catalyst 9500 (24 ports QSFP, Layer 3)",
    "Cisco Catalyst 9600 (24 ports, Layer 3)",
    "Cisco Catalyst 9600 (48 ports, Layer 3)",
    "Cisco Catalyst 9600 (24 ports SFP+, Layer 3)",
]

    def __init__(self, parent=None):
        super().__init__(parent)
        # Désactivation de l'historique en effaçant les paramètres sauvegardés
        self.settings = QSettings("NetTools", "SwitchConfigGenerator")
        self.settings.clear()
        
        # Initialisation des listes de ports
        self.selected_access_ports = []
        self.selected_trunk_ports = []
        self.selected_vlan666_ports = []
        
        # Configuration des VLANs par défaut
        self.default_vlans = [
            {"id": "10", "name": "ADMIN"},
            {"id": "20", "name": "PROD"},
            {"id": "30", "name": "VOICE"},
            {"id": "666", "name": "POUBELLE"}
        ]
        
        self.initUI()
        self.add_graphical_effects()
        
        self.configChanged.connect(self.updatePortsDisplay)
        self.setMinimumSize(900, 700)
        
        # Connecter le changement de modèle à la mise à jour de l'interface Layer 3
        self.model_combo.currentTextChanged.connect(self.updateLayer3CheckboxVisibility)
        # Initialiser l'état des contrôles Layer 3 selon le modèle sélectionné
        self.updateLayer3CheckboxVisibility(self.model_combo.currentText())

    def initUI(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Onglets
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("switch_tab_widget")
        self.tab_widget.setMinimumHeight(400)
        main_layout.addWidget(self.tab_widget)
        
        # Onglet "Base"
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_content = QWidget()
        basic_scroll_layout = QVBoxLayout(basic_content)
        basic_layout.addWidget(basic_content)
        self.tab_widget.addTab(basic_tab, "Base")
        
        # Configuration du switch
        switch_group = QGroupBox("Configuration du Switch")
        switch_group.setObjectName("switch_group")
        switch_form = QFormLayout(switch_group)
        self.model_combo = QComboBox()
        self.model_combo.addItems(sorted(list(self.MODELS_PORTS.keys())))
        self.model_combo.setToolTip("Sélectionnez le modèle du switch")
        self.model_combo.setMaximumWidth(220)  # Réduit la largeur de la liste déroulante
        self.model_combo.setMaxVisibleItems(6)  # Affiche moins d'éléments visibles
        switch_form.addRow("Modèle de switch :", self.model_combo)
        self.hostname_edit = QLineEdit()
        self.hostname_edit.setPlaceholderText("Entrez le hostname du switch")
        self.hostname_edit.setToolTip("Saisissez le hostname du switch")
        switch_form.addRow("Hostname :", self.hostname_edit)
        basic_scroll_layout.addWidget(switch_group)
        
        # Configuration des VLANs
        vlans_group = QGroupBox("Configuration des VLANs")
        vlans_group.setObjectName("vlans_group")
        vlans_layout = QVBoxLayout(vlans_group)
        vlans_form = QFormLayout()
        self.vlans_edit = QTextEdit()
        self.vlans_edit.setObjectName("vlans_edit")
        self.vlans_edit.setPlaceholderText("Exemple:\n10:ADMIN\n20:VOICE\n30:PROD")
        self.vlans_edit.setToolTip("Saisissez les VLANs (un par ligne au format ID:Name)")
        self.vlans_edit.setMinimumHeight(100)
        self.vlans_edit.setMaximumHeight(150)
        vlans_form.addRow("VLANs (ID:Name) :", self.vlans_edit)
        vlans_layout.addLayout(vlans_form)
        vlans_buttons = QHBoxLayout()
        self.add_default_vlans_button = QPushButton("Ajouter VLANs par défaut")
        self.add_default_vlans_button.setObjectName("addDefaultVlansButton")
        self.add_default_vlans_button.clicked.connect(self.addDefaultVlans)
        vlans_buttons.addWidget(self.add_default_vlans_button)
        self.clear_vlans_button = QPushButton("Effacer les VLANs")
        self.clear_vlans_button.setObjectName("clearVlansButton")
        self.clear_vlans_button.clicked.connect(self.clearVlans)
        vlans_buttons.addWidget(self.clear_vlans_button)
        vlans_layout.addLayout(vlans_buttons)
        basic_scroll_layout.addWidget(vlans_group)
        
        # Onglet "Ports"
        ports_tab = QWidget()
        ports_layout = QVBoxLayout(ports_tab)
        ports_content = QWidget()
        ports_scroll_layout = QVBoxLayout(ports_content)
        ports_content.setLayout(ports_scroll_layout)  # <-- Cette ligne doit être AVANT ports_layout.addWidget(ports_content)
        ports_layout.addWidget(ports_content)
        self.tab_widget.addTab(ports_tab, "Ports")

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        ports_scroll_layout.addWidget(self.splitter)
        
        # Partie gauche : liste des ports disponibles
        ports_selection = QWidget()
        ports_selection_layout = QVBoxLayout(ports_selection)
        ports_selection.setMinimumWidth(300)
        ports_list_label = QLabel("Ports disponibles :")
        ports_selection_layout.addWidget(ports_list_label)
        self.ports_list = QListWidget()
        self.ports_list.setObjectName("ports_list")
        self.ports_list.setSelectionMode(QListWidget.MultiSelection)
        self.ports_list.setToolTip("Sélectionnez les ports à assigner")
        self.ports_list.setMinimumHeight(200)
        ports_selection_layout.addWidget(self.ports_list)
        select_layout = QHBoxLayout()
        self.btn_select_all = QPushButton("Sélectionner tout")
        self.btn_select_all.setObjectName("btn_select_all")
        self.btn_select_all.clicked.connect(self.ports_list.selectAll)
        select_layout.addWidget(self.btn_select_all)
        self.btn_clear_selection = QPushButton("Désélectionner tout")
        self.btn_clear_selection.setObjectName("btn_clear_selection")
        self.btn_clear_selection.clicked.connect(self.ports_list.clearSelection)
        select_layout.addWidget(self.btn_clear_selection)
        ports_selection_layout.addLayout(select_layout)
        filter_layout = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setObjectName("filter_edit")
        self.filter_edit.setPlaceholderText("Filtrer les ports (ex: 1-10 ou Gi1/0/1)")
        # Connexion de la touche Entrée pour appliquer le filtre
        self.filter_edit.returnPressed.connect(self.applyPortFilter)
        filter_layout.addWidget(self.filter_edit)
        self.filter_button = QPushButton("Appliquer filtre")
        self.filter_button.setObjectName("filterButton")
        self.filter_button.clicked.connect(self.applyPortFilter)
        filter_layout.addWidget(self.filter_button)
        ports_selection_layout.addLayout(filter_layout)
        self.splitter.addWidget(ports_selection)
        
        # Partie droite : assignation des ports
        ports_assignment = QWidget()
        ports_assignment_layout = QVBoxLayout(ports_assignment)
        ports_assignment.setMinimumWidth(400)  # Augmente la largeur minimale du conteneur
        assign_mode_group = QGroupBox("Assigner les ports sélectionnés")
        assign_mode_group.setObjectName("assign_mode_group")
        assign_mode_layout = QVBoxLayout(assign_mode_group)
        assign_mode_layout.setSpacing(10)  # Plus d'espace entre les boutons
        
        # -- BOUTONS D'ASSIGNATION AVEC LARGEUR MINIMALE ET POLICE LISIBLES --
        self.btn_assign_access = QPushButton("Assigner en mode Access")
        self.btn_assign_access.setObjectName("btn_assign_access")
        self.btn_assign_access.clicked.connect(self.assignAccessPorts)
        assign_mode_layout.addWidget(self.btn_assign_access)
        
        self.btn_assign_trunk = QPushButton("Assigner en mode Trunk")
        self.btn_assign_trunk.setObjectName("btn_assign_trunk")
        self.btn_assign_trunk.clicked.connect(self.assignTrunkPorts)
        assign_mode_layout.addWidget(self.btn_assign_trunk)
        
        self.btn_assign_vlan666 = QPushButton("Assigner au VLAN 666 (POUBELLE)")
        self.btn_assign_vlan666.setObjectName("btn_assign_vlan666")
        self.btn_assign_vlan666.clicked.connect(self.assignVlan666Ports)
        assign_mode_layout.addWidget(self.btn_assign_vlan666)
        
        ports_assignment_layout.addWidget(assign_mode_group)
        
        assigned_ports_group = QGroupBox("Ports assignés")
        assigned_ports_group.setObjectName("assigned_ports_group")
        assigned_ports_layout = QVBoxLayout(assigned_ports_group)
        # Ports Access
        access_ports_form = QFormLayout()
        access_ports_row = QHBoxLayout()
        self.access_ports_display = QLineEdit()
        self.access_ports_display.setObjectName("access_ports_display")
        self.access_ports_display.setReadOnly(True)
        access_ports_row.addWidget(self.access_ports_display)
        self.access_ports_remove = QPushButton("Supprimer sélection")
        self.access_ports_remove.setObjectName("accessPortsRemoveButton")
        self.access_ports_remove.clicked.connect(self.removeAccessPorts)
        access_ports_row.addWidget(self.access_ports_remove)
        access_ports_form.addRow("Ports Access :", access_ports_row)
        assigned_ports_layout.addLayout(access_ports_form)
        # Ports Trunk
        trunk_ports_form = QFormLayout()
        trunk_ports_row = QHBoxLayout()
        self.trunk_ports_display = QLineEdit()
        self.trunk_ports_display.setObjectName("trunk_ports_display")
        self.trunk_ports_display.setReadOnly(True)
        trunk_ports_row.addWidget(self.trunk_ports_display)
        self.trunk_ports_remove = QPushButton("Supprimer sélection")
        self.trunk_ports_remove.setObjectName("trunkPortsRemoveButton")
        self.trunk_ports_remove.clicked.connect(self.removeTrunkPorts)
        trunk_ports_row.addWidget(self.trunk_ports_remove)
        trunk_ports_form.addRow("Ports Trunk :", trunk_ports_row)
        assigned_ports_layout.addLayout(trunk_ports_form)
        # Ports VLAN 666
        vlan666_ports_form = QFormLayout()
        vlan666_ports_row = QHBoxLayout()
        self.vlan666_ports_display = QLineEdit()
        self.vlan666_ports_display.setObjectName("vlan666_ports_display")
        self.vlan666_ports_display.setReadOnly(True)
        vlan666_ports_row.addWidget(self.vlan666_ports_display)
        self.vlan666_ports_remove = QPushButton("Supprimer sélection")
        self.vlan666_ports_remove.setObjectName("vlan666PortsRemoveButton")
        self.vlan666_ports_remove.clicked.connect(self.removeVlan666Ports)
        vlan666_ports_row.addWidget(self.vlan666_ports_remove)
        vlan666_ports_form.addRow("Ports VLAN 666 :", vlan666_ports_row)
        assigned_ports_layout.addLayout(vlan666_ports_form)
        ports_assignment_layout.addWidget(assigned_ports_group)
        self.splitter.addWidget(ports_assignment)
        self.splitter.setSizes([500, 500])
        ports_scroll_layout.addWidget(self.splitter)
        
        # Bouton "Supprimer tout" pour effacer le formulaire de ports
        self.clear_port_button = QPushButton("Supprimer tout")
        self.clear_port_button.setObjectName("clearPortButton")
        self.clear_port_button.setToolTip("Effacer toutes les assignations de ports")
        self.clear_port_button.clicked.connect(self.clearPortForm)
        ports_scroll_layout.addWidget(self.clear_port_button)
        
        # Onglet "Avancée"
        advanced_tab = QWidget()
        # Création d'un QScrollArea pour l'onglet avancé
        self.advanced_scroll = QScrollArea()
        self.advanced_scroll.setWidgetResizable(True)
        self.advanced_scroll.setWidget(advanced_tab)
        
        # Définir une hauteur fixe pour empêcher l'interface de descendre
        self.advanced_scroll.setMinimumHeight(400)
        self.advanced_scroll.setMaximumHeight(600)
        
        # Layout pour l'onglet avancé avec alignement en haut
        advanced_layout = QVBoxLayout(advanced_tab)
        advanced_layout.setContentsMargins(10, 10, 10, 10)
        advanced_layout.setAlignment(Qt.AlignTop)
        
        self.tab_widget.addTab(self.advanced_scroll, "Avancée")
        
        security_group = QGroupBox("Sécurité")
        security_layout = QFormLayout(security_group)
        self.dhcp_snooping_check = QCheckBox("Activer DHCP Snooping")
        security_layout.addRow("", self.dhcp_snooping_check)
        self.arp_inspection_check = QCheckBox("Activer ARP Inspection")
        security_layout.addRow("", self.arp_inspection_check)
        self.port_security_check = QCheckBox("Activer Port Security sur les ports Access")
        security_layout.addRow("", self.port_security_check)
        advanced_layout.addWidget(security_group)
        
        # CORRECTION: Groupe Layer 3 amélioré
        self.layer3_group = QGroupBox("Fonctionnalités Layer 3")
        self.layer3_group.setObjectName("layer3_group")
        self.layer3_group.setStyleSheet("QGroupBox#layer3_group { border: 2px solid #0078D7; border-radius: 5px; }")
        layer3_layout = QVBoxLayout(self.layer3_group)
        
        # Layout pour l'option principale Layer 3
        layer3_main_layout = QHBoxLayout()
        self.layer3_check = QCheckBox("Activer Layer 3 (ip routing)")
        self.layer3_check.setObjectName("layer3_check")
        self.layer3_check.setToolTip("Active le routage IP sur les switches compatibles Layer 3")
        self.layer3_check.stateChanged.connect(self.layer3CheckChanged)
        layer3_main_layout.addWidget(self.layer3_check)
        
        # Indicateur de compatibilité (sera mis à jour par updateLayer3CheckboxVisibility)
        self.layer3_indicator = QLabel("")
        self.layer3_indicator.setObjectName("layer3_indicator")
        layer3_main_layout.addWidget(self.layer3_indicator)
        layer3_main_layout.addStretch()
        layer3_layout.addLayout(layer3_main_layout)
        
        # Texte informatif sur le Layer 3
        layer3_info = QLabel("Cette option active le routage entre VLANs et les fonctionnalités Layer 3.\nDisponible uniquement sur les modèles compatibles.")
        layer3_info.setWordWrap(True)
        layer3_layout.addWidget(layer3_info)
        
        # Ajout du groupe Layer 3 au layout principal
        advanced_layout.addWidget(self.layer3_group)
        
        misc_group = QGroupBox("Options Diverses")
        misc_layout = QFormLayout(misc_group)
        self.cdp_check = QCheckBox("Activer CDP")
        self.cdp_check.setChecked(True)
        misc_layout.addRow("", self.cdp_check)
        self.lldp_check = QCheckBox("Activer LLDP")
        misc_layout.addRow("", self.lldp_check)
        self.logging_check = QCheckBox("Activer Logging")
        self.logging_check.setChecked(True)
        misc_layout.addRow("", self.logging_check)
        advanced_layout.addWidget(misc_group)
        
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        self.generate_button = QPushButton("Générer la configuration Switch")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.clicked.connect(self.generate_config)
        main_layout.addWidget(self.generate_button)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(50)
        main_layout.addWidget(self.result_text)

        # Ajout des boutons d'action comme dans config_base
        action_layout = QHBoxLayout()
        self.save_button = QPushButton("Sauvegarder")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self.save_config)
        action_layout.addWidget(self.save_button)
        self.copy_button = QPushButton("Copier")
        self.copy_button.setObjectName("copyButton")
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        action_layout.addWidget(self.copy_button)
        self.clear_button = QPushButton("Effacer")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_config)
        action_layout.addWidget(self.clear_button)
        main_layout.addLayout(action_layout)

        self.updatePortsList()

    def add_graphical_effects(self):
        # Appliquer un effet d'ombre à tous les QPushButton de l'interface
        for button in self.findChildren(QPushButton):
            shadow = QGraphicsDropShadowEffect(self)
            shadow.setBlurRadius(10)
            shadow.setXOffset(2)
            shadow.setYOffset(2)
            shadow.setColor(QColor(0, 0, 0, 160))
            button.setGraphicsEffect(shadow)

    def animate_result_text(self):
        self.result_text.setWindowOpacity(0)
        animation = QPropertyAnimation(self.result_text, b"windowOpacity")
        animation.setDuration(1000)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()
        self.animation = animation

    def updatePortsList(self):
        model = self.model_combo.currentText()
        ports = self.MODELS_PORTS.get(model, [])
        self.ports_list.clear()
        for port in ports:
            item = QListWidgetItem(port)
            self.ports_list.addItem(item)
        self.updatePortsDisplay()

    def updatePortsDisplay(self):
        access_ports_text = []
        for port_data in self.selected_access_ports:
            if isinstance(port_data, dict):
                access_ports_text.append(f"{port_data['port']} (VLAN {port_data['vlan']})")
            else:
                access_ports_text.append(port_data)
        self.access_ports_display.setText(", ".join(access_ports_text))
        self.trunk_ports_display.setText(", ".join(sorted(self.selected_trunk_ports)))
        self.vlan666_ports_display.setText(", ".join(sorted(self.selected_vlan666_ports)))

    def applyPortFilter(self):
        filter_text = self.filter_edit.text().strip()
        if not filter_text:
            return
            
        # Réinitialiser la sélection
        for i in range(self.ports_list.count()):
            self.ports_list.item(i).setSelected(False)
            
        try:
            if "-" in filter_text:
                # Format de plage (ex: 1-10)
                start, end = map(int, filter_text.split("-"))
                for i in range(self.ports_list.count()):
                    item = self.ports_list.item(i)
                    port_text = item.text()
                    port_num_match = re.search(r'(\d+)$', port_text)
                    if port_num_match:
                        port_num = int(port_num_match.group(1))
                        if start <= port_num <= end:
                            item.setSelected(True)
            else:
                # Format simple (ex: Gi1/0/1 ou juste un numéro)
                count_selected = 0
                for i in range(self.ports_list.count()):
                    item = self.ports_list.item(i)
                    if filter_text.lower() in item.text().lower():
                        item.setSelected(True)
                        count_selected += 1
                
                if count_selected == 0:
                    QMessageBox.information(self, "Filtre", "Aucun port ne correspond à ce filtre.")
        except Exception as e:
            QMessageBox.warning(self, "Erreur de filtre", f"Impossible d'appliquer le filtre: {str(e)}")

    def updateLayer3CheckboxVisibility(self, model_name):
        """Affiche ou masque les options Layer 3 selon la compatibilité du modèle"""
        is_layer3_model = model_name in self.LAYER3_MODELS
        
        # Débogage pour voir si le modèle est compatible
        print(f"Modèle: {model_name}, Compatible Layer 3: {is_layer3_model}")
        
        # Màj de l'indication visuelle
        if hasattr(self, 'layer3_indicator'):
            if is_layer3_model:
                self.layer3_indicator.setText("✓ Modèle compatible")
                self.layer3_indicator.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.layer3_indicator.setText("✗ Modèle non compatible")
                self.layer3_indicator.setStyleSheet("color: red;")
        
        # Assurer que le groupe Layer 3 est toujours visible, mais les contrôles sont activés/désactivés
        if hasattr(self, 'layer3_group'):
            self.layer3_group.setVisible(True)  # Toujours visible
            self.layer3_check.setEnabled(is_layer3_model)  # Activé seulement si compatible
            
            # Styliser pour indiquer clairement l'état
            if is_layer3_model:
                self.layer3_group.setStyleSheet("QGroupBox#layer3_group { border: 2px solid green; border-radius: 5px; }")
            else:
                self.layer3_group.setStyleSheet("QGroupBox#layer3_group { border: 2px solid #888888; border-radius: 5px; }")
        else:
            print("ERREUR: Attribut layer3_group non trouvé!")
        
        # Si le modèle n'est pas compatible Layer 3, décocher la case
        if not is_layer3_model and hasattr(self, 'layer3_check') and self.layer3_check.isChecked():
            self.layer3_check.blockSignals(True)
            self.layer3_check.setChecked(False)
            self.layer3_check.blockSignals(False)
            self.result_text.clear()
            QMessageBox.warning(self, "Modèle incompatible", 
                f"Le modèle '{model_name}' n'est pas compatible Layer 3.\n"
                "La configuration Layer 3 a été désactivée.")

    def layer3CheckChanged(self, state):
        """Gère les changements d'état de la case à cocher Layer 3"""
        current_model = self.model_combo.currentText()
        is_layer3_model = current_model in self.LAYER3_MODELS
        
        if state == Qt.Checked:
            if not is_layer3_model:
                # L'utilisateur a tenté d'activer Layer 3 sur un modèle incompatible
                QMessageBox.warning(self, "Modèle incompatible", 
                    f"Le modèle sélectionné '{current_model}' n'est pas compatible avec les fonctionnalités Layer 3.\n\n"
                    "Veuillez sélectionner un modèle compatible Layer 3 pour activer cette fonctionnalité.")
                # Décocher automatiquement la case
                self.layer3_check.blockSignals(True)
                self.layer3_check.setChecked(False)
                self.layer3_check.blockSignals(False)
                return
            else:
                # Modèle compatible, afficher juste un message explicatif
                # mais ne pas générer la configuration (ce sera fait par le template)
                QMessageBox.information(self, "Configuration Layer 3", 
                    "La configuration Layer 3 sera générée.\n\n"
                    "NOTE: Cette configuration nécessitera un redémarrage du switch.\n"
                    "Les commandes sdm prefer et reload seront exécutées avant l'activation du routage IP.")
        else:
            # Case décochée, effacer le résultat si besoin
            if self.result_text.toPlainText().startswith("! Configuration de transition Layer"):
                self.result_text.clear()

    def clearPortForm(self):
        self.selected_access_ports = []
        self.selected_trunk_ports = []
        self.selected_vlan666_ports = []
        self.ports_list.clearSelection()
        self.updatePortsDisplay()
        self.configChanged.emit()

    def assignAccessPorts(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        vlans = self.parse_vlans()
        vlan_options = [f"{vlan['id']} - {vlan['name']}" for vlan in vlans if vlan['id'] != "666"]
        if not vlan_options:
            QMessageBox.warning(self, "Erreur", "Aucun VLAN disponible. Veuillez créer des VLANs d'abord.")
            return

        vlan_dialog = QDialog(self)
        vlan_dialog.setWindowTitle("Sélection du VLAN")
        dialog_layout = QVBoxLayout(vlan_dialog)
        dialog_layout.addWidget(QLabel("Choisissez le VLAN pour les ports Access sélectionnés:"))
        vlan_combo = QComboBox()
        vlan_combo.addItems(vlan_options)
        dialog_layout.addWidget(vlan_combo)
        button_box = QHBoxLayout()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(vlan_dialog.accept)
        cancel_button = QPushButton("Annuler")
        cancel_button.clicked.connect(vlan_dialog.reject)
        button_box.addWidget(ok_button)
        button_box.addWidget(cancel_button)
        dialog_layout.addLayout(button_box)

        result = vlan_dialog.exec_()
        if result == QDialog.Accepted:
            selected_vlan_text = vlan_combo.currentText()
            selected_vlan_id = selected_vlan_text.split(' - ')[0]
            for item in selected_items:
                port = item.text()
                if port in self.selected_trunk_ports:
                    self.selected_trunk_ports.remove(port)
                if port in self.selected_vlan666_ports:
                    self.selected_vlan666_ports.remove(port)

                existing_port_index = -1
                for i, port_data in enumerate(self.selected_access_ports):
                    if isinstance(port_data, dict) and port_data['port'] == port:
                        existing_port_index = i
                        break
                    elif not isinstance(port_data, dict) and port_data == port:
                        existing_port_index = i
                        break

                port_data = {'port': port, 'vlan': selected_vlan_id}
                if existing_port_index >= 0:
                    self.selected_access_ports[existing_port_index] = port_data
                else:
                    self.selected_access_ports.append(port_data)

            self.selected_access_ports.sort(key=lambda x: self.natural_sort_key(x['port']))
            self.updatePortsDisplay()
            self.configChanged.emit()

    def removeAccessPorts(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            port = item.text()
            for i, port_data in enumerate(self.selected_access_ports):
                if isinstance(port_data, dict) and port_data['port'] == port:
                    self.selected_access_ports.pop(i)
                    break
                elif not isinstance(port_data, dict) and port_data == port:
                    self.selected_access_ports.pop(i)
                    break

        self.updatePortsDisplay()
        self.configChanged.emit()

    def assignTrunkPorts(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            port = item.text()
            self.selected_access_ports = [p for p in self.selected_access_ports
                                          if not (isinstance(p, dict) and p['port'] == port)]
            if port in self.selected_vlan666_ports:
                self.selected_vlan666_ports.remove(port)
            if port not in self.selected_trunk_ports:
                self.selected_trunk_ports.append(port)

        self.selected_trunk_ports.sort(key=self.natural_sort_key)
        self.updatePortsDisplay()
        self.configChanged.emit()

    def removeTrunkPorts(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            port = item.text()
            if port in self.selected_trunk_ports:
                self.selected_trunk_ports.remove(port)

        self.updatePortsDisplay()
        self.configChanged.emit()

    def assignVlan666Ports(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            port = item.text()
            self.selected_access_ports = [p for p in self.selected_access_ports
                                          if not (isinstance(p, dict) and p['port'] == port)]
            if port in self.selected_trunk_ports:
                self.selected_trunk_ports.remove(port)
            if port not in self.selected_vlan666_ports:
                self.selected_vlan666_ports.append(port)

        self.selected_vlan666_ports.sort(key=self.natural_sort_key)
        self.updatePortsDisplay()
        self.configChanged.emit()

    def removeVlan666Ports(self):
        selected_items = self.ports_list.selectedItems()
        if not selected_items:
            return

        for item in selected_items:
            port = item.text()
            if port in self.selected_vlan666_ports:
                self.selected_vlan666_ports.remove(port)

        self.updatePortsDisplay()
        self.configChanged.emit()

    def natural_sort_key(self, s):
        return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', s)]

    def addDefaultVlans(self):
        current_text = self.vlans_edit.toPlainText().strip()
        default_vlans_text = "\n".join([f"{vlan['id']}:{vlan['name']}" for vlan in self.default_vlans])
        if current_text:
            current_vlans = {line.split(":")[0].strip() for line in current_text.split("\n") if ":" in line}
            vlans_to_add = []
            for vlan in self.default_vlans:
                if vlan["id"] not in current_vlans and vlan["id"] != "666":
                    vlans_to_add.append(f"{vlan['id']}:{vlan['name']}")
            if vlans_to_add:
                self.vlans_edit.setPlainText(current_text + "\n" + "\n".join(vlans_to_add))
        else:
            vlans_to_add = [f"{vlan['id']}:{vlan['name']}" for vlan in self.default_vlans if vlan["id"] != "666"]
            self.vlans_edit.setPlainText("\n".join(vlans_to_add))

    def clearVlans(self):
        self.vlans_edit.clear()

    def copy_to_clipboard(self):
        config_text = self.result_text.toPlainText()
        if not config_text:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(config_text)
        QMessageBox.information(self, "Copié", "Configuration copiée dans le presse-papiers.")

    def clear_config(self):
        self.result_text.clear()

    def parse_vlans(self):
        vlans_text = self.vlans_edit.toPlainText().strip()
        vlans = []
        has_vlan666 = False
        for line in vlans_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            if len(parts) == 2:
                vlan_id = parts[0].strip()
                vlan_name = parts[1].strip()
                if vlan_id == "666":
                    has_vlan666 = True
                try:
                    vlan_id_int = int(vlan_id)
                    if 1 <= vlan_id_int <= 4094:
                        vlans.append({"id": vlan_id, "name": vlan_name})
                except ValueError:
                    pass
        if not has_vlan666:
            vlans.append({"id": "666", "name": "POUBELLE"})
        return vlans

    def generate_config(self):
        try:
            model = self.model_combo.currentText()
            hostname = self.hostname_edit.text().strip()
            if not hostname:
                QMessageBox.warning(self, "Erreur", "Veuillez définir un hostname pour le switch")
                return

            # Vérifier la compatibilité Layer 3 à nouveau lors de la génération
            layer3_requested = self.layer3_check.isChecked()
            is_layer3_model = model in self.LAYER3_MODELS
            
            if layer3_requested and not is_layer3_model:
                QMessageBox.critical(self, "Erreur de configuration",
                                    f"Le modèle '{model}' n'est pas compatible Layer 3.\n"
                                    "La configuration ne peut pas être générée avec Layer 3 activé.\n\n"
                                    "Veuillez désactiver l'option Layer 3 ou choisir un modèle compatible.")
                return
                
            # Continuer avec la génération normale
            vlans = self.parse_vlans()
            
            access_ports_with_vlans = []
            for port_data in self.selected_access_ports:
                if isinstance(port_data, dict):
                    access_ports_with_vlans.append(port_data)
                else:
                    default_vlan = vlans[0]["id"] if vlans else "1"
                    access_ports_with_vlans.append({'port': port_data, 'vlan': default_vlan})
            access_ports_with_vlans.sort(key=lambda x: self.natural_sort_key(x['port']))
            
            # Déterminer la commande SDM prefer appropriée selon le modèle
            sdm_command = "sdm prefer lanbase-routing"
            if layer3_requested and is_layer3_model:
                if "3560" in model or "3750" in model or "3850" in model:
                    sdm_command = "sdm prefer routing"
                elif "4500" in model or "6500" in model or "9300" in model or "9500" in model:
                    sdm_command = "sdm prefer routing"
            
            params = {
                "model": model,
                "hostname": hostname,
                "vlans": vlans,
                "access_ports_with_vlans": access_ports_with_vlans,
                "trunk_ports": sorted(self.selected_trunk_ports, key=self.natural_sort_key),
                "vlan666_ports": sorted(self.selected_vlan666_ports, key=self.natural_sort_key),
                "current_time": datetime.now().strftime("%H:%M:%S %b %d %Y"),
                "cdp": self.cdp_check.isChecked(),
                "lldp": self.lldp_check.isChecked(),
                "logging": self.logging_check.isChecked(),
                "dhcp_snooping": self.dhcp_snooping_check.isChecked(),
                "arp_inspection": self.arp_inspection_check.isChecked(),
                "port_security": self.port_security_check.isChecked(),
                "default_vlan": vlans[0]["id"] if vlans else "1",
                "layer3_enabled": layer3_requested and is_layer3_model,
                "sdm_command": sdm_command
            }
            
            template_str = """enable
conf t
hostname {{ hostname }}
{% for vlan in vlans %}
vlan {{ vlan.id }}
name {{ vlan.name }}
{% endfor %}
{% if not cdp %}
no cdp run
{% endif %}
{% if lldp %}
lldp run
{% endif %}
{% if logging %}
logging buffered 16384
logging console informational
{% endif %}
{% if dhcp_snooping %}
ip dhcp snooping
{% for vlan in vlans %}
ip dhcp snooping vlan {{ vlan.id }}
{% endfor %}
{% endif %}
{% if arp_inspection %}
{% for vlan in vlans %}
ip arp inspection vlan {{ vlan.id }}
{% endfor %}
{% endif %}
{% if access_ports_with_vlans %}
{% for port_data in access_ports_with_vlans %}
interface {{ port_data.port }}
 description ACCESS PORT - VLAN {{ port_data.vlan }}
 switchport mode access
 switchport access vlan {{ port_data.vlan }}
{% if port_security %}
 switchport port-security
 switchport port-security mac-address sticky
 switchport port-security violation shutdown
{% endif %}
{% if dhcp_snooping %}
 ip dhcp snooping trust
{% endif %}
{% if arp_inspection %}
 ip arp inspection trust
{% endif %}
{% endfor %}
{% endif %}
{% if trunk_ports %}
{% for port in trunk_ports %}
interface {{ port }}
 description TRUNK PORT
 switchport mode trunk
 switchport trunk allowed vlan all
{% endfor %}
{% endif %}
{% if vlan666_ports %}
{% for port in vlan666_ports %}
interface {{ port }}
 description DISABLED PORT - VLAN 666
 switchport mode access
 switchport access vlan 666
 shutdown
{% endfor %}
{% endif %}
{% if layer3_enabled %}
{{ sdm_command }}
write memory
reload
ip routing
{% endif %}

"""
            template = jinja2.Template(template_str)
            config_generated = template.render(**params)
            self.result_text.setPlainText(config_generated)
            self.animate_result_text()
        except Exception as e:
            self.result_text.setPlainText(f"Erreur de génération : {str(e)}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors de la génération de la configuration : {str(e)}")

    def save_config(self):
        config_text = self.result_text.toPlainText()
        if not config_text:
            QMessageBox.warning(self, "Avertissement", "Aucune configuration à sauvegarder.")
            return

        hostname = self.hostname_edit.text().strip()
        default_filename = f"{hostname}_config.txt" if hostname else "switch_config.txt"
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder la configuration", default_filename,
            "Fichiers texte (*.txt);;Tous les fichiers (*)",
            options=options
        )
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(config_text)
                QMessageBox.information(self, "Succès", "La configuration a été sauvegardée avec succès.")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la sauvegarde : {str(e)}")

    def load_saved_settings(self):
        # Cette méthode est désactivée car l'historique est désactivé dans le __init__
        pass

    def save_current_settings(self):
        # Cette méthode est désactivée car l'historique est désactivé dans le __init__
        pass

    def is_valid_ip(self, ip):
        # Validation basique d'une adresse IPv4
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                if not 0 <= int(part) <= 255:
                    return False
            return True
        except:
            return False