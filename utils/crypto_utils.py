import base64
import hashlib
import hmac
import json
import datetime
import time
import random
import re
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend  # <--- ajout
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT = b'$\xbcQ\x15\x8aN\x16\xeb\x00\xe6\xce\xac\xcb\xb9\xdc!'
APP_SECRET = "c8e7142b5b3a6f0e7d2c1a3b5d9e8f7a"

_cache = {
    'encryption_key': None,
    'fernet': None
}

def get_encryption_key():
    if _cache['encryption_key'] is None:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=SALT,
            iterations=10000,
            backend=default_backend()  # <--- spécifié
        )
        derived_key = kdf.derive(APP_SECRET.encode())
        key = base64.urlsafe_b64encode(derived_key)
        _cache['encryption_key'] = key
        _cache['fernet'] = Fernet(key)
    return _cache['encryption_key']

def get_fernet():
    if _cache['fernet'] is None:
        get_encryption_key()
    return _cache['fernet']

def create_short_code(license_data):
    """Crée un code court unique à partir des données de licence"""
    # Créer une string unique à partir des données essentielles
    hw_id = license_data.get('hwid', '')
    exp_date = license_data.get('exp', '')
    features = '-'.join(sorted(license_data.get('feat', [])))
    unique_str = f"{hw_id}|{exp_date}|{features}|{APP_SECRET}"
    
    # Générer un hash unique
    hash_obj = hashlib.sha256(unique_str.encode())
    hash_digest = hash_obj.digest()
    
    # Convertir en format XXXX-XXXX-XXXX-XXXX
    # Utiliser un alphabet limité pour éviter les caractères ambigus
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    chars = []
    for i in range(16):
        # Utiliser des modulos pour garantir des indices valides
        index = hash_digest[i] % len(alphabet)
        chars.append(alphabet[index])
    
    # Former le code avec des tirets
    return f"{chars[0]}{chars[1]}{chars[2]}{chars[3]}-{chars[4]}{chars[5]}{chars[6]}{chars[7]}-{chars[8]}{chars[9]}{chars[10]}{chars[11]}-{chars[12]}{chars[13]}{chars[14]}{chars[15]}"

def generate_license(hardware_id, days, features=None):
    """Génère une licence avec les informations fournies"""
    if features is None:
        features = ["basic"]
    elif isinstance(features, str):
        features = [f.strip() for f in features.split(",") if f.strip()]
    
    # Calculer la date d'expiration
    expiry_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Créer les données de licence
    license_data = {
        "hwid": hardware_id,
        "exp": expiry_date,
        "feat": features,
        "ts": int(time.time()),
        "rand": random.randint(10000, 99999)
    }
    
    # Créer une signature pour éviter la falsification
    serialized = json.dumps(license_data, sort_keys=True)
    signature = hmac.new(
        APP_SECRET.encode(),
        serialized.encode(),
        hashlib.sha256
    ).hexdigest()
    license_data["sig"] = signature
    
    # Chiffrer les données complètes
    try:
        encrypted = get_fernet().encrypt(json.dumps(license_data).encode())
        # Encoder en base64 pour une licence complète
        full_license = base64.urlsafe_b64encode(encrypted).decode()
        
        # Générer le code court directement à partir des données
        short_license = create_short_code(license_data)
        
        # Enregistrer le mapping entre code court et licence complète
        save_license_mapping(short_license, license_data)
        
        return short_license, full_license, expiry_date
    except Exception as e:
        print(f"Erreur lors du chiffrement de la licence: {e}")
        raise

def save_license_mapping(short_code, license_data):
    """Sauvegarde le mapping entre code court et données de licence"""
    # Cette fonction stocke en mémoire le mapping pour la session actuelle
    # Vous pourriez la rendre persistante en stockant dans un fichier chiffré si nécessaire
    if not hasattr(save_license_mapping, "mappings"):
        save_license_mapping.mappings = {}
    
    save_license_mapping.mappings[short_code] = license_data

def get_license_from_short_code(short_code):
    """Récupère les données de licence à partir du code court"""
    if not hasattr(save_license_mapping, "mappings"):
        return None
    
    return save_license_mapping.mappings.get(short_code)

