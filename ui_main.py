import sys
import os
from PyQt5 import uic
from PyQt5.QtWidgets import (
    QMainWindow, QApplication, QTabWidget, QFileDialog, QMessageBox, QVBoxLayout, QWidget, QPlainTextEdit, QPushButton, QHBoxLayout
)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt
from utils.file_utils import get_resource_path  # <--- ajout

# Import des widgets personnalisés
from views.home_page import HomePage
from views.config_generator_cme import CMEConfigWidget
from views.config_base import BaseConfigWidget
from views.ssh_connection import SSHConnection
from views.serial_connection import SerialConnection
from views.switch import SwitchConfigWidget
from views.generateur import GenerateurConfigWidget
from views.supervision import SupervisionWidget
from views.tftp_server import TFTPServerWidget
from views.maj import UpdateTab
from views.sys_log import SyslogServerGUI  
from views.stormshield import StormshieldConfigWidget


class ConfigGeneratorWindow(QMainWindow):
    @staticmethod
    def get_resource_path(relative_path):
        return get_resource_path(relative_path)  # <--- délégation

    def __init__(self):
        super().__init__()
        # Définir les chemins de ressources de manière dynamique
        self.STYLESHEET_PATH = self.get_resource_path("resources/style.qss")
        self.ICON_PATH = self.get_resource_path("resources/logo/logo_netops.png")  
        
        # Vérifier que les fichiers existent
        for path, name in [(self.STYLESHEET_PATH, "Stylesheet"), (self.ICON_PATH, "Icon")]:
            if not os.path.exists(path):
                print(f"ERREUR: {name} n'existe pas au chemin: {path}")
            else:
                print(f"{name} trouvé au chemin: {path}")
                
        self.initUI()

    def initUI(self):
        try:
            # Créer l'instance de HomePage et définir comme widget central
            self.home_page = HomePage()
            self.setCentralWidget(self.home_page)
            
            # Load stylesheet seulement si nécessaire
            app = QApplication.instance()
            if not hasattr(app, 'style_loaded') or not app.style_loaded:
                try:
                    with open(self.STYLESHEET_PATH, 'r') as style_file:
                        style_content = style_file.read()
                        print(f"Style chargé avec succès depuis ConfigGeneratorWindow: {self.STYLESHEET_PATH}")
                        app.setStyleSheet(style_content)
                        app.style_loaded = True
                except Exception as style_error:
                    print(f"Erreur lors du chargement du style dans ConfigGeneratorWindow: {str(style_error)}")
            else:
                print("Style déjà chargé dans l'application, skip dans ConfigGeneratorWindow")
            
            # Obtenir les références aux widgets depuis l'instance HomePage
            self.stackedWidget = self.home_page.stackedWidget
            self.homePage = self.home_page.homePage
            self.generationPage = self.home_page.generationPage
            self.sshPage = self.home_page.sshPage
            self.consolePage = self.home_page.consolePage
            
            # Obtenir les références aux boutons depuis l'instance HomePage
            self.configGenerationButton = self.home_page.configGenerationButton
            self.sshConnectionButton = self.home_page.sshConnectionButton
            self.consoleConnectionButton = self.home_page.consoleConnectionButton
            self.backToHomeFromConfigButton = self.home_page.backToHomeFromConfigButton
            
            # Ne pas créer de nouvelles références pour les widgets SSH, utiliser directement ceux de HomePage
            self.sshConnectionWidget = self.home_page.sshConnectionWidget
            
            # Initialize the tabs
            self.initTabs()
                
        except Exception as e:
            print(f"Erreur lors du chargement de HomePage: {str(e)}")
            # En cas d'échec, création d'une interface basique
            self.setWindowTitle("Configuration Generator")
            self.resize(800, 600)
            
            # Créer un layout principal
            main_layout = QVBoxLayout()
            central_widget = QWidget()
            central_widget.setLayout(main_layout)
            self.setCentralWidget(central_widget)
            
            # Créer le widget pour les onglets et l'ajouter au layout
            self.stackedWidget = QTabWidget()
            main_layout.addWidget(self.stackedWidget)
            
            # Créer des pages basiques
            self.homePage = QWidget()
            self.generationPage = QWidget()
            self.sshPage = QWidget()
            self.consolePage = QWidget()
            
            # Ajouter des layouts pour chaque page
            self.homePage.setLayout(QVBoxLayout())
            self.generationPage.setLayout(QVBoxLayout())
            self.sshPage.setLayout(QVBoxLayout())
            self.consolePage.setLayout(QVBoxLayout())
            
            # Ajouter les pages au widget empilé
            self.stackedWidget.addTab(self.homePage, "Accueil")
            self.stackedWidget.addTab(self.generationPage, "Configuration")
            self.stackedWidget.addTab(self.sshPage, "SSH")

            # Créer des boutons pour la navigation
            self.configGenerationButton = QPushButton("Config Generation")
            self.sshConnectionButton = QPushButton("SSH Connection")
            self.backToHomeFromConfigButton = QPushButton("Back to Home")
            self.backToHomeFromSSHButton = QPushButton("Back to Home")
            self.injectConfigButton = QPushButton("Inject SSH Config")

            
            # Ajouter les boutons aux pages
            self.homePage.layout().addWidget(self.configGenerationButton)
            self.homePage.layout().addWidget(self.sshConnectionButton)
            
            self.generationPage.layout().addWidget(self.backToHomeFromConfigButton)
            self.sshPage.layout().addWidget(self.backToHomeFromSSHButton)
            self.sshPage.layout().addWidget(self.injectConfigButton)

        # Mettre à jour les chemins d'icônes
        try:
            self.setWindowIcon(QIcon(self.ICON_PATH))
        except Exception as e:
            print(f"Erreur lors du chargement de l'icône: {str(e)}")

        # Connect buttons after initializing tabs
        self.connectButtons()
        
        # Make sure we're showing the home page initially
        self.home_page.show_home()
        print("UI initialized successfully!")

    def initTabs(self):
        self.configTabs = QTabWidget()
        self.configTabs.setObjectName("configTabs")

        # Création des différents widgets
        self.baseTab = BaseConfigWidget()
        self.switchTab = SwitchConfigWidget()
        self.cmeTab = CMEConfigWidget()
        self.generateurTab = GenerateurConfigWidget()
        self.supervisionTab = SupervisionWidget()
        self.tftpTab = TFTPServerWidget()
        self.maj = UpdateTab()
        self.syslog = SyslogServerGUI()
        self.stormshield = StormshieldConfigWidget()

        # Ajout des onglets avec des labels (et emojis pour un style moderne)
        self.configTabs.addTab(self.baseTab, "🌈 Base")
        self.configTabs.addTab(self.switchTab, "🔌 Switch")
        self.configTabs.addTab(self.cmeTab, "📞 CME")
        self.configTabs.addTab(self.generateurTab, "🔨 Maintenance")
        self.configTabs.addTab(self.maj, "🚧 Mise à Jours")    
        self.configTabs.addTab(self.tftpTab, "💾 TFTP")
        self.configTabs.addTab(self.syslog, "📊 SysLog")
        self.configTabs.addTab(self.stormshield, "🔒 Stormshield")
        self.configTabs.addTab(self.supervisionTab, "👁️ Supervision")


        # Trouver le widget de contenu dans la page de génération
        # Si la page a été structurée avec le bouton en haut et un widget de contenu,
        # nous devons trouver ce widget de contenu
        content_widget = None
        for i in range(self.generationPage.layout().count()):
            item = self.generationPage.layout().itemAt(i)
            if item.widget() and not isinstance(item.widget(), QPushButton):
                content_widget = item.widget()
                break
                
        # S'il y a un widget de contenu trouvé, utiliser son layout
        if content_widget and content_widget.layout():
            content_widget.layout().addWidget(self.configTabs)
        else:
            # Sinon, utiliser le layout principal de la page, mais s'assurer que le bouton retour reste en haut
            if not self.generationPage.layout():
                self.generationPage.setLayout(QVBoxLayout())
            self.generationPage.layout().addWidget(self.configTabs)

        
        # Partager l'instance TFTP avec le module CME s'il existe
        if hasattr(self.cmeTab, 'set_tftp_widget'):
            self.cmeTab.set_tftp_widget(self.tftpTab)


    def injectSSHConfig(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Sélectionner un fichier de configuration", "", "Fichiers texte (*.txt)")
        if file_name:
            try:
                with open(file_name, "r") as f:
                    config = f.read()
                # Utiliser l'instance de SSHConnection créée par HomePage
                self.sshConnectionWidget.inject_configuration(config)
                QMessageBox.information(self, "Succès", "Configuration injectée avec succès via SSH.")
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de l'injection : {e}")

    def connectButtons(self):
        """Connect UI buttons to their respective actions"""
        try:
            # Connecter le bouton de retour de la page de génération de configuration
            # à la méthode show_home de l'instance HomePage
            if hasattr(self, 'backToHomeFromConfigButton'):
                try:
                    self.backToHomeFromConfigButton.clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.backToHomeFromConfigButton.clicked.connect(self.home_page.show_home)
            
            # Pour la connexion des boutons d'injection, utiliser la référence à sshConnectionWidget
            if hasattr(self, 'injectConfigButton'):
                try:
                    self.injectConfigButton.clicked.disconnect()
                except (TypeError, RuntimeError):
                    pass
                self.injectConfigButton.clicked.connect(self.sshConnectionWidget.open_file_dialog)
        except Exception as e:
            print(f"Erreur lors de la connexion des boutons: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ConfigGeneratorWindow()
    window.setWindowTitle("NetOpsKit")
    window.resize(1000, 700)  # Ensure a good initial size
    window.show()
    sys.exit(app.exec_())