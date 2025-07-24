from PyQt5.QtCore import QThread, pyqtSignal
import traceback
import logging
import time
import jinja2

logger = logging.getLogger(__name__)

class BaseConfigWorker(QThread):
    """Worker pour la génération de configuration de base."""
    config_generated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)

    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self.is_canceled = False

    def run(self):
        try:
            self.progress_updated.emit(10)
            logger.info("Démarrage de la génération de la configuration de base")
            
            # Validation des paramètres
            if not self.params.get('hostname') or not self.params.get('enable_secret'):
                raise ValueError("Les paramètres de base sont requis (hostname et enable_secret)")
            
            self.progress_updated.emit(30)
            # Génération de la configuration
            config = self._generate_config()
            
            if self.is_canceled:
                logger.info("Génération de configuration annulée")
                return
                
            self.progress_updated.emit(100)
            self.config_generated.emit(config)
            logger.info("Configuration de base générée avec succès")
            
        except Exception as e:
            error_msg = f"Erreur de génération: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            self.error_occurred.emit(error_msg)

    def cancel(self):
        """Permet d'annuler la génération en cours"""
        self.is_canceled = True
        logger.info("Demande d'annulation de la génération de configuration")
        
    def _generate_config(self):
        """Génère la configuration de base en utilisant Jinja2"""
        # Amélioration avec un template Jinja2 plus complet
        template_str = """
! Configuration générée le {{ timestamp }}
! Configuration de base pour {{ hostname }}
!
enable
configure terminal
!
hostname {{ hostname }}
enable secret {{ enable_secret }}
!
{% if username %}
username {{ username }} privilege 15 secret {{ user_secret|default('cisco') }}
{% endif %}
!
no ip domain-lookup
ip domain-name example.com
!
line con 0
 logging synchronous
 login local
 exec-timeout 0 0
!
line vty 0 4
 logging synchronous
 login local
 exec-timeout 0 0
!
{% if banner %}
banner motd ^
{{ banner }}
^
{% endif %}
!
end
"""
        # Ajoute le timestamp et valeurs par défaut
        params = self.params.copy()
        params['timestamp'] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        template = jinja2.Template(template_str)
        return template.render(**params)

