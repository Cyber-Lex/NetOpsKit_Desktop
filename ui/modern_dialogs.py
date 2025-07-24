from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QPushButton, QMessageBox, QFrame, QSpacerItem,
                           QGraphicsDropShadowEffect)
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint

class ModernMessageBox(QDialog):
    """Boîte de dialogue moderne avec animation et effets visuels améliorés"""
    
    # Types de messages
    INFO = 0
    WARNING = 1
    CRITICAL = 2
    QUESTION = 3
    
    def __init__(self, parent=None, title="Message", text="", message_type=INFO):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.result_value = QMessageBox.Cancel
        
        # Variables pour gérer le déplacement de la fenêtre
        self.dragging = False
        self.drag_position = QPoint()
        
        # Configurer le type de message
        self.message_type = message_type
        self.setWindowTitle(title)
        
        # Créer et configurer l'interface
        self.setup_ui(title, text)
        
        # Ajouter l'animation d'apparition
        self.setup_animations()
        
    def setup_ui(self, title, text):
        """Configure l'interface utilisateur de la boîte de dialogue"""
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Conteneur principal avec ombre et bordure
        self.container = QFrame(self)
        self.container.setObjectName("modernMessageBox")
        self.container.setFrameShape(QFrame.NoFrame)
        
        # Couleurs selon le type de message
        if self.message_type == self.INFO:
            bg_color = "#2c3e50"
            accent_color = "#3498db"
            icon_text = "ℹ️"
        elif self.message_type == self.WARNING:
            bg_color = "#2c3e50"
            accent_color = "#f39c12"
            icon_text = "⚠️"
        elif self.message_type == self.CRITICAL:
            bg_color = "#2c3e50"
            accent_color = "#e74c3c"
            icon_text = "❌"
        else:  # QUESTION
            bg_color = "#2c3e50"
            accent_color = "#2ecc71"
            icon_text = "❓"
            
        # Appliquer le style au conteneur
        self.container.setStyleSheet(f"""
            #modernMessageBox {{
                background-color: {bg_color};
                border: 1px solid {accent_color};
                border-radius: 8px;
            }}
        """)
        
        # Ombre portée
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.container.setGraphicsEffect(shadow)
        
        # Layout du conteneur
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(15, 15, 15, 15)
        
        # Entête (titre et bouton fermer)
        header_layout = QHBoxLayout()
        
        # Icône
        icon_label = QLabel(icon_text)
        icon_label.setStyleSheet(f"""
            font-size: 24px;
            margin-right: 10px;
        """)
        
        # Titre
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {accent_color};
            font-weight: bold;
            font-size: 16px;
        """)
        
        # Espaceur
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Bouton fermer (pour les messages non-question)
        if self.message_type != self.QUESTION:
            close_button = QPushButton("×")
            close_button.setFlat(True)
            close_button.setFixedSize(30, 30)
            close_button.setStyleSheet(f"""
                QPushButton {{
                    color: #ecf0f1;
                    background-color: transparent;
                    border: none;
                    font-size: 20px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    color: {accent_color};
                }}
                QPushButton:pressed {{
                    color: #bdc3c7;
                }}
            """)
            close_button.clicked.connect(self.reject)
            header_layout.addWidget(close_button)
        
        container_layout.addLayout(header_layout)
        
        # Ligne de séparation
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(f"background-color: {accent_color}; height: 1px;")
        container_layout.addWidget(separator)
        
        # Contenu (message)
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setStyleSheet("""
            color: #ecf0f1;
            font-size: 13px;
            margin: 20px 0;
            min-width: 300px;
        """)
        container_layout.addWidget(text_label)
        
        # Boutons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Style commun des boutons
        button_style = f"""
            QPushButton {{
                background-color: #34495e;
                color: #ecf0f1;
                border: 1px solid {accent_color};
                border-radius: 4px;
                padding: 6px 20px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {accent_color};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background-color: #2c3e50;
            }}
        """
        
        # Boutons selon le type de message
        if self.message_type == self.QUESTION:
            # Bouton Oui
            yes_button = QPushButton("Oui")
            yes_button.setStyleSheet(button_style)
            yes_button.clicked.connect(self.accept_clicked)
            
            # Bouton Non
            no_button = QPushButton("Non")
            no_button.setStyleSheet(button_style)
            no_button.clicked.connect(self.reject_clicked)
            
            button_layout.addWidget(yes_button)
            button_layout.addWidget(no_button)
        else:
            # Bouton OK
            ok_button = QPushButton("OK")
            ok_button.setStyleSheet(button_style)
            ok_button.clicked.connect(self.accept)
            
            button_layout.addWidget(ok_button)
        
        container_layout.addLayout(button_layout)
        
        main_layout.addWidget(self.container)
    
    def setup_animations(self):
        """Configure les animations d'apparition"""
        # Animation d'opacité
        self.opacity_animation = QPropertyAnimation(self, b"windowOpacity")
        self.opacity_animation.setDuration(150)
        self.opacity_animation.setStartValue(0)
        self.opacity_animation.setEndValue(1)
        self.opacity_animation.setEasingCurve(QEasingCurve.OutCubic)
        
    def showEvent(self, event):
        """Exécuté lors de l'affichage de la fenêtre"""
        super().showEvent(event)
        # Démarrer l'animation
        self.opacity_animation.start()
        
    def accept_clicked(self):
        """Réponse Oui/OK"""
        self.result_value = QMessageBox.Yes
        self.accept()
    
    def reject_clicked(self):
        """Réponse Non/Annuler"""
        self.result_value = QMessageBox.No
        self.reject()
    
    def mousePressEvent(self, event):
        """Capture l'événement de clic de souris pour permettre le déplacement"""
        if event.button() == Qt.LeftButton:
            # Vérifier si le clic est dans la zone de l'en-tête (partie supérieure de la fenêtre)
            # On considère que l'en-tête est en haut de la fenêtre, sur les ~40 premiers pixels
            if event.pos().y() < 40:
                self.dragging = True
                self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
                event.accept()
    
    def mouseMoveEvent(self, event):
        """Déplace la fenêtre lorsque l'utilisateur fait glisser la souris"""
        if event.buttons() == Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def mouseReleaseEvent(self, event):
        """Arrête le déplacement de la fenêtre quand le bouton de la souris est relâché"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
            event.accept()
    
    @classmethod
    def information(cls, parent, title, text):
        """Affiche une boîte d'information et retourne le résultat"""
        dialog = cls(parent, title, text, cls.INFO)
        dialog.exec_()
        return dialog.result_value
    
    @classmethod
    def warning(cls, parent, title, text):
        """Affiche une boîte d'avertissement et retourne le résultat"""
        dialog = cls(parent, title, text, cls.WARNING)
        dialog.exec_()
        return dialog.result_value
    
    @classmethod
    def critical(cls, parent, title, text):
        """Affiche une boîte d'erreur critique et retourne le résultat"""
        dialog = cls(parent, title, text, cls.CRITICAL)
        dialog.exec_()
        return dialog.result_value
    
    @classmethod
    def question(cls, parent, title, text):
        """Affiche une boîte de question et retourne le résultat
        
        Args:
            parent: Widget parent
            title: Titre de la boîte de dialogue
            text: Texte de la question
            
        Returns:
            QMessageBox.Yes ou QMessageBox.No
        """
        dialog = cls(parent, title, text, cls.QUESTION)
        dialog.exec_()
        return dialog.result_value
