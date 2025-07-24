import platform
from PyQt5.QtGui import QPalette, QColor, QFont
from PyQt5.QtCore import Qt

def apply_dark_theme(app):
    """Applique un thème sombre moderne à l'application avec effets visuels améliorés"""
    app.setStyle("Fusion")
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # Police moderne - utilisez une police système standard
    if platform.system() == "Windows":
        font_family = "Segoe UI"
    elif platform.system() == "Darwin":  # macOS
        font_family = "SF Pro Text"
    else:  # Linux et autres
        font_family = "Sans-Serif"
    
    app_font = QFont(font_family, 10)
    app.setFont(app_font)
    
    # Palette de couleurs sombre améliorée
    palette = QPalette()
    bg_color = QColor("#2c3e50")
    text_color = QColor("#ecf0f1")
    accent_color = QColor("#3498db")
    
    for role in [QPalette.Window, QPalette.Base, QPalette.AlternateBase]:
        palette.setColor(role, bg_color)
    
    for role in [QPalette.WindowText, QPalette.Text, QPalette.ButtonText]:
        palette.setColor(role, text_color)
    
    palette.setColor(QPalette.Highlight, accent_color)
    palette.setColor(QPalette.HighlightedText, text_color)
    
    app.setPalette(palette)
