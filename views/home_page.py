import os
import sys
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
    QMainWindow, QStackedWidget, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QTextEdit, QSizePolicy, QSpacerItem, QFrame
)
from PyQt5.QtGui import QPixmap, QIcon, QFont
from PyQt5.QtCore import Qt, QSize

# Fix the import statement to use the correct module path
from views.serial_connection import SerialConnection
from views.ssh_connection import SSHConnection 

class HomePage(QMainWindow):
    def __init__(self, parent=None):
        super(HomePage, self).__init__(parent)   
        # Cache pour les ressources uniquement (mais pas pour les pages)
        self._resource_cache = {}
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Create stacked widget for different pages
        self.stackedWidget = QStackedWidget()
        self.stackedWidget.setObjectName("stackedWidget")
        main_layout.addWidget(self.stackedWidget)
        
        # Create all pages at initialization (suppression du lazy loading)
        self.homePage = self.create_home_page()
        self.generationPage = self.create_generation_page()
        self.sshPage = self.create_ssh_page()
        self.consolePage = self.create_console_page()
        
        # Add pages to stacked widget
        self.stackedWidget.addWidget(self.homePage)
        self.stackedWidget.addWidget(self.generationPage)
        self.stackedWidget.addWidget(self.sshPage)
        self.stackedWidget.addWidget(self.consolePage)
        
        # Initialize UI components
        self.init_ui()
        
        # Connect signals to slots
        self.connect_signals()
        
        # Start on home page
        self.stackedWidget.setCurrentIndex(0)
    
    def create_home_page(self):
        page = QWidget()
        page.setObjectName("homePage")
        layout = QVBoxLayout(page)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Spacer top
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # Logo parfaitement centré
        logo_row = QHBoxLayout()
        logo_row.addStretch()
        self.logoLabel = QLabel()
        self.logoLabel.setMinimumSize(250, 250)
        self.logoLabel.setMaximumSize(400, 400)
        self.logoLabel.setAlignment(Qt.AlignCenter)
        self.logoLabel.setStyleSheet("background: transparent;")
        logo_row.addWidget(self.logoLabel)
        logo_row.addStretch()
        layout.addLayout(logo_row)

        # Titre principal seulement
        homeLabel = QLabel("Bienvenue dans NetOpsKit")
        homeLabel.setObjectName("homeLabel")
        homeLabel.setAlignment(Qt.AlignCenter)
        layout.addWidget(homeLabel)

        # Espace avant les boutons
        layout.addSpacing(20)

        # Boutons centrés horizontalement
        btn_row = QHBoxLayout()
        btn_row.setSpacing(32)
        btn_row.addStretch()

        # Générer Configuration (Couleur personnalisée, même police que les autres)
        self.configGenerationButton = QPushButton("Générer Configuration")
        self.configGenerationButton.setObjectName("configGenerationButton")
        self.configGenerationButton.setMinimumSize(180, 80)
        self.configGenerationButton.setCursor(Qt.PointingHandCursor)
        self.configGenerationButton.setIconSize(QSize(48, 48))
        btn_row.addWidget(self.configGenerationButton)

        # Connexion SSH (Vert)
        self.sshConnectionButton = QPushButton("Connexion SSH")
        self.sshConnectionButton.setObjectName("sshConnectionButton")
        self.sshConnectionButton.setMinimumSize(180, 80)
        self.sshConnectionButton.setCursor(Qt.PointingHandCursor)
        self.sshConnectionButton.setIconSize(QSize(48, 48))
        btn_row.addWidget(self.sshConnectionButton)

        # Connexion Console (Orange)
        self.consoleConnectionButton = QPushButton("Connexion Console")
        self.consoleConnectionButton.setObjectName("consoleConnectionButton")
        self.consoleConnectionButton.setMinimumSize(180, 80)
        self.consoleConnectionButton.setCursor(Qt.PointingHandCursor)
        self.consoleConnectionButton.setIconSize(QSize(48, 48))
        btn_row.addWidget(self.consoleConnectionButton)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Espace après les boutons
        layout.addSpacing(20)
        
        # Spacer bottom
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        return page
    
    def create_generation_page(self):
        """Create the configuration generation page"""
        page = QWidget()
        
        # Création d'un layout principal pour toute la page
        main_layout = QVBoxLayout(page)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Création du bouton retour en haut de la page (comme dans ssh_connection)
        self.backToHomeFromConfigButton = QPushButton("Retour")
        self.backToHomeFromConfigButton.setObjectName("backToHomeFromConfigButton")
        self.backToHomeFromConfigButton.setMinimumHeight(40)
        main_layout.addWidget(self.backToHomeFromConfigButton)
        
        # Création d'un conteneur pour le contenu de l'onglet
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Placeholder (will be replaced by tabs in ui_main.py)
        self.generationPlaceholder = QLabel()
        self.generationPlaceholder.setAlignment(Qt.AlignCenter)
        self.generationPlaceholder.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        content_layout.addWidget(self.generationPlaceholder)
        
        main_layout.addWidget(content_widget)
        
        return page
    
    def create_ssh_page(self):
        """Create the SSH connection page - all functionality is handled by SSHConnection"""
        # Simply create a SSHConnection instance and pass self for navigation callback
        self.sshConnectionWidget = SSHConnection(self)
        
        # Connecter le bouton de retour au callback de navigation
        # IMPORTANT: Utilisez la méthode set_home_callback pour éviter les connexions en double
        self.sshConnectionWidget.set_home_callback(self.show_home)
        
        # Ces références sont maintenant accessibles directement depuis l'instance SSHConnection
        # Ne créez pas de nouvelles références qui pourraient provoquer des duplications
        
        # Return the SSHConnection widget directly as the page
        return self.sshConnectionWidget
    
    def create_console_page(self):
        """Create the console connection page - all functionality is handled by SerialConnection"""
        # Simply create a SerialConnection instance and pass self for navigation callback
        self.serialConnectionWidget = SerialConnection(self)
        
        # Store references needed for compatibility with other code
        self.backToHomeFromConsoleButton = self.serialConnectionWidget.backToHomeButton
        self.injectConsoleConfigButton = self.serialConnectionWidget.inject_config_button
        
        # Return the SerialConnection widget directly as the page
        return self.serialConnectionWidget
    
    def init_ui(self):
        """Initialize UI components with caching for resources"""
        resources_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources")
        
        # Logo avec cache
        logo_path = os.path.join(resources_dir, "logo", "logo_netops.png")
        if logo_path not in self._resource_cache:
            if os.path.exists(logo_path):
                self._resource_cache[logo_path] = QPixmap(logo_path)
            else:
                self._resource_cache[logo_path] = None
        
        if self._resource_cache[logo_path]:
            self.logoLabel.setPixmap(self._resource_cache[logo_path])
        else:
            self.logoLabel.setText("LOGO")
            self.logoLabel.setStyleSheet("background-color: gray;")
        
        # Icons avec cache
        icon_files = {
            "configGenerationButton": "generer.png",
            "sshConnectionButton": "ssh.png",
            "consoleConnectionButton": "console.png"
        }
        
        for button_name, icon_file in icon_files.items():
            icon_path = os.path.join(resources_dir, icon_file)
            if icon_path not in self._resource_cache:
                if os.path.exists(icon_path):
                    self._resource_cache[icon_path] = QIcon(icon_path)
                else:
                    self._resource_cache[icon_path] = None
            
            if hasattr(self, button_name):
                button = getattr(self, button_name)
                if self._resource_cache[icon_path]:
                    button.setIcon(self._resource_cache[icon_path])
    
    def connect_signals(self):
        """Connect all button signals to their respective slots"""
        # Main menu navigation
        self.configGenerationButton.clicked.connect(self.show_config_generation)
        self.sshConnectionButton.clicked.connect(self.show_ssh_connection)
        self.consoleConnectionButton.clicked.connect(self.show_console_connection)
        
        # Ne plus connecter le bouton de retour ici car cela sera fait dans ui_main.py
        # Le bouton est créé ici mais le signal sera connecté dans ui_main.py
        # self.backToHomeFromConfigButton.clicked.connect(self.show_home)
    
    # Navigation methods
    def show_home(self):
        self.stackedWidget.setCurrentIndex(0)
    
    def show_config_generation(self):
        self.stackedWidget.setCurrentIndex(1)
    
    def show_ssh_connection(self):
        self.stackedWidget.setCurrentIndex(2)
    
    def show_console_connection(self):
        self.stackedWidget.setCurrentIndex(3)
    
# For testing the UI directly
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec_())
    self.consolePage = self.create_console_page()
    self.stackedWidget.addWidget(self.consolePage)
    self.stackedWidget.setCurrentWidget(self.consolePage)
    
# For testing the UI directly
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = HomePage()
    window.show()
    sys.exit(app.exec_())