def verify_license(license_key, hardware_id):
    """Vérifie si une licence est valide"""
    try:
        if not license_key or not hardware_id:
            return False, None, None, "Données de licence incomplètes"
            
        # Détecter le format (court ou complet)
        is_short_format = len(license_key) == 19 and license_key.count('-') == 3
        
        if is_short_format:
            # Format court (XXXX-XXXX-XXXX-XXXX)
            # Vérifier d'abord si c'est dans notre mapping en mémoire
            license_data = get_license_from_short_code(license_key)
            
            if license_data:
                print("Licence trouvée dans le cache mémoire")
                # Vérifier le hardware ID
                if license_data["hwid"] != hardware_id:
                    return False, None, None, "La licence n'est pas valide pour cet ordinateur"
                
                # Vérifier la date d'expiration
                expiry_date = license_data["exp"]
                expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
                if expiry < datetime.datetime.now().date():
                    return False, None, None, "Licence expirée"
                
                # Licence valide
                days_left = (expiry - datetime.datetime.now().date()).days
                features = license_data.get("feat", ["basic"])
                return True, expiry_date, features, f"Licence valide ({days_left} jours restants)"
            
            # Si le code court n'est pas dans notre mapping, essayer de reconstituer la licence
            print("Licence non trouvée dans le cache, tentative de reconstruction")
            return reconstruct_license_from_short_code(license_key, hardware_id)
            
        else:
            # Format complet (clé base64)
            try:
                # Déchiffrer les données
                encrypted_data = base64.urlsafe_b64decode(license_key.strip())
                decrypted_data = get_fernet().decrypt(encrypted_data).decode()
                license_data = json.loads(decrypted_data)
                
                # Vérifier la signature pour détecter la manipulation
                signature = license_data.pop("sig", "")
                serialized = json.dumps(license_data, sort_keys=True)
                expected_signature = hmac.new(
                    APP_SECRET.encode(),
                    serialized.encode(),
                    hashlib.sha256
                ).hexdigest()
                
                if signature != expected_signature:
                    return False, None, None, "Signature invalide, licence corrompue"
                
                # Vérifier le hardware ID
                if license_data["hwid"] != hardware_id:
                    return False, None, None, "La licence n'est pas valide pour cet ordinateur"
                
                # Vérifier la date d'expiration
                expiry_date = license_data["exp"]
                expiry = datetime.datetime.strptime(expiry_date, "%Y-%m-%d").date()
                if expiry < datetime.datetime.now().date():
                    return False, None, None, "Licence expirée"
                
                # Licence valide
                days_left = (expiry - datetime.datetime.now().date()).days
                features = license_data.get("feat", ["basic"])
                
                # Sauvegarder le mapping pour une utilisation future
                short_code = create_short_code(license_data)
                save_license_mapping(short_code, license_data)
                
                return True, expiry_date, features, f"Licence valide ({days_left} jours restants)"
                
            except Exception as e:
                print(f"Erreur lors de la vérification du format complet: {e}")
                return False, None, None, f"Erreur de licence: {e}"
    
    except Exception as e:
        print(f"Exception non gérée lors de la vérification: {e}")
        return False, None, None, f"Erreur lors de la vérification: {e}"

def reconstruct_license_from_short_code(short_code, hardware_id):
    """Essaie de reconstituer et valider les données de licence à partir d'un code court"""
    # Obtenir les ensembles de fonctionnalités possibles pour tester
    feature_sets = get_possible_feature_sets()
    
    # Récupérer les dates d'expiration possibles
    expiry_dates = get_possible_expiry_dates()
    
    print(f"Tentative de validation du code court: {short_code}")
    print(f"Test de {len(feature_sets)} ensembles de fonctionnalités et {len(expiry_dates)} dates possibles")
    
    # Essayer différentes combinaisons de dates d'expiration et fonctionnalités
    for exp_date in expiry_dates:
        for features in feature_sets:
            # Construire un ensemble de données de licence potentiel
            license_data = {
                "hwid": hardware_id,
                "exp": exp_date,
                "feat": features,
                "ts": int(time.time()),
                "rand": 12345  # Valeur arbitraire pour la cohérence
            }
            
            # Calculer le code court pour ces données
            generated_code = create_short_code(license_data)
            
            # Si le code généré correspond au code fourni
            if generated_code == short_code:
                print(f"Code court validé avec succès: {exp_date}, fonctionnalités: {features}")
                
                # Vérifier la date d'expiration
                expiry = datetime.datetime.strptime(exp_date, "%Y-%m-%d").date()
                if expiry < datetime.datetime.now().date():
                    return False, None, None, "Licence expirée"
                
                # Licence valide
                days_left = (expiry - datetime.datetime.now().date()).days
                
                # Sauvegarder dans le mapping pour les futures références
                save_license_mapping(short_code, license_data)
                
                return True, exp_date, features, f"Licence valide ({days_left} jours restants)"
    
    # Si aucune combinaison n'a fonctionné
    print(f"Échec de validation du code court: {short_code}")
    return False, None, None, "Code de licence invalide ou non reconnu"