class BasculeConfigWorker(QThread):
    """Worker pour la génération de configuration de bascule."""
    config_generated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)

    def __init__(self, bgp_params, stations, acls, routes, parent=None):
        super().__init__(parent)
        self.bgp_params = bgp_params
        self.stations = stations
        self.acls = acls
        self.routes = routes
        self.is_canceled = False

    def run(self):
        try:
            self.progress_updated.emit(10)
            self.status_updated.emit("Validation des paramètres BGP...")
            
            # Validation plus stricte des paramètres
            required_params = [
                ('as_number', "Le numéro d'AS BGP est requis"),
                ('router_id', "L'identifiant du routeur est requis"),
            ]
            
            for param, error_msg in required_params:
                if not self.bgp_params.get(param):
                    raise ValueError(error_msg)
            
            if not self.stations:
                raise ValueError("Au moins une station doit être configurée")
                
            self.progress_updated.emit(30)
            self.status_updated.emit("Génération des configurations des stations...")
            
            # Génération des configurations par étapes
            config = self._generate_bgp_config()
            if self.is_canceled:
                return
                
            self.progress_updated.emit(50)
            
            config += self._generate_acl_config()
            if self.is_canceled:
                return
                
            self.progress_updated.emit(70)
            
            config += self._generate_route_config()
            if self.is_canceled:
                return
                
            self.status_updated.emit("Configuration générée avec succès")
            self.progress_updated.emit(100)
            self.config_generated.emit(config)
            logger.info("Configuration de bascule générée avec succès")

        except Exception as e:
            error_msg = f"Erreur de génération: {str(e)}"
            logger.error(f"{error_msg}\n{traceback.format_exc()}")
            self.error_occurred.emit(error_msg)

    def cancel(self):
        """Permet d'annuler la génération en cours"""
        self.is_canceled = True
        
    def _generate_bgp_config(self):
        """Génère une configuration BGP complète utilisant Jinja2"""
        template_str = """
! ---------------------------------------
! Configuration BGP
! ---------------------------------------
router bgp {{ as_number }}
 bgp router-id {{ router_id }}
 bgp log-neighbor-changes
{% for neighbor in neighbors %}
 neighbor {{ neighbor.ip }} remote-as {{ neighbor.remote_as }}
 {% if neighbor.description %}
 neighbor {{ neighbor.ip }} description {{ neighbor.description }}
 {% endif %}
 {% if neighbor.password %}
 neighbor {{ neighbor.ip }} password {{ neighbor.password }}
 {% endif %}
{% endfor %}
{% for network in networks %}
 network {{ network.address }} mask {{ network.mask }}
{% endfor %}
"""
        template = jinja2.Template(template_str)
        
        # Préparation des données pour le template
        data = {
            'as_number': self.bgp_params.get('as_number'),
            'router_id': self.bgp_params.get('router_id', '0.0.0.0'),
            'neighbors': self.stations,
            'networks': self._parse_networks()
        }
        
        return template.render(data)

    def _parse_networks(self):
        """Transforme les réseaux en format utilisable par le template"""
        networks = []
        raw_networks = self.bgp_params.get('networks', [])
        
        for net in raw_networks:
            # Parse CIDR or x.x.x.x mask y.y.y.y format
            parts = net.split()
            if len(parts) == 3 and parts[1].lower() == 'mask':
                networks.append({'address': parts[0], 'mask': parts[2]})
            elif '/' in net:
                # Parse CIDR notation
                address, prefix = net.split('/')
                # Convert prefix to mask
                mask_bits = int(prefix)
                mask_int = (0xffffffff >> (32 - mask_bits)) << (32 - mask_bits)
                mask = f"{mask_int >> 24 & 0xff}.{mask_int >> 16 & 0xff}.{mask_int >> 8 & 0xff}.{mask_int & 0xff}"
                networks.append({'address': address, 'mask': mask})
                
        return networks

    def _generate_acl_config(self):
        """Génère la configuration des ACLs"""
        template_str = """
! ---------------------------------------
! Configuration ACL
! ---------------------------------------
{% for acl in acls %}
ip access-list extended {{ acl.name }}
 {% for rule in acl.rules %}
 {{ rule }}
 {% endfor %}
{% endfor %}
"""
        template = jinja2.Template(template_str)
        return template.render({'acls': self.acls})

    def _generate_route_config(self):
        """Génère la configuration des routes"""
        template_str = """
! ---------------------------------------
! Configuration Routes
! ---------------------------------------
{% for route in routes %}
ip route {{ route.network }} {{ route.mask }} {{ route.next_hop }}{% if route.distance %} {{ route.distance }}{% endif %}{% if route.track %} track {{ route.track }}{% endif %}{% if route.name %} name {{ route.name }}{% endif %}
{% endfor %}
"""
        template = jinja2.Template(template_str)
        return template.render({'routes': self.routes})

class CMEConfigWorker(QThread):
    """Worker pour la génération de configuration CME."""
    config_generated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)

    def __init__(self, telephony_params, network_params, dial_peer_params, firmware_params, parent=None):
        super().__init__(parent)
        self.telephony_params = telephony_params
        self.network_params = network_params
        self.dial_peer_params = dial_peer_params
        self.firmware_params = firmware_params

    def run(self):
        try:
            self.progress_updated.emit(10)
            self.status_updated.emit("Validation des paramètres de téléphonie...")
            
            # Validation des paramètres essentiels
            if not self.telephony_params.get('max_dn'):
                raise ValueError("Le nombre maximum de DN est requis")

            self.progress_updated.emit(25)
            self.status_updated.emit("Génération de la configuration de téléphonie...")
            config = self._generate_telephony_config()

            self.progress_updated.emit(50)
            self.status_updated.emit("Génération de la configuration réseau...")
            config += self._generate_network_config()

            self.progress_updated.emit(75)
            self.status_updated.emit("Génération de la configuration dial-peer...")
            config += self._generate_dial_peer_config()

            self.progress_updated.emit(90)
            self.status_updated.emit("Génération de la configuration firmware...")
            config += self._generate_firmware_config()

            self.progress_updated.emit(100)
            self.status_updated.emit("Configuration générée avec succès")
            self.config_generated.emit(config)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def _generate_telephony_config(self):
        # Implémentation de la génération de config téléphonie
        return "! Telephony Configuration\n"

    def _generate_network_config(self):
        # Implémentation de la génération de config réseau
        return "! Network Configuration\n"

    def _generate_dial_peer_config(self):
        # Implémentation de la génération de config dial-peer
        return "! Dial-Peer Configuration\n"

    def _generate_firmware_config(self):
        # Implémentation de la génération de config firmware
        return "! Firmware Configuration\n"
