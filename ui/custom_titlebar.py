from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QSpacerItem
from PyQt5.QtCore import Qt, QPoint, QTime, QTimer
from ui.custom_controls import WindowButton

class CustomTitleBar(QWidget):
    """Barre de titre personnalisée améliorée avec effets visuels et fonctionnalités supplémentaires"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()
        self.start = QPoint(0, 0)
        self.pressing = False
        self.setFixedHeight(40)  # Hauteur légèrement augmentée pour un look plus moderne
        
    def setup_ui(self):
        """Configure l'interface utilisateur de la barre de titre"""
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 0, 15, 0)  # Marges augmentées pour un meilleur espacement
        self.layout.setSpacing(6)
        
        # Logo (peut être remplacé par une icône réelle)
        self.logo_label = QLabel("🔧")
        self.logo_label.setStyleSheet("color: #3498db; font-size: 18px; font-weight: bold;")
        
        # Titre de l'application
        self.title_label = QLabel("NetOpsKit")
        self.title_label.setStyleSheet("color: #ecf0f1; font-weight: bold; font-size: 14px;")
        
        # Conteneur pour les boutons de fenêtre
        self.window_buttons = QWidget()
        self.window_buttons_layout = QHBoxLayout(self.window_buttons)
        self.window_buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.window_buttons_layout.setSpacing(6)  # Espacement augmenté entre les boutons
        
        # Boutons de contrôle avec QPainter
        self.minimize_button = self.create_title_button("minimize", self.parent.showMinimized, "#f1c40f")
        self.maximize_button = self.create_title_button("maximize", self.toggle_maximize, "#2ecc71")
        self.close_button = self.create_title_button("close", self.parent.close, "#e74c3c")
        
        # Ajouter les boutons au conteneur
        self.window_buttons_layout.addWidget(self.minimize_button)
        self.window_buttons_layout.addWidget(self.maximize_button)
        self.window_buttons_layout.addWidget(self.close_button)
        
        # Ajouter les widgets au layout principal
        self.layout.addWidget(self.logo_label)
        self.layout.addSpacing(8)
        self.layout.addWidget(self.title_label)
        self.layout.addStretch(1)  # Séparateur élastique
        self.layout.addWidget(self.window_buttons)
        
        # Appliquer un style à la barre de titre avec dégradé
        self.setStyleSheet("""
            CustomTitleBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #1a2530, stop:1 #2c3e50);
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                border-bottom: 1px solid #3498db;
            }
        """)
    
    # Cette méthode est maintenue pour compatibilité mais ne fait plus rien
    def set_license_info(self, text):
        """Cette méthode est conservée pour compatibilité mais ne fait plus rien"""
        pass
        
    def create_title_button(self, button_type, callback, hover_color):
        """Crée un bouton pour la barre de titre avec QPainter"""
        button = WindowButton(button_type, callback, hover_color)
        return button

    def mousePressEvent(self, event):
        """Gère le clic sur la barre de titre pour déplacer la fenêtre"""
        if event.button() == Qt.LeftButton:
            self.start = self.mapToGlobal(event.pos())
            self.pressing = True

    def mouseMoveEvent(self, event):
        """Gère le déplacement de la fenêtre"""
        if self.pressing and not self.parent.isMaximized():
            end = self.mapToGlobal(event.pos())
            movement = end - self.start
            
            # Simple window movement without velocity calculations
            self.parent.move(self.parent.pos() + movement)
            self.start = end

    def mouseReleaseEvent(self, event):
        """Gère le relâchement du clic"""
        self.pressing = False
    
    def mouseDoubleClickEvent(self, event):
        """Double-clic pour maximiser/restaurer"""
        if event.button() == Qt.LeftButton:
            self.toggle_maximize()

    def toggle_maximize(self):
        """Bascule entre l'état maximisé et normal avec animation visuelle améliorée"""
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_button.button_type = "maximize"
            self.maximize_button.setToolTip("Agrandir")
        else:
            self.parent.showMaximized()
            self.maximize_button.button_type = "restore"
            self.maximize_button.setToolTip("Restaurer")
        
        # Forcer le rafraîchissement du bouton
        self.maximize_button.update()
        
        # Mise à jour du statut dans la barre d'état
        if hasattr(self.parent, 'update_status'):
            self.parent.update_status()