def get_possible_feature_sets():
    """Retourne les combinaisons de fonctionnalités possibles pour la vérification"""
    # Ensemble de base des combinaisons courantes
    base_sets = [
        ["basic"],
        ["basic", "premium"],
        ["premium"],
        ["standard"],
        ["basic", "advanced"],
        ["all"]
    ]
    
    # Essayer d'importer les combinaisons spécifiques de l'application
    try:
        import sys
        import importlib.util
        spec = importlib.util.find_spec('licence')
        if spec is not None:
            licence_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(licence_module)
            if hasattr(licence_module, 'get_features_for_verification'):
                additional_sets = licence_module.get_features_for_verification()
                # Combiner sans dupliquer
                for feat_set in additional_sets:
                    if feat_set not in base_sets:
                        base_sets.append(feat_set)
    except Exception as e:
        print(f"Erreur lors de l'importation des fonctionnalités: {e}")
    
    return base_sets

def get_possible_expiry_dates():
    """Génère des dates d'expiration possibles à tester de manière optimisée"""
    # Utiliser un cache pour éviter de recalculer les mêmes dates à chaque appel
    if hasattr(get_possible_expiry_dates, 'cache'):
        # Vérifier si le cache est encore valide (recalculer une fois par jour)
        cache_time = getattr(get_possible_expiry_dates, 'cache_time', 0)
        if time.time() - cache_time < 86400:  # 24 heures
            return getattr(get_possible_expiry_dates, 'cache')
    
    dates = []
    today = datetime.datetime.now().date()
    
    # Périodes courantes de licence (en jours)
    common_periods = [0, 1, 3, 7, 14, 30, 60, 90, 180, 365, 730, 1095, 1460, 1825]
    
    # Ajouter les périodes communes à partir d'aujourd'hui
    for days in common_periods:
        future_date = today + datetime.timedelta(days=days)
        dates.append(future_date.strftime("%Y-%m-%d"))
    
    # Ajouter des dates spéciales (fin d'année, début d'année)
    current_year = today.year
    for year in range(current_year, current_year + 6):
        dates.append(f"{year}-12-31")
        dates.append(f"{year}-01-01")
    
    # Dates spécifiques pour les licences annuelles à partir de dates connues
    base_dates = ["2023-01-01", "2023-07-01", "2024-01-01", "2024-07-01"]
    for base_date in base_dates:
        base = datetime.datetime.strptime(base_date, "%Y-%m-%d").date()
        for years in range(5):
            dates.append((base + datetime.timedelta(days=365*years)).strftime("%Y-%m-%d"))
    
    # Éliminer les doublons et trier
    unique_dates = sorted(list(set(dates)))
    
    # Stocker dans le cache
    get_possible_expiry_dates.cache = unique_dates
    get_possible_expiry_dates.cache_time = time.time()
    
    return unique_dates

# Fonction de cache LRU pour les vérifications de licence
def lru_cache_license(max_size=128):
    """
    Implémente un cache simple LRU (Least Recently Used) pour les vérifications de licence
    
    Args:
        max_size: Taille maximale du cache
    """
    cache = {}
    access_order = []
    
    def decorator(func):
        def wrapper(license_key, hardware_id):
            # Créer une clé de cache qui combine license_key et hardware_id
            cache_key = f"{license_key}:{hardware_id}"
            
            # Vérifier si résultat en cache
            if cache_key in cache:
                # Déplacer cette entrée à la fin de l'ordre d'accès (la plus récente)
                if cache_key in access_order:
                    access_order.remove(cache_key)
                access_order.append(cache_key)
                return cache[cache_key]
            
            # Appeler la fonction originale
            result = func(license_key, hardware_id)
            
            # Stocker le résultat dans le cache
            cache[cache_key] = result
            access_order.append(cache_key)
            
            # Si le cache dépasse la taille maximale, supprimer l'élément le moins récemment utilisé
            if len(cache) > max_size:
                oldest_key = access_order.pop(0)
                if oldest_key in cache:
                    del cache[oldest_key]
                    
            return result
        return wrapper
    return decorator

# Appliquer le cache LRU à la fonction verify_license
verify_license_original = verify_license
verify_license = lru_cache_license(max_size=64)(verify_license_original)
