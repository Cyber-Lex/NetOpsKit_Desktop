from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QPushButton,
    QTextEdit, QMessageBox, QFileDialog, QLabel, QFrame, QApplication, QGraphicsDropShadowEffect,
    QTabWidget, QComboBox, QCheckBox, QGroupBox
)
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSettings
from PyQt5.QtGui import QColor, QFont
import jinja2
from datetime import datetime
import sys

class BaseConfigWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("NetTools", "ConfigGenerator")
        self.initUI()
        self.add_graphical_effects()
        self.load_saved_settings()

    def initUI(self):
        # Layout principal moderne avec marges et espacements
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Création des onglets pour organiser l'interface
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Premier onglet : Configuration de base
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        self.tab_widget.addTab(basic_tab, "Base")

        # Deuxième onglet : Configuration avancée
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        self.tab_widget.addTab(advanced_tab, "Avancée")

        # Onglet de base
        # Groupe de configuration d'appareil
        device_group = QGroupBox("EAR")
        device_layout = QFormLayout(device_group)
        device_layout.setSpacing(10)

        self.hostname_line = self.create_input_field("Hostname :", device_layout, tooltip="Saisissez le nom d'hôte de l'appareil")
        self.enable_secret_line = self.create_input_field("Enable Secret :", device_layout, is_password=True, tooltip="Saisissez le secret enable")
        basic_layout.addWidget(device_group)

        # Groupe d'authentification
        auth_group = QGroupBox("Authentification")
        auth_layout = QFormLayout(auth_group)
        auth_layout.setSpacing(10)

        self.username_line = self.create_input_field("Username :", auth_layout, tooltip="Saisissez le nom d'utilisateur")
        self.user_secret_line = self.create_input_field("User Secret :", auth_layout, is_password=True, tooltip="Saisissez le secret utilisateur")
        self.rsa_label_line = self.create_input_field("RSA Label :", auth_layout, tooltip="Saisissez le label RSA")
        
        basic_layout.addWidget(auth_group)

        # Onglet avancé
        # Paramètres de sécurité
        security_group = QGroupBox("Sécurité")
        security_layout = QFormLayout(security_group)
        
        self.ssh_version_combo = QComboBox()
        self.ssh_version_combo.addItems(["2", "1 2"])
        security_layout.addRow("Version SSH :", self.ssh_version_combo)
        
        self.disable_cdp = QCheckBox("Désactiver CDP")
        self.disable_cdp.setChecked(True)
        security_layout.addRow("", self.disable_cdp)
        
        self.disable_http = QCheckBox("Désactiver les serveurs HTTP/HTTPS")
        self.disable_http.setChecked(True)
        security_layout.addRow("", self.disable_http)
        
        self.disable_domain_lookup = QCheckBox("Désactiver la recherche de domaine")
        self.disable_domain_lookup.setChecked(True)
        security_layout.addRow("", self.disable_domain_lookup)
        
        advanced_layout.addWidget(security_group)
        
        # Configuration de la bannière
        banner_group = QGroupBox("Bannière MOTD")
        banner_layout = QVBoxLayout(banner_group)
        
        self.banner_text = QTextEdit()
        self.banner_text.setPlaceholderText("Saisissez votre bannière MOTD personnalisée...")
        self.banner_text.setText(self.get_default_banner())
        banner_layout.addWidget(self.banner_text)
        
        advanced_layout.addWidget(banner_group)
        
        # Séparateur moderne
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setObjectName("separator")
        main_layout.addWidget(separator)

        # Boutons d'action
        action_layout = QHBoxLayout()
        
        self.generate_button = QPushButton("Générer la Configuration")
        self.generate_button.setObjectName("generateButton")
        self.generate_button.clicked.connect(self.generate_config)
        action_layout.addWidget(self.generate_button)
        
        main_layout.addLayout(action_layout)

        # Zone d'affichage de la configuration générée avec animation
        result_group = QGroupBox("Configuration Générée")
        result_layout = QVBoxLayout(result_group)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setObjectName("resultText")
        result_layout.addWidget(self.result_text)
        
        # Boutons d'actions pour la configuration générée
        result_actions = QHBoxLayout()
        
        self.save_button = QPushButton("Sauvegarder")
        self.save_button.setObjectName("saveButton")
        self.save_button.clicked.connect(self.save_config)
        result_actions.addWidget(self.save_button)
        
        self.copy_button = QPushButton("Copier")
        self.copy_button.setObjectName("copyButton") 
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        result_actions.addWidget(self.copy_button)
        
        self.clear_button = QPushButton("Effacer")
        self.clear_button.setObjectName("clearButton")
        self.clear_button.clicked.connect(self.clear_config)
        result_actions.addWidget(self.clear_button)
        
        result_layout.addLayout(result_actions)
        main_layout.addWidget(result_group)
        
        # Barre de statut
        self.status_bar = QLabel("Prêt")
        self.status_bar.setObjectName("statusBar")
        main_layout.addWidget(self.status_bar)

    def create_input_field(self, label_text, form_layout, is_password=False, tooltip=""):
        """Crée un champ de saisie avec un label, ajoute au formulaire et définit un tooltip."""
        label = QLabel(label_text)
        label.setObjectName("formLabel")
        input_field = QLineEdit()
        input_field.setObjectName("inputField")
        input_field.setToolTip(tooltip)
        if is_password:
            input_field.setEchoMode(QLineEdit.Password)
        form_layout.addRow(label, input_field)
        return input_field

    def add_graphical_effects(self):
        """Ajoute une ombre portée sur les boutons principaux."""
        for button in [self.generate_button, self.save_button, self.copy_button, self.clear_button]:
            shadow_effect = QGraphicsDropShadowEffect(self)
            shadow_effect.setBlurRadius(10)
            shadow_effect.setXOffset(2)
            shadow_effect.setYOffset(2)
            shadow_effect.setColor(QColor(0, 0, 0, 160))
            button.setGraphicsEffect(shadow_effect)

    def get_default_banner(self):
        """Renvoie la bannière MOTD par défaut."""
        return ""  # Bannière par défaut supprimée

    def validate_inputs(self):
        """Valide les entrées utilisateur."""
        if not self.hostname_line.text().strip():
            QMessageBox.warning(self, "Erreur", "Le champ Hostname est obligatoire.")
            return False
        if not self.enable_secret_line.text().strip():
            QMessageBox.warning(self, "Erreur", "Le champ Enable Secret est obligatoire.")
            return False
        if not self.username_line.text().strip():
            QMessageBox.warning(self, "Erreur", "Le champ Username est obligatoire.")
            return False
        if not self.user_secret_line.text().strip():
            QMessageBox.warning(self, "Erreur", "Le champ User Secret est obligatoire.")
            return False
        if not self.rsa_label_line.text().strip():
            QMessageBox.warning(self, "Erreur", "Le champ RSA Label est obligatoire.")
            return False
        return True

    def generate_config(self):
        """Génère la configuration en fonction des entrées utilisateur et anime l'affichage du résultat."""
        if not self.validate_inputs():
            return
        
        current_time = datetime.now().strftime("%H:%M:%S %b %d %Y")
        params = {
            "current_time": current_time,
            "hostname": self.hostname_line.text(),
            "enable_secret": self.enable_secret_line.text(),
            "username": self.username_line.text(),
            "user_secret": self.user_secret_line.text(),
            "rsa_label": self.rsa_label_line.text(),
            "rsa_size": "1024",  # Valeur fixe à 1024
            "ssh_version": self.ssh_version_combo.currentText(),
            "disable_cdp": self.disable_cdp.isChecked(),
            "disable_http": self.disable_http.isChecked(),
            "disable_domain_lookup": self.disable_domain_lookup.isChecked(),
            "banner_text": self.banner_text.toPlainText(),
        }
        
        template_str = """
enable
clock set {{ current_time }}

conf t
hostname {{ hostname }}
enable secret {{ enable_secret }}
username {{ username }} privilege 15 secret {{ user_secret }}
{% if disable_cdp %}
no cdp run
{% endif %}
{% if disable_domain_lookup %}
no ip domain-lookup
{% endif %}
{% if disable_http %}
no ip http server
no ip http secure-server
ip scp server enable
{% endif %}

line con 0
 login local
 logging synchronous

line vty 0 4
 transport input ssh
 transport output ssh
 login local
 exec-timeout 5 0
 crypto key generate rsa label {{ rsa_label }} modulus {{ rsa_size }}
 ip ssh version {{ ssh_version }}

line vty 5 15
 transport input none
 transport output none
 exec-timeout 0 1


banner motd ^
{{ banner_text }}
^
"""
        try:
            template = jinja2.Template(template_str)
            config_generated = template.render(**params)
            self.result_text.setPlainText(config_generated)
            self.animate_result_text()
            self.status_bar.setText("Configuration générée avec succès.")
            QMessageBox.information(self, "Succès", "Configuration générée avec succès.")
        except Exception as e:
            self.result_text.setPlainText(f"Erreur de génération : {e}")
            self.status_bar.setText(f"Erreur : {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur lors de la génération : {e}")

    def animate_result_text(self):
        """Anime l'apparition du texte généré pour un effet visuel agréable."""
        self.result_text.setWindowOpacity(0)
        animation = QPropertyAnimation(self.result_text, b"windowOpacity")
        animation.setDuration(1000)
        animation.setStartValue(0)
        animation.setEndValue(1)
        animation.setEasingCurve(QEasingCurve.InOutQuad)
        animation.start()
        # Conserver la référence à l'animation pour éviter sa destruction prématurée
        self.animation = animation

    def save_config(self):
        """Sauvegarde la configuration générée dans un fichier."""
        config_text = self.result_text.toPlainText()
        if not config_text:
            QMessageBox.warning(self, "Avertissement", "Aucune configuration à sauvegarder.")
            return
        hostname = self.hostname_line.text().strip()
        default_filename = f"{hostname}_config.txt" if hostname else "config.txt"
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder la configuration", default_filename, "Fichiers texte (*.txt);;Tous les fichiers (*)", options=options
        )
        if file_name:
            try:
                with open(file_name, "w", encoding="utf-8") as f:
                    f.write(config_text)
                self.status_bar.setText(f"Configuration sauvegardée dans {file_name}")
                QMessageBox.information(self, "Succès", "La configuration a été sauvegardée avec succès.")
            except Exception as e:
                self.status_bar.setText(f"Erreur lors de la sauvegarde : {e}")
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la sauvegarde : {e}")

    def clear_config(self):
        """Efface tous les champs du formulaire et la zone de résultat."""
        self.hostname_line.clear()
        self.enable_secret_line.clear()
        self.username_line.clear()
        self.user_secret_line.clear()
        self.rsa_label_line.clear()
        self.result_text.clear()
        self.status_bar.setText("Tous les champs ont été effacés.")

    def copy_to_clipboard(self):
        """Copie la configuration générée dans le presse-papiers."""
        config_text = self.result_text.toPlainText()
        if not config_text:
            self.status_bar.setText("Aucune configuration à copier.")
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(config_text)
        self.status_bar.setText("Configuration copiée dans le presse-papiers.")

    def load_saved_settings(self):
        """Charge les paramètres sauvegardés."""
        # Chargement des derniers paramètres utilisés
        self.hostname_line.setText(self.settings.value("last_hostname", ""))
        self.username_line.setText(self.settings.value("last_username", ""))
        self.rsa_label_line.setText(self.settings.value("last_rsa_label", ""))
        
        # Ne pas sauvegarder les mots de passe pour des raisons de sécurité
        
        # Chargement des paramètres avancés
        index = self.ssh_version_combo.findText(self.settings.value("last_ssh_version", "2"))
        if index >= 0:
            self.ssh_version_combo.setCurrentIndex(index)
            
        self.disable_cdp.setChecked(self.settings.value("last_disable_cdp", True, type=bool))
        self.disable_http.setChecked(self.settings.value("last_disable_http", True, type=bool))
        self.disable_domain_lookup.setChecked(self.settings.value("last_disable_domain_lookup", True, type=bool))
        
        saved_banner = self.settings.value("last_banner_text", "")
        if saved_banner:
            self.banner_text.setText(saved_banner)

    def save_current_settings(self):
        """Sauvegarde les paramètres actuels pour une utilisation future."""
        # Sauvegarde des paramètres de base
        self.settings.setValue("last_hostname", self.hostname_line.text())
        self.settings.setValue("last_username", self.username_line.text())
        self.settings.setValue("last_rsa_label", self.rsa_label_line.text())
        
        # Ne pas sauvegarder les mots de passe pour des raisons de sécurité
        
        # Sauvegarde des paramètres avancés
        self.settings.setValue("last_ssh_version", self.ssh_version_combo.currentText())
        self.settings.setValue("last_disable_cdp", self.disable_cdp.isChecked())
        self.settings.setValue("last_disable_http", self.disable_http.isChecked())
        self.settings.setValue("last_disable_domain_lookup", self.disable_domain_lookup.isChecked())
        self.settings.setValue("last_banner_text", self.banner_text.toPlainText())

    def closeEvent(self, event):
        """Événement déclenché lors de la fermeture de l'application."""
        self.save_current_settings()
        event.accept()


