import sys
import os
import platform
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt
from utils.file_utils import get_resource_path
from utils.theme_utils import apply_dark_theme
from ui.modern_dialogs import ModernMessageBox
from ui.main_window import MainWindow

def main():
    try:
        # Initialiser l'application
        app = QApplication(sys.argv)
        app.setAttribute(Qt.AA_EnableHighDpiScaling)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)
        
        app.setApplicationName("NetOpsKit")
        app.setOrganizationName("Varez Network")
        
        # Appliquer le thème sombre amélioré
        apply_dark_theme(app)
        
        # Variable globale pour suivre si le style a été chargé
        app.style_loaded = False

        try:
            # Obtenir le chemin de style avec notre fonction d'utilitaire
            style_path = get_resource_path('resources/style.qss')
            
            if os.path.exists(style_path):
                with open(style_path, 'r', encoding='utf-8') as f:
                    style_sheet = f.read()
                    if style_sheet:
                        print(f"Application du style: {style_path}")
                        app.setStyleSheet(app.styleSheet() + "\n" + style_sheet)
                        app.style_loaded = True
                    else:
                        print("Le fichier de style est vide")
            else:
                print(f"Fichier de style non trouvé: {style_path}")
                
        except Exception as style_error:
            print(f"Erreur lors du chargement de la feuille de style : {style_error}")
        
        # Remplacer la fonction des boîtes de dialogue système standard par nos versions modernes
        original_question = QMessageBox.question
        original_information = QMessageBox.information
        original_warning = QMessageBox.warning
        original_critical = QMessageBox.critical
        
        QMessageBox.question = ModernMessageBox.question
        QMessageBox.information = ModernMessageBox.information
        QMessageBox.warning = ModernMessageBox.warning
        QMessageBox.critical = ModernMessageBox.critical
        
        try:
            window = MainWindow()
            window.show()
                
        except Exception as e:
            print(f"Erreur lors du démarrage de l'application: {e}")
            ModernMessageBox.critical(None, "Erreur de démarrage", f"Impossible de démarrer l'application: {str(e)}")
            return 1

        result = app.exec_()
        
        # Restaurer les fonctions originales de QMessageBox
        QMessageBox.question = original_question
        QMessageBox.information = original_information
        QMessageBox.warning = original_warning
        QMessageBox.critical = original_critical
        
        return result
        
    except Exception as e:
        # Utiliser notre boîte de dialogue personnalisée pour l'erreur
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            ModernMessageBox.critical(None, "Erreur critique", f"Une erreur s'est produite: {str(e)}")
        except:
            QMessageBox.critical(None, "Erreur critique", f"Une erreur s'est produite: {str(e)}")
        return 1

if __name__ == '__main__':
    sys.exit(main())