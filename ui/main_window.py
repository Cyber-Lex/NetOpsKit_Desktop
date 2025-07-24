import datetime
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, 
                           QSizePolicy, QDesktopWidget, QApplication,
                           QMessageBox)
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import Qt, QPoint, QSettings, QPropertyAnimation, QEasingCurve, QTime, QTimer
from ui.custom_titlebar import CustomTitleBar
from ui.modern_dialogs import ModernMessageBox
from utils.securite import SecurityManager
from ui_main import ConfigGeneratorWindow

class MainWindow(QWidget):
    """Fenêtre principale améliorée avec fonctionnalités supplémentaires et effets visuels améliorés"""
    
    def __init__(self):
        super().__init__()
        # Constantes pour le redimensionnement
        self.RESIZE_BORDER = 8  # Zone de redimensionnement légèrement plus large
        self.resizing = False
        self.resize_edge = None
        self.resize_cursor_active = False
        self.resize_start_pos = QPoint(0, 0)
        self.resize_start_geometry = self.geometry()
        
        # Optimisations des attributs de fenêtre
        self.setAttribute(Qt.WA_DontCreateNativeAncestors)
        self.setAttribute(Qt.WA_StyledBackground)
        
        self.security_manager = SecurityManager(self)
        self.init_ui()
        
        expiry_date, features = self.security_manager.check_license()
        self.update_license_info(expiry_date)
        self.license_expiry = expiry_date
        self.license_features = features
        
        # Désactiver les mises à jour pendant l'initialisation
        self.setUpdatesEnabled(False)
        self.load_settings()
        
        if hasattr(self, 'content') and hasattr(self.content, 'set_features'):
            self.content.set_features(features)
        
        self.setup_animations()
        # Réactiver les mises à jour
        self.setUpdatesEnabled(True)
        
        # Utiliser un timer pour adapter la taille après initialisation complète
        QTimer.singleShot(100, self.delayed_size_adaptation)
        QTimer.singleShot(200, self.show_welcome_message)

    def delayed_size_adaptation(self):
        """Ajuste la taille et position de la fenêtre après l'initialisation"""
        if not self.isMaximized() and not self.isFullScreen():
            self.adapt_to_screen_fullscreen()

    def setup_animations(self):
        """Configure les animations pour la fenêtre principale"""
        # Animation de fondu pour l'apparition
        self.setWindowOpacity(0.0)  # Commencer invisible
        
        self.fade_in = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in.setDuration(250)
        self.fade_in.setStartValue(0.0)
        self.fade_in.setEndValue(1.0)
        self.fade_in.setEasingCurve(QEasingCurve.OutCubic)
        
        # Exécuter l'animation d'apparition avec un délai
        QTimer.singleShot(100, self.fade_in.start)
        
    def init_ui(self):
        """Initialise l'interface utilisateur avec une mise en page responsive et des effets visuels améliorés"""
        # Configuration de base de la fenêtre
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)  # Permet les coins arrondis
        self.setMinimumSize(800, 600)
        
        # Mise en page principale sans marge pour l'ombre
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Conteneur principal sans bordure
        self.container = QFrame()
        self.container.setObjectName("mainContainer")
        self.container.setFrameShape(QFrame.NoFrame)
        self.container.setStyleSheet("""
            #mainContainer {
                background-color: #2c3e50;
                border-radius: 8px;
            }
        """)
        
        # Layout du conteneur
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        # Barre de titre personnalisée
        self.title_bar = CustomTitleBar(self)
        container_layout.addWidget(self.title_bar)
        
        # Contenu principal
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Créer et configurer le widget principal
        self.content = ConfigGeneratorWindow()
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Ajouter le contenu au layout
        self.content_layout.addWidget(self.content)
        container_layout.addWidget(self.content_widget, 1)
        
        # Ajouter le conteneur au layout principal
        main_layout.addWidget(self.container)

    def update_status(self, message=None):
        """Méthode conservée pour compatibilité"""
        pass
        
    def show_welcome_message(self):
        """Affiche un message de bienvenue moderne"""
        # Version moderne du message de bienvenue (décommentez pour activer)
        # QTimer.singleShot(500, lambda: ModernMessageBox.information(
        #     self, "Bienvenue", "Bienvenue dans NetOpsKit, votre application est prête à être utilisée."))
        pass
        
    def load_settings(self):
        """Charge les paramètres enregistrés"""
        settings = QSettings("VotreEntreprise", "GenerateurConfiguration")
        geometry = settings.value("geometry")
        state = settings.value("windowState")
        
        if geometry:
            self.restoreGeometry(geometry)
        if state:
            is_maximized = bool(int(state))
            if is_maximized:
                self.showMaximized()
                self.title_bar.maximize_button.button_type = "restore"
                self.title_bar.maximize_button.update()
                
    def adapt_to_screen_fullscreen(self):
        """Adapte la fenêtre en plein écran en respectant la barre des tâches"""
        desktop = QDesktopWidget()
        available_geometry = desktop.availableGeometry()  # Obtient la géométrie sans la barre des tâches
        self.setGeometry(available_geometry)
        self.showMaximized()
        
    def save_settings(self):
        """Enregistre les paramètres"""
        settings = QSettings("VotreEntreprise", "GenerateurConfiguration")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("windowState", int(self.isMaximized()))
        
    def closeEvent(self, event):
        """Gère l'événement de fermeture avec confirmation et nettoyage"""
        # Utiliser la boîte de dialogue moderne
        reply = ModernMessageBox.question(
            self, 
            'Confirmation de fermeture',
            'Êtes-vous sûr de vouloir quitter l\'application?'
        )
        
        if reply == QMessageBox.Yes:
            # Animation de fermeture
            self.fade_out = QPropertyAnimation(self, b"windowOpacity")
            self.fade_out.setDuration(200)
            self.fade_out.setStartValue(1.0)
            self.fade_out.setEndValue(0.0)
            self.fade_out.setEasingCurve(QEasingCurve.OutCubic)
            self.fade_out.finished.connect(lambda: self._finish_close(event))
            self.fade_out.start()
            event.ignore()  # On ignorera l'événement jusqu'à la fin de l'animation
        else:
            event.ignore()
    
    def _finish_close(self, event):
        """Termine proprement la fermeture après l'animation"""
        self.security_manager.cleanup()
        self.save_settings()
        # Maintenant on peut accepter l'événement de fermeture
        QApplication.instance().quit()
            
    def resizeEvent(self, event):
        """Gère le redimensionnement de la fenêtre"""
        super().resizeEvent(event)
        
        # Mise à jour des styles pour les coins arrondis quand maximisé
        if self.isMaximized():
            self.container.setStyleSheet("""
                #mainContainer {
                    background-color: #2c3e50;
                    border-radius: 0px;
                }
            """)
            self.title_bar.setStyleSheet("""
                CustomTitleBar {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #1a2530, stop:1 #2c3e50);
                    border-top-left-radius: 0px;
                    border-top-right-radius: 0px;
                    border-bottom: 1px solid #3498db;
                }
            """)
        else:
            self.container.setStyleSheet("""
                #mainContainer {
                    background-color: #2c3e50;
                    border-radius: 8px;
                }
            """)
            self.title_bar.setStyleSheet("""
                CustomTitleBar {
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                                           stop:0 #1a2530, stop:1 #2c3e50);
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border-bottom: 1px solid #3498db;
                }
            """)
        
        # Assurez-vous que le contenu s'adapte correctement après un court délai
        QTimer.singleShot(10, self.update_content_geometry)
    
    def update_content_geometry(self):
        """Mise à jour de la géométrie du contenu avec délai pour éviter les problèmes de timing"""
        if hasattr(self, 'content') and hasattr(self, 'container') and hasattr(self, 'title_bar'):
            content_height = max(0, self.container.height() - self.title_bar.height())
            self.content.setGeometry(0, 0, self.container.width(), content_height)

    def showEvent(self, event):
        """Gère l'affichage initial de la fenêtre"""
        super().showEvent(event)
        # Mettre à jour la géométrie du contenu au premier affichage
        QTimer.singleShot(50, self.update_content_geometry)

    def update_maximize_button_state(self, is_maximized):
        """Met à jour l'état visuel du bouton maximize/restore"""
        if hasattr(self, 'title_bar') and hasattr(self.title_bar, 'maximize_button'):
            if is_maximized:
                self.title_bar.maximize_button.button_type = "restore"
            else:
                self.title_bar.maximize_button.button_type = "maximize"
            self.title_bar.maximize_button.update()
            self.title_bar.maximize_button.setToolTip("Restaurer" if is_maximized else "Agrandir")

    def paintEvent(self, event):
        """Optimisation du rendu"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        # Rendu optimisé
        if not self.isMaximized():
            painter.fillRect(self.rect(), QColor(44, 62, 80, 230))

    def mousePressEvent(self, event):
        """Gère les événements de clic de souris pour le redimensionnement"""
        if not self.isMaximized():
            edge = self.get_resize_edge(event.pos())
            if edge:
                self.resizing = True
                self.resize_edge = edge
                self.resize_start_pos = event.globalPos()
                self.resize_start_geometry = self.geometry()
                self.setCursor(self.get_resize_cursor(edge))
                event.accept()
                return
        event.ignore()

    def mouseMoveEvent(self, event):
        """Gère le redimensionnement fluide de la fenêtre avec précision améliorée"""
        if not self.isMaximized():
            # Gestion du redimensionnement actif
            if self.resizing and self.resize_edge:
                delta = event.globalPos() - self.resize_start_pos
                new_geometry = self.resize_start_geometry
                min_width = max(self.minimumWidth(), 400)
                min_height = max(self.minimumHeight(), 300)
                
                # Facteur d'accélération pour un redimensionnement plus dynamique
                accel_factor = 1.0
                
                # Calcul des nouvelles dimensions avec précision améliorée
                if 'right' in self.resize_edge:
                    new_width = max(min_width, new_geometry.width() + int(delta.x() * accel_factor))
                    new_geometry.setWidth(new_width)
                if 'left' in self.resize_edge:
                    max_left_movement = new_geometry.width() - min_width
                    left_movement = min(max_left_movement, delta.x())
                    new_geometry.setLeft(new_geometry.left() + left_movement)
                if 'bottom' in self.resize_edge:
                    new_height = max(min_height, new_geometry.height() + int(delta.y() * accel_factor))
                    new_geometry.setHeight(new_height)
                if 'top' in self.resize_edge:
                    max_top_movement = new_geometry.height() - min_height
                    top_movement = min(max_top_movement, delta.y())
                    new_geometry.setTop(new_geometry.top() + top_movement)
                
                # Application de la nouvelle géométrie
                self.setGeometry(new_geometry)
                return
            
            # Gestion du survol des bords avec feedback visuel amélioré
            edge = self.get_resize_edge(event.pos())
            if edge:
                cursor = self.get_resize_cursor(edge)
                if self.cursor().shape() != cursor:
                    self.setCursor(cursor)
                    self.resize_cursor_active = True
            elif self.resize_cursor_active and not self.resizing:
                self.setCursor(Qt.ArrowCursor)
                self.resize_cursor_active = False
        
        event.ignore()

    def mouseReleaseEvent(self, event):
        """Termine le redimensionnement avec retour fluide du curseur"""
        was_resizing = self.resizing
        
        if self.resizing:
            self.resizing = False
            self.resize_edge = None
            
            # Force la mise à jour de la géométrie du contenu
            QTimer.singleShot(10, self.update_content_geometry)
        
        # Vérifier si on est toujours sur un bord avant de restaurer le curseur
        edge = self.get_resize_edge(event.pos())
        if was_resizing and not edge:
            # Animation subtile de transition du curseur
            QTimer.singleShot(50, lambda: self.setCursor(Qt.ArrowCursor))
        elif edge:
            # Maintenir le curseur de redimensionnement si on est sur un bord
            self.setCursor(self.get_resize_cursor(edge))
        
        event.ignore()

    def get_resize_cursor(self, edge):
        """Retourne le curseur approprié pour le bord avec priorité améliorée"""
        cursors = {
            'left': Qt.SizeHorCursor,
            'right': Qt.SizeHorCursor,
            'top': Qt.SizeVerCursor,
            'bottom': Qt.SizeVerCursor,
            'top-left': Qt.SizeFDiagCursor,
            'bottom-right': Qt.SizeFDiagCursor,
            'top-right': Qt.SizeBDiagCursor,
            'bottom-left': Qt.SizeBDiagCursor
        }
        return cursors.get(edge, Qt.ArrowCursor)

    def get_resize_edge(self, pos):
        """Détermine si la position est sur un bord de redimensionnement avec précision améliorée"""
        if self.isMaximized():
            return None
            
        x = pos.x()
        y = pos.y()
        width = self.width()
        height = self.height()
        border = self.RESIZE_BORDER
        
        # Détection précise des coins avec priorité
        if x <= border and y <= border:
            return 'top-left'
        elif x >= width - border and y <= border:
            return 'top-right'
        elif x <= border and y >= height - border:
            return 'bottom-left'
        elif x >= width - border and y >= height - border:
            return 'bottom-right'
        
        # Détection des bords
        elif y <= border:
            return 'top'
        elif y >= height - border:
            return 'bottom'
        elif x <= border:
            return 'left'
        elif x >= width - border:
            return 'right'
            
        return None

    def enterEvent(self, event):
        """Réinitialise le curseur lors de l'entrée dans la fenêtre"""
        if not self.isMaximized() and not self.resizing:
            self.setCursor(Qt.ArrowCursor)
        super().enterEvent(event)

    def update_license_info(self, expiry_date=None):
        """Méthode conservée pour compatibilité mais ne fait plus rien"""
        pass
