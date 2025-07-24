from PyQt5.QtWidgets import QPushButton
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor
from PyQt5.QtCore import Qt, QPoint, QRectF

class WindowButton(QPushButton):
    """Bouton personnalisé dessiné avec QPainter pour les contrôles de fenêtre"""
    
    def __init__(self, button_type, callback, hover_color):
        super().__init__()
        self.button_type = button_type  # "minimize", "maximize", "close" ou "restore"
        self.setFixedSize(34, 34)  # Légèrement plus grands pour un meilleur toucher
        self.clicked.connect(callback)
        self.hover_color = QColor(hover_color)
        self.is_hovered = False
        self.is_pressed = False
        self.setToolTip(self._get_tooltip())
        
        # Appliquer un style de base
        self.setStyleSheet("""
            WindowButton {
                background-color: transparent;
                border: none;
                border-radius: 17px;
            }
        """)
    
    def _get_tooltip(self):
        """Retourne le texte d'infobulle pour le bouton"""
        tooltips = {
            "minimize": "Réduire",
            "maximize": "Agrandir",
            "restore": "Restaurer",
            "close": "Fermer"
        }
        return tooltips.get(self.button_type, "")
    
    def enterEvent(self, event):
        """Gère l'entrée du curseur dans la zone du bouton"""
        self.is_hovered = True
        self.update()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Gère la sortie du curseur de la zone du bouton"""
        self.is_hovered = False
        self.is_pressed = False
        self.update()
        super().leaveEvent(event)
        
    def mousePressEvent(self, event):
        """Gère l'appui du bouton de la souris"""
        if event.button() == Qt.LeftButton:
            self.is_pressed = True
            self.update()
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Gère le relâchement du bouton de la souris"""
        self.is_pressed = False
        self.update()
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        """Dessine le bouton avec QPainter"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Dessiner le fond lors du survol ou appui
        if self.is_pressed:
            # Couleur plus foncée pendant l'appui
            darker_color = self.hover_color.darker(150)
            painter.setBrush(QBrush(darker_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(2, 2, 30, 30))
        elif self.is_hovered:
            # Couleur normale pendant le survol
            painter.setBrush(QBrush(self.hover_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRectF(2, 2, 30, 30))
        
        # Dessiner l'icône du bouton
        pen_color = QColor("#ffffff") if self.is_hovered or self.is_pressed else QColor("#ecf0f1")
        painter.setPen(QPen(pen_color, 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        
        if self.button_type == "minimize":
            # Dessiner une ligne horizontale pour minimiser
            painter.drawLine(QPoint(11, 17), QPoint(23, 17))
            
        elif self.button_type == "maximize":
            # Dessiner un rectangle pour maximiser
            painter.drawRect(QRectF(11, 11, 12, 12))
            
        elif self.button_type == "restore":
            # Dessiner deux rectangles décalés pour restaurer
            painter.drawRect(QRectF(10, 13, 10, 10))
            painter.drawLine(QPoint(13, 13), QPoint(13, 10))
            painter.drawLine(QPoint(13, 10), QPoint(23, 10))
            painter.drawLine(QPoint(23, 10), QPoint(23, 13))
            
        elif self.button_type == "close":
            # Dessiner une croix pour fermer
            painter.drawLine(QPoint(11, 11), QPoint(23, 23))
            painter.drawLine(QPoint(23, 11), QPoint(11, 23))
