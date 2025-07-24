import os
import sys
import logging  # <--- ajout

logger = logging.getLogger(__name__)

def get_resource_path(relative_path):
    """Obtient le chemin absolu des ressources, fonctionne en mode développement et après compilation"""
    try:
        if getattr(sys, 'frozen', False):
            # Si nous sommes dans un exe
            base_path = sys._MEIPASS  # Utilise le chemin spécial PyInstaller
        else:
            # Si nous sommes dans un script
            base_path = os.path.dirname(os.path.abspath(__file__))
            # Remonter d'un niveau car nous sommes dans le dossier utils
            base_path = os.path.dirname(base_path)
        
        result = os.path.join(base_path, relative_path)
        logger.debug(f"Chemin résolu: {result}")
        return result
    except Exception as e:
        logger.error(f"Erreur get_resource_path({relative_path}): {e}")
        raise
