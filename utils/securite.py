"""
Module de sécurité simplifié - Fonctionnalités de licence supprimées
"""
import sys
import platform
import os
from PyQt5.QtCore import QTimer

class SecurityManager:
    """Version simplifiée du gestionnaire de sécurité"""
    
    def __init__(self, window=None, force_license=False, debug_mode=False, offline_mode=False):
        """Initialisation simplifiée du gestionnaire de sécurité"""
        self.window = window
        self.security_timer = None
    
    def check_license(self):
        """Fonction simplifiée qui simule une licence permanente"""
        expiry_date = "2099-12-31"
        features = ["all"]
        
        # Mise à jour de l'interface si la fenêtre est disponible
        if self.window and hasattr(self.window, 'update_license_info'):
            self.window.update_license_info(expiry_date)
            
        return expiry_date, features

    def start_security_checks(self):
        """Ne fait rien - Les vérifications de sécurité sont désactivées"""
        pass
        
def get_hardware_id():
    """Fonction simplifiée pour la compatibilité avec le code existant"""
    import hashlib
    import uuid
    
    # Utiliser une valeur fixe pour éviter tout suivi
    hardware_info = [str(uuid.uuid4())]  # Générer un UUID aléatoire
    
    # Concaténer les infos et générer un hash
    concatenated = ''.join(str(item).strip() for item in hardware_info).encode()
    hardware_id = hashlib.sha256(concatenated).hexdigest()
    
    return hardware_id

def get_license_path():
    """Retourne le chemin du fichier de licence selon l'environnement"""
    app_name = "NetOpsKit"
    if platform.system() == 'Windows':
        return os.path.join(os.environ.get('APPDATA', os.path.expanduser("~")), app_name, ".license")
    else:
        return os.path.join(os.path.expanduser("~"), f".{app_name.lower()}", ".license")

# Fonctions simplifiées pour la compatibilité
def verify_license_key(license_key):
    """Version simplifiée qui retourne toujours vrai"""
    return True, "2099-12-31", ["all"], "License valid"

def verify_license_key_full(license_key):
    """Version simplifiée qui retourne toujours vrai"""
    return verify_license_key(license_key)