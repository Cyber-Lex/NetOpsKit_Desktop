import sys
import os
import socket
import threading
import time
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, Optional, Tuple, Any

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QPushButton, QTextEdit, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QSpinBox, QComboBox, QProgressBar, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, QThreadPool, QObject, pyqtSignal, QTimer 
from PyQt5.QtGui import QBrush, QColor

from worker.tftp_worker import TFTPWorker, TFTPServerSignals

# Tentative d'importation de netifaces pour obtenir les interfaces réseau
try:
    import netifaces
    NETIFACES_AVAILABLE = True
except ImportError:
    NETIFACES_AVAILABLE = False

# -------------------- CONFIGURATION DU LOGGING -------------------- #
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])
logger = logging.getLogger("TFTPServer")

# -------------------- CONSTANTES DU PROTOCOLE TFTP -------------------- #
OPCODE_RRQ = 1    # Read request
OPCODE_WRQ = 2    # Write request
OPCODE_DATA = 3   # Data packet
OPCODE_ACK = 4    # Acknowledgment
OPCODE_ERROR = 5  # Error
OPCODE_OACK = 6   # Option Acknowledgment (RFC2347)

# TFTP Error codes
ERROR_NOT_DEFINED = 0
ERROR_FILE_NOT_FOUND = 1
ERROR_ACCESS_VIOLATION = 2
ERROR_DISK_FULL = 3
ERROR_ILLEGAL_OPERATION = 4
ERROR_UNKNOWN_TRANSFER_ID = 5
ERROR_FILE_EXISTS = 6
ERROR_NO_SUCH_USER = 7

# Pour Windows, on limite la taille de bloc négociée à 1024 octets.
MAX_ALLOWED_BLKSIZE = 1024 if sys.platform.startswith('win') else 8192

# -------------------- CLASSE DE SIGNALS -------------------- #
class TFTPServerSignals(QObject):
    log_message = pyqtSignal(str, str)     # niveau, message
    client_connected = pyqtSignal(str, dict)   # client_id, infos
    client_disconnected = pyqtSignal(str)
    transfer_started = pyqtSignal(str, dict)   # client_id, infos transfert
    transfer_updated = pyqtSignal(str, dict)   # client_id, infos transfert
    transfer_completed = pyqtSignal(str, bool) # client_id, succès

# -------------------- CLASSE DU SERVEUR TFTP -------------------- #
class TFTPServer:
    def __init__(self, interface='0.0.0.0', port=69, block_size=8192, root_dir='./tftp_root', timeout=5.0):
        self.interface = interface
        self.port = port
        # Sur Windows, forcer la taille de bloc à 1024 par défaut
        self.block_size = 1024 if sys.platform.startswith('win') else block_size
        self.root_dir = os.path.abspath(root_dir)
        self.timeout = timeout
        self.clients: Dict[str, Dict[str, Any]] = {}
        self.transfers: Dict[str, Dict[str, Any]] = defaultdict(dict)
        self.lock = threading.Lock()
        self.running = False
        self.sock: Optional[socket.socket] = None
        self.signals = TFTPServerSignals()

        # Options TFTP supportées
        self.support_options = True
        self.default_options = {
            'blksize': str(self.block_size),
            'timeout': str(timeout)
        }
        
        self.statistics = {
            'total_transfers': 0,
            'successful_transfers': 0,
            'failed_transfers': 0,
            'bytes_uploaded': 0,
            'bytes_downloaded': 0,
            'start_time': time.time()
        }
        
        os.makedirs(self.root_dir, exist_ok=True)
        self.is_windows = sys.platform.startswith('win')
        logger.setLevel(logging.INFO)
        
        logger.info(f"Server initialized with root directory: {self.root_dir}")
        logger.info(f"Platform detected: {'Windows' if self.is_windows else 'Unix-like'}")
        logger.info(f"Server parameters: Interface={interface}, Port={port}, Block Size={block_size}, Timeout={timeout}s")
    
    def debug_socket_buffers(self):
        """Affiche les tailles actuelles des tampons de socket pour le débogage"""
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            current_recv = test_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            current_send = test_socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
            logger.info(f"Current socket buffers - Receive: {current_recv} bytes, Send: {current_send} bytes")
            test_sizes = [8192, 16384, 32768, 65536, 131072, 262144]
            max_recv = current_recv
            max_send = current_send
            for size in test_sizes:
                try:
                    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, size)
                    actual_recv = test_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                    if actual_recv > max_recv:
                        max_recv = actual_recv
                    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, size)
                    actual_send = test_socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
                    if actual_send > max_send:
                        max_send = actual_send
                except Exception as e:
                    logger.info(f"Error testing buffer size {size}: {e}")
                    break
            logger.info(f"Max socket buffers - Receive: {max_recv} bytes, Send: {max_send} bytes")
            test_socket.close()
            return max_recv, max_send
        except Exception as e:
            logger.error(f"Error debugging socket buffers: {e}")
            return 65536, 65536

    def start(self):
        """Démarre le serveur TFTP"""
        try:
            self.running = True
            if self.is_windows:
                max_recv, max_send = self.debug_socket_buffers()
            else:
                max_recv, max_send = 65536, 65536
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, max_recv)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, max_send)
            actual_recv = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            actual_send = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
            logger.info(f"Configured socket buffers - Receive: {actual_recv} bytes, Send: {actual_send} bytes")
            
            bind_attempts = 0
            max_attempts = 5
            while bind_attempts < max_attempts:
                try:
                    self.sock.bind((self.interface, self.port))
                    break
                except OSError as e:
                    if e.errno == 10048:
                        bind_attempts += 1
                        wait_time = bind_attempts * 2
                        logger.warning(f"Port {self.port} is busy, waiting {wait_time} seconds (attempt {bind_attempts}/{max_attempts})")
                        time.sleep(wait_time)
                    else:
                        raise
            if bind_attempts >= max_attempts:
                raise OSError(f"Failed to bind to port {self.port} after {max_attempts} attempts")
            
            logger.info(f"Server started on {self.interface}:{self.port}")
            self.signals.log_message.emit("INFO", f"Server started on {self.interface}:{self.port}")
            self.sock.setblocking(False)
            
            while self.running:
                try:
                    import select
                    ready, _, _ = select.select([self.sock], [], [], 0.5)
                    if ready:
                        try:
                            # Lecture : on reçoit au maximum block_size + 4 octets
                            data, client_addr = self.sock.recvfrom(self.block_size + 4)
                            client_thread = threading.Thread(
                                target=self.handle_client,
                                args=(data, client_addr),
                                daemon=True
                            )
                            client_thread.start()
                        except (ConnectionResetError, OSError) as e:
                            logger.error(f"Socket receive error: {str(e)}")
                            continue
                    time.sleep(0.01)
                except Exception as e:
                    if self.running:
                        logger.error(f"Server loop error: {str(e)}")
                        continue
                    else:
                        break
        except Exception as e:
            logger.error(f"Failed to start server: {str(e)}")
            self.signals.log_message.emit("ERROR", f"Failed to start server: {str(e)}")
            self.running = False
            raise
        finally:
            logger.info("Server main loop exited")
    
    def stop(self):
        """Arrête le serveur TFTP"""
        logger.info("Stopping server...")
        self.running = False
        time.sleep(0.5)
        if self.sock:
            try:
                dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                dummy_socket.sendto(b'', ('127.0.0.1', self.port))
                dummy_socket.close()
                self.sock.close()
                self.sock = None
            except Exception as e:
                logger.error(f"Error while closing server socket: {str(e)}")
        logger.info("Server stopped")
        self.signals.log_message.emit("INFO", "Server stopped")
    
    def handle_client(self, data: bytes, client_addr: Tuple[str, int]):
        """Gère les requêtes clients TFTP"""
        client_ip, client_port = client_addr
        client_id = f"{client_ip}:{client_port}"
        try:
            if len(data) < 2:
                self.send_error(client_addr, ERROR_ILLEGAL_OPERATION, "Invalid packet size")
                return
            opcode = int.from_bytes(data[:2], 'big')
            if opcode not in [OPCODE_RRQ, OPCODE_WRQ, OPCODE_DATA, OPCODE_ACK, OPCODE_ERROR]:
                logger.warning(f"Invalid opcode {opcode} from {client_id}")
                self.send_error(client_addr, ERROR_ILLEGAL_OPERATION, f"Illegal TFTP operation: {opcode}")
                return

            with self.lock:
                if client_id not in self.clients:
                    self.clients[client_id] = {
                        'ip': client_ip,
                        'port': client_port,
                        'last_seen': datetime.now(),
                        'active': True
                    }
                    self.signals.client_connected.emit(client_id, self.clients[client_id])
                else:
                    self.clients[client_id]['last_seen'] = datetime.now()
                    self.clients[client_id]['active'] = True
            
            if opcode == OPCODE_RRQ:
                filename, mode, options = self.parse_tftp_request(data[2:])
                logger.info(f"Received READ request from {client_id} for file: {filename}")
                filepath = os.path.join(self.root_dir, filename)
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                if options and 'tsize' in options:
                    options['tsize'] = str(file_size)
                self.signals.log_message.emit("INFO", f"Received READ request from {client_id} for file: {filename}")
                self.record_transfer(client_id, filename, 'download', file_size)
                thread = threading.Thread(
                    target=self.handle_read_request,
                    args=(client_addr, filename, mode, options),
                    daemon=True
                )
                thread.start()
            elif opcode == OPCODE_WRQ:
                filename, mode, options = self.parse_tftp_request(data[2:])
                logger.info(f"Received WRITE request from {client_id} for file: {filename}")
                file_size = int(options.get('tsize', 0)) if options else 0
                self.signals.log_message.emit("INFO", f"Received WRITE request from {client_id} for file: {filename}")
                self.record_transfer(client_id, filename, 'upload', file_size)
                thread = threading.Thread(
                    target=self.handle_write_request,
                    args=(client_addr, filename, mode, options),
                    daemon=True
                )
                thread.start()
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {str(e)}")
            self.send_error(client_addr, ERROR_NOT_DEFINED, str(e))
            self.signals.transfer_completed.emit(client_id, False)

    def parse_tftp_request(self, data: bytes) -> Tuple[str, str, Dict[str, str]]:
        """Extrait le nom de fichier, le mode et les options supportées (blksize, timeout, tsize)."""
        try:
            parts = data.split(b'\x00')
            if len(parts) < 2:
                raise ValueError("Invalid TFTP request format")
            filename = parts[0].decode('utf-8')
            mode = parts[1].decode('utf-8').lower()
            filename = os.path.normpath(filename).lstrip('/')
            if mode not in ['netascii', 'octet', 'mail']:
                logger.warning(f"Unsupported mode: {mode}, using octet")
                mode = 'octet'
            valid_options = {"blksize", "timeout", "tsize"}
            options = {}
            i = 2
            while i < len(parts) - 1:
                if parts[i] and parts[i+1]:
                    try:
                        key = parts[i].decode('utf-8').lower()
                        value = parts[i+1].decode('utf-8')
                        if key in valid_options:
                            if key == 'blksize':
                                # Limiter la taille des blocs sur Windows
                                requested_size = int(value)
                                if sys.platform.startswith('win'):
                                    value = str(min(requested_size, MAX_ALLOWED_BLKSIZE))
                                    logger.info(f"Adjusting block size from {requested_size} to {value} for Windows compatibility")
                            options[key] = value
                            logger.info(f"Option negotiation: {key}={value}")
                        else:
                            logger.info(f"Ignoring unsupported option: {key}={value}")
                    except Exception as e:
                        logger.warning(f"Error parsing option: {e}")
                    i += 2
            return filename, mode, options
        except Exception as e:
            logger.error(f"Error parsing TFTP request: {str(e)}")
            raise ValueError(f"Invalid TFTP request format: {str(e)}")

    def handle_read_request(self, client_addr: Tuple[str, int], filename: str, mode: str, options: Dict[str, str] = None):
        """Traite une demande de lecture (download) d'un fichier"""
        client_ip, client_port = client_addr 
        client_id = f"{client_ip}:{client_port}"
        filepath = os.path.join(self.root_dir, filename)
        
        # Vérification d'accès et existence du fichier
        if not os.path.abspath(filepath).startswith(self.root_dir):
            logger.warning(f"Access violation attempt from {client_id}: {filename}")
            self.send_error(client_addr, ERROR_ACCESS_VIOLATION, "Access violation")
            return
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            logger.warning(f"File not found: {filepath}")
            self.send_error(client_addr, ERROR_FILE_NOT_FOUND, "File not found")
            return
        
        # Préparation des options de transfert
        if options is None:
            options = {}
        negotiated_options = {}
        
        # SOLUTION CLÉE: Limiter la taille du bloc à une valeur sûre pour éviter les erreurs Windows
        safe_blksize = 1024 if self.is_windows else 8192
        
        if self.support_options and options:
            if 'blksize' in options:
                try:
                    requested_blksize = int(options['blksize'])
                    if self.is_windows:
                        logger.warning(f"Client requested blksize {requested_blksize}, but Windows has buffer limitations")
                        logger.warning(f"Using safe blksize of {safe_blksize} to avoid WinError 10040")
                        negotiated_options['blksize'] = str(safe_blksize)
                    else:
                        negotiated_options['blksize'] = options['blksize']
                    logger.info(f"Option negotiation: blksize={negotiated_options['blksize']}")
                except ValueError:
                    negotiated_options['blksize'] = str(safe_blksize)
            if 'timeout' in options:
                negotiated_options['timeout'] = options['timeout']
            if 'tsize' in options and options['tsize'] == '0' and os.path.exists(filepath):
                negotiated_options['tsize'] = str(os.path.getsize(filepath))
                logger.info(f"File size (tsize): {negotiated_options['tsize']} bytes")
        
        requested_blksize = int(negotiated_options.get('blksize', safe_blksize))
        
        # Création du socket de transfert
        transfer_socket = None
        try:
            transfer_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Configuration des tampons pour le socket de transfert (512KB)
            try:
                buffer_size = 524288  # 512 KB
                transfer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size)
                transfer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, buffer_size)
                actual_recv = transfer_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                actual_send = transfer_socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)
                logger.info(f"Transfer socket buffers - Receive: {actual_recv} bytes, Send: {actual_send} bytes")
            except Exception as e:
                logger.warning(f"Could not set socket buffer sizes: {e}")
            
            transfer_socket.bind((self.interface, 0))
            transfer_socket.settimeout(self.timeout)
            _, transfer_port = transfer_socket.getsockname()
            logger.info(f"Starting RRQ transfer to {client_id} from port {transfer_port}")
            
            # Envoi de l'OACK si des options négociées sont présentes
            if negotiated_options:
                logger.info(f"Sending OACK to {client_id} with options: {negotiated_options}")
                packet = bytearray()
                packet.extend(OPCODE_OACK.to_bytes(2, 'big'))
                for key, value in negotiated_options.items():
                    packet.extend(key.encode('utf-8') + b'\x00')
                    packet.extend(value.encode('utf-8') + b'\x00')
                oack_acknowledged = False
                retry_count = 0
                max_retries = 5
                while not oack_acknowledged and retry_count < max_retries:
                    try:
                        transfer_socket.sendto(packet, client_addr)
                        transfer_socket.settimeout(self.timeout)
                        response, addr = transfer_socket.recvfrom(4)
                        if addr != client_addr:
                            logger.warning(f"Received response from unexpected address: {addr}")
                            continue
                        if len(response) < 4:
                            logger.warning(f"Received packet too small: {len(response)} bytes")
                            continue
                        resp_opcode = int.from_bytes(response[:2], 'big')
                        if resp_opcode == OPCODE_ACK:
                            block_num = int.from_bytes(response[2:4], 'big')
                            if block_num == 0:
                                logger.info(f"Client {client_id} acknowledged options with ACK 0")
                                oack_acknowledged = True
                            else:
                                logger.warning(f"Expected ACK 0, got ACK {block_num}")
                        elif resp_opcode == OPCODE_ERROR:
                            error_code = int.from_bytes(response[2:4], 'big')
                            error_msg = response[4:].split(b'\x00')[0].decode('utf-8', errors='replace')
                            logger.error(f"Client rejected options with error {error_code}: {error_msg}")
                            logger.info("Falling back to standard TFTP (no options)")
                            requested_blksize = 512  # Taille par défaut du TFTP standard 
                            negotiated_options = {}
                            oack_acknowledged = True
                        else:
                            logger.warning(f"Expected ACK or ERROR, got opcode {resp_opcode}")
                    except socket.timeout:
                        retry_count += 1
                        logger.warning(f"Timeout waiting for OACK acknowledgment, retry {retry_count}/{max_retries}")
                    except Exception as e:
                        logger.error(f"Error in OACK handshake: {str(e)}")
                        raise
                if not oack_acknowledged:
                    raise Exception("Failed to negotiate options - max retries exceeded")
            
            # Envoi du fichier
            with open(filepath, 'rb') as f:
                file_size = os.path.getsize(filepath)
                # Stocker la taille du fichier dans le transfert pour le calcul de progression
                with self.lock:
                    if client_id in self.transfers:
                        self.transfers[client_id]['file_size'] = file_size
                block_number = 1
                bytes_sent = 0
                start_time = time.time()
                while self.running:
                    data_chunk = f.read(requested_blksize)
                    if not data_chunk:
                        break
                    
                    packet = bytearray()
                    packet.extend(OPCODE_DATA.to_bytes(2, 'big'))
                    packet.extend(block_number.to_bytes(2, 'big'))
                    packet.extend(data_chunk)
                    
                    # Tentatives d'envoi pour chaque bloc
                    retries_left = 5
                    while retries_left > 0 and self.running:
                        try:
                            transfer_socket.sendto(packet, client_addr)
                            ack_data, ack_addr = transfer_socket.recvfrom(4)
                            if self._validate_ack(ack_data, ack_addr, client_addr, block_number):
                                bytes_sent += len(data_chunk)
                                self._update_transfer_progress(client_id, bytes_sent, start_time)
                                break  # Passage au bloc suivant
                        except socket.error as e:
                            if self.is_windows and "10040" in str(e):
                                logger.error(f"Windows socket buffer error (10040): {e}")
                                self.send_error(client_addr, ERROR_NOT_DEFINED, str(e))
                                raise Exception(f"Windows buffer overflow error: {e}")
                            retries_left -= 1
                            if retries_left <= 0:
                                logger.error(f"Max retries exceeded for block {block_number}")
                                raise Exception(f"Transfer failed after maximum retries for block {block_number}")
                            logger.warning(f"Socket error, retrying block {block_number} ({5 - retries_left}/5): {e}")
                        except socket.timeout:
                            retries_left -= 1
                            if retries_left <= 0:
                                logger.error(f"Max retries exceeded for block {block_number}")
                                raise Exception(f"Transfer timed out for block {block_number}")
                            logger.warning(f"Timeout, retrying block {block_number} ({5 - retries_left}/5)")
                    if retries_left <= 0:
                        raise Exception(f"Transfer failed after maximum retries for block {block_number}")
                    
                    # Si le bloc est plus petit que la taille demandée, c'est la fin du fichier
                    if len(data_chunk) < requested_blksize:
                        break
                    
                    block_number = (block_number + 1) % 65536
                
                logger.info(f"Transfer completed for {client_id}: {filename}")
                self._complete_transfer(client_id, filename, file_size, True)
        except Exception as e:
            logger.error(f"Error in file transfer to {client_id}: {str(e)}")
            self._handle_transfer_error(client_id, client_addr, str(e))
        finally:
            self._cleanup_transfer(transfer_socket, client_id)

    def _validate_ack(self, ack_data: bytes, ack_addr: Tuple[str, int], client_addr: Tuple[str, int], expected_block: int) -> bool:
        """Valide un ACK reçu"""
        if ack_addr != client_addr:
            logger.warning(f"Received ACK from unexpected address: {ack_addr}")
            return False
        if len(ack_data) < 4:
            logger.warning(f"Received invalid packet size: {len(ack_data)}")
            return False
        opcode = int.from_bytes(ack_data[:2], 'big')
        block = int.from_bytes(ack_data[2:4], 'big')
        return opcode == OPCODE_ACK and block == expected_block

    def _update_transfer_progress(self, client_id: str, bytes_sent: int, start_time: float) -> None:
        """Met à jour la progression du transfert"""
        with self.lock:
            if client_id in self.transfers:
                self.transfers[client_id]['progress'] = bytes_sent
                elapsed = time.time() - start_time
                self.transfers[client_id]['speed'] = bytes_sent / elapsed if elapsed > 0 else 0
                file_size = self.transfers[client_id].get('file_size', 1)
                remaining_bytes = file_size - bytes_sent
                self.transfers[client_id]['remaining_time'] = (remaining_bytes / self.transfers[client_id]['speed']
                                                                if self.transfers[client_id]['speed'] > 0 else -1)
                self.signals.transfer_updated.emit(client_id, self.transfers[client_id])

    def _complete_transfer(self, client_id: str, filename: str, file_size: int, success: bool) -> None:
        """Marque la fin du transfert, met à jour les statistiques et émet le signal de fin"""
        with self.lock:
            if client_id in self.transfers:
                self.transfers[client_id]['completed'] = True
                self.transfers[client_id]['end_time'] = datetime.now()
                if success:
                    self.statistics['successful_transfers'] += 1
                    self.statistics['bytes_downloaded'] += file_size
                else:
                    self.statistics['failed_transfers'] += 1
        self.signals.transfer_completed.emit(client_id, success)

    def _handle_transfer_error(self, client_id: str, client_addr: Tuple[str, int], error_message: str) -> None:
        """Gère une erreur pendant un transfert : envoi d'un paquet ERROR et marquage du transfert comme échoué"""
        self.send_error(client_addr, ERROR_NOT_DEFINED, error_message)
        with self.lock:
            if client_id in self.transfers:
                self.transfers[client_id]['completed'] = True
                self.transfers[client_id]['end_time'] = datetime.now()
        self.signals.transfer_completed.emit(client_id, False)

    def _cleanup_transfer(self, transfer_socket: Optional[socket.socket], client_id: str) -> None:
        """Nettoie et ferme le socket de transfert"""
        if transfer_socket:
            try:
                transfer_socket.close()
            except Exception as e:
                logger.error(f"Error closing transfer socket: {str(e)}")

    def _send_data_safely(self, socket_obj: socket.socket, data: bytes, addr: Tuple[str, int]) -> bool:
        """Envoie des données de manière sécurisée en gérant les erreurs de dépassement du tampon sur Windows"""
        try:
            socket_obj.sendto(data, addr)
            return True
        except OSError as e:
            if self.is_windows and "10040" in str(e):
                logger.warning(f"OSError 10040 - Data size {len(data)} exceeds buffer limit. Attempting safe send.")
                # Réduire la taille du payload à une taille sûre
                safe_size = 512  # taille réduite pour Windows
                if len(data) > 4:  # on garde l'en-tête
                    opcode = int.from_bytes(data[:2], 'big')
                    if opcode == OPCODE_DATA:
                        block_num = int.from_bytes(data[2:4], 'big')
                        reduced_payload = data[4:4+safe_size]
                        reduced_packet = bytearray()
                        reduced_packet.extend(OPCODE_DATA.to_bytes(2, 'big'))
                        reduced_packet.extend(block_num.to_bytes(2, 'big'))
                        reduced_packet.extend(reduced_payload)
                        try:
                            socket_obj.sendto(reduced_packet, addr)
                            logger.info(f"Sent reduced data packet of size {len(reduced_packet)} bytes")
                            return True
                        except Exception as e2:
                            logger.error(f"Failed to send reduced packet: {e2}")
                            return False
                return False
            else:
                raise

    def send_error(self, client_addr: Tuple[str, int], error_code: int, error_msg: str):
        """Envoie un paquet d'erreur au client"""
        try:
            error_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                error_socket.bind((self.interface, 0))
                packet = bytearray()
                packet.extend(OPCODE_ERROR.to_bytes(2, 'big'))
                packet.extend(error_code.to_bytes(2, 'big'))
                packet.extend(error_msg.encode('utf-8'))
                packet.append(0)
                if self._send_data_safely(error_socket, packet, client_addr):
                    logger.error(f"Sent error to {client_addr[0]}:{client_addr[1]}: {error_code} - {error_msg}")
                else:
                    logger.error(f"Failed to send error to {client_addr[0]}:{client_addr[1]}")
            finally:
                error_socket.close()
        except Exception as e:
            logger.error(f"Error sending ERROR packet: {str(e)}")

    def record_transfer(self, client_id: str, filename: str, direction: str, file_size: int):
        """Enregistre un nouveau transfert"""
        with self.lock:
            if client_id not in self.clients:
                ip, port = client_id.split(':')
                self.clients[client_id] = {
                    'ip': ip,
                    'port': int(port),
                    'last_seen': datetime.now(),
                    'active': True
                }
                self.signals.client_connected.emit(client_id, self.clients[client_id])
            else:
                self.clients[client_id]['last_seen'] = datetime.now()
                self.clients[client_id]['active'] = True
            transfer_info = {
                'filename': filename,
                'direction': direction,
                'file_size': file_size,
                'start_time': datetime.now(),
                'last_activity': datetime.now(),
                'progress': 0,
                'completed': False,
                'end_time': None,
                'speed': 0.0,
                'block_size': self.block_size,
                'remaining_time': -1
            }
            self.transfers[client_id] = transfer_info
            self.statistics['total_transfers'] += 1
            self.signals.transfer_started.emit(client_id, transfer_info)

    def get_status(self) -> Dict[str, Any]:
        """Retourne l'état du serveur"""
        with self.lock:
            now = datetime.now()
            inactive_timeout = 300  # 5 minutes
            inactive_clients = [client_id for client_id, client in self.clients.items() 
                                if (now - client['last_seen']).total_seconds() > inactive_timeout]
            for client_id in inactive_clients:
                self.clients[client_id]['active'] = False
                if client_id in self.transfers and not self.transfers[client_id]['completed']:
                    self.transfers[client_id]['completed'] = True
                    self.transfers[client_id]['end_time'] = now
                self.signals.client_disconnected.emit(client_id)
            for client_id, transfer in self.transfers.items():
                if not transfer['completed'] and transfer['progress'] > 0:
                    elapsed = (now - transfer['start_time']).total_seconds()
                    if elapsed > 0:
                        transfer['speed'] = transfer['progress'] / elapsed
            uptime = time.time() - self.statistics.get('start_time', time.time())
            total_bytes = self.statistics.get('bytes_downloaded', 0) + self.statistics.get('bytes_uploaded', 0)
            avg_speed = total_bytes / uptime if uptime > 0 else 0
            return {
                'running': self.running,
                'interface': self.interface,
                'port': self.port,
                'block_size': self.block_size,
                'root_dir': self.root_dir,
                'clients': dict(self.clients),
                'transfers': dict(self.transfers),
                'active_clients': sum(1 for c in self.clients.values() if c['active']),
                'active_transfers': sum(1 for t in self.transfers.values() if not t['completed']),
                'statistics': {
                    'total_transfers': self.statistics.get('total_transfers', 0),
                    'successful_transfers': self.statistics.get('successful_transfers', 0),
                    'failed_transfers': self.statistics.get('failed_transfers', 0),
                    'bytes_downloaded': self.statistics.get('bytes_downloaded', 0),
                    'bytes_uploaded': self.statistics.get('bytes_uploaded', 0),
                    'uptime': uptime,
                    'uptime_str': self.format_uptime(uptime),
                    'average_speed': avg_speed,
                    'average_speed_str': self.format_speed(avg_speed)
                }
            }

    def format_uptime(self, seconds: float) -> str:
        days, remainder = divmod(int(seconds), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        if days > 0:
            return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def format_speed(self, bytes_per_sec: float) -> str:
        if bytes_per_sec < 1024:
            return f"{bytes_per_sec:.1f} B/s"
        elif bytes_per_sec < 1024 * 1024:
            return f"{bytes_per_sec/1024:.1f} KB/s"
        else:
            return f"{bytes_per_sec/(1024*1024):.1f} MB/s"

# -------------------- INTERFACE GRAPHIQUE – TFTP SERVER WIDGET (APPLICATION) -------------------- #
class TFTPServerWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None
        self.worker = None
        self.refresh_interval = 0.2
        self.last_refresh = 0
        self.initUI()
        self.connectSignals()
        self.populateInterfaces()

        default_root = os.path.abspath("./tftp_root")
        self.root_dir_edit.setText(default_root)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refreshStatus)
        self.timer.start(200)

    def initUI(self):
        main_layout = QVBoxLayout(self)

        # Groupe de configuration
        config_group = QGroupBox("Configuration du serveur TFTP")
        config_layout = QFormLayout()

        # Répertoire racine
        root_layout = QHBoxLayout()
        self.root_dir_edit = QLineEdit()
        self.root_dir_edit.setReadOnly(True)
        self.root_dir_edit.setPlaceholderText("Sélectionner le répertoire racine pour les fichiers TFTP")
        self.browse_button = QPushButton("Parcourir...")
        root_layout.addWidget(self.root_dir_edit)
        root_layout.addWidget(self.browse_button)
        config_layout.addRow("Répertoire racine:", root_layout)

        # Port
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(69)
        self.port_spin.setToolTip("Port standard TFTP: 69 (requiert admin) ou utilisez un port > 1024.")
        config_layout.addRow("Port:", self.port_spin)

        # Interface réseau
        self.interface_combo = QComboBox()
        self.interface_combo.setToolTip("Sélectionnez l'interface réseau à utiliser")
        config_layout.addRow("Interface réseau:", self.interface_combo)

        # Adresse IP locale
        self.ip_label = QLabel("0.0.0.0")
        self.ip_label.setStyleSheet("font-weight: bold;")
        config_layout.addRow("Adresse IP locale:", self.ip_label)

        # Statut du serveur
        self.status_label = QLabel("Arrêté")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        config_layout.addRow("Statut:", self.status_label)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Boutons démarrer/arrêter
        buttons_layout = QHBoxLayout()
        self.start_button = QPushButton("Démarrer le serveur")
        self.stop_button = QPushButton("Arrêter le serveur")
        self.stop_button.setEnabled(False)
        buttons_layout.addWidget(self.start_button)
        buttons_layout.addWidget(self.stop_button)
        main_layout.addLayout(buttons_layout)

        # Appliquer des styles aux boutons
        self.applyButtonStyle(self.start_button, "#4CAF50", "#45a049", "#3e8e41")
        self.applyButtonStyle(self.stop_button, "#F44336", "#e57373", "#d32f2f")
        self.applyButtonStyle(self.browse_button, "#607D8B", "#78909C", "#455A64")
        self.clear_log_button = QPushButton("Effacer le journal")
        self.save_log_button = QPushButton("Enregistrer le journal")
        self.applyButtonStyle(self.clear_log_button, "#9E9E9E", "#BDBDBD", "#757575")
        self.applyButtonStyle(self.save_log_button, "#9E9E9E", "#BDBDBD", "#757575")

        # Table des clients connectés
        clients_group = QGroupBox("Clients connectés")
        clients_layout = QVBoxLayout()
        self.clients_table = QTableWidget(0, 3)
        self.clients_table.setHorizontalHeaderLabels(["Adresse IP", "Dernière activité", "Fichiers"])
        self.clients_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.clients_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.clients_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.clients_table.setAlternatingRowColors(True)
        clients_layout.addWidget(self.clients_table)
        clients_group.setLayout(clients_layout)
        main_layout.addWidget(clients_group)

        # Table des transferts actifs
        transfers_group = QGroupBox("Transferts actifs")
        transfers_layout = QVBoxLayout()
        self.transfers_table = QTableWidget(0, 6)
        self.transfers_table.setHorizontalHeaderLabels(["Fichier", "Client", "Progression", "Statut", "Type", "Temps restant"])
        self.transfers_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.transfers_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.transfers_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.transfers_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.transfers_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.transfers_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.transfers_table.setAlternatingRowColors(True)
        transfers_layout.addWidget(self.transfers_table)
        transfers_group.setLayout(transfers_layout)
        main_layout.addWidget(transfers_group)

        # Journal du serveur
        log_group = QGroupBox("Journal du serveur TFTP")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        log_layout.addWidget(self.log_text)
        log_buttons_layout = QHBoxLayout()
        log_buttons_layout.addWidget(self.clear_log_button)
        log_buttons_layout.addWidget(self.save_log_button)
        log_layout.addLayout(log_buttons_layout)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

    def applyButtonStyle(self, button, base_color, hover_color, pressed_color):
        style = f"""
            QPushButton {{
                background-color: {base_color};
                color: white;
                font-weight: bold;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {pressed_color};
                padding-left: 12px;
                padding-top: 12px;
            }}
        """
        button.setStyleSheet(style)
        from PyQt5.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(button)
        shadow.setBlurRadius(10)
        shadow.setOffset(3, 3)
        button.setGraphicsEffect(shadow)

    def connectSignals(self):
        self.browse_button.clicked.connect(self.browseRootDir)
        self.start_button.clicked.connect(self.startServer)
        self.stop_button.clicked.connect(self.stopServer)
        self.clear_log_button.clicked.connect(self.clearLog)
        self.save_log_button.clicked.connect(self.saveLog)
        self.interface_combo.currentIndexChanged.connect(self.onInterfaceChanged)

    def populateInterfaces(self):
        self.interface_combo.clear()
        if NETIFACES_AVAILABLE:
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr', None)
                        if ip and not ip.startswith("127."):
                            self.interface_combo.addItem(f"{iface} - {ip}", ip)
            self.interface_combo.insertItem(0, "Toutes les interfaces (0.0.0.0)", "0.0.0.0")
        else:
            self.interface_combo.addItem("Toutes les interfaces (0.0.0.0)", "0.0.0.0")
            try:
                local_ip = socket.gethostbyname(socket.gethostname())
            except Exception:
                local_ip = "127.0.0.1"
            self.interface_combo.addItem(f"Interface locale ({local_ip})", local_ip)
        current_ip = self.interface_combo.itemData(self.interface_combo.currentIndex())
        self.ip_label.setText(current_ip if current_ip else "0.0.0.0")

    def browseRootDir(self):
        directory = QFileDialog.getExistingDirectory(self, "Sélectionner le répertoire racine TFTP",
                                                     self.root_dir_edit.text() or os.path.expanduser("~"))
        if directory:
            self.root_dir_edit.setText(directory)

    def startServer(self):
        root_dir = self.root_dir_edit.text()
        if not root_dir:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un répertoire racine")
            return
        port = self.port_spin.value()
        interface = self.interface_combo.currentData()
        try:
            from worker.tftp_worker import TFTPWorker
            self.server = TFTPServer(interface=interface, port=port, block_size=512, root_dir=root_dir, timeout=5)
            self.worker = TFTPWorker(self.server)
            
            self.worker.signals.log_message.connect(self.addLogMessage)
            self.worker.signals.client_connected.connect(self.onClientConnected)
            self.worker.signals.client_disconnected.connect(self.onClientDisconnected)
            self.worker.signals.transfer_started.connect(self.onTransferStarted)
            self.worker.signals.transfer_updated.connect(self.onTransferUpdated)
            self.worker.signals.transfer_completed.connect(self.onTransferCompleted)
            
            self.server_thread = threading.Thread(target=self.server.start, daemon=True)
            self.server_thread.start()
            self.worker.start()
            
            self.status_label.setText("En cours d'exécution")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.port_spin.setEnabled(False)
            self.browse_button.setEnabled(False)
            self.interface_combo.setEnabled(True)
            self.addLogMessage(f"Serveur TFTP démarré sur {interface}:{port}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du démarrage: {e}")
            self.addLogMessage(f"Erreur lors du démarrage du serveur: {e}", error=True)

    def stopServer(self):
        if self.worker:
            self.worker.stop()
        if self.server:
            self.server.stop()
            if hasattr(self, "server_thread") and self.server_thread.is_alive():
                self.server_thread.join(timeout=2)
            self.status_label.setText("Arrêté")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.port_spin.setEnabled(True)
            self.browse_button.setEnabled(True)
            self.interface_combo.setEnabled(True)
            self.addLogMessage("Serveur TFTP arrêté")

    def onInterfaceChanged(self, index):
        ip = self.interface_combo.itemData(index)
        if ip:
            self.ip_label.setText(ip)
        else:
            self.ip_label.setText("0.0.0.0")

    def addLogMessage(self, message, level="INFO", error=False):
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        if error or level == "ERROR":
            fmt = "<span style='color:red;font-weight:bold;'>"
        elif level == "WARNING":
            fmt = "<span style='color:orange;'>"
        elif level == "DEBUG":
            fmt = "<span style='color:gray;'>"
        else:
            fmt = "<span>"
        self.log_text.append(fmt + timestamp + message + "</span>")

    def clearLog(self):
        self.log_text.clear()
        self.addLogMessage("Journal effacé.")

    def saveLog(self):
        log_file, _ = QFileDialog.getSaveFileName(self, "Enregistrer le journal",
                                                  os.path.join(os.path.expanduser("~"), "tftp_server_log.txt"),
                                                  "Fichiers texte (*.txt);;Tous les fichiers (*)")
        if log_file:
            try:
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.toPlainText())
                self.addLogMessage(f"Journal enregistré dans {log_file}")
            except Exception as e:
                self.addLogMessage(f"Erreur lors de l'enregistrement du journal: {e}", error=True)

    def refreshStatus(self):
        if self.server and self.server.running:
            status = self.server.get_status()
            self.updateClientsTable(status.get('clients', {}))
            self.updateTransfersTable(status.get('transfers', {}))

    def updateClientsTable(self, clients):
        self.clients_table.setRowCount(0)
        current_time = time.time()
        for client_id, info in clients.items():
            last_seen = info.get('last_seen')
            if last_seen:
                last_ts = time.mktime(last_seen.timetuple())
                if current_time - last_ts < 300:
                    row = self.clients_table.rowCount()
                    self.clients_table.insertRow(row)
                    self.clients_table.setItem(row, 0, QTableWidgetItem(client_id))
                    activity = last_seen.strftime("%H:%M:%S\n%Y-%m-%d")
                    self.clients_table.setItem(row, 1, QTableWidgetItem(activity))
                    files = info.get('files_transferred', [])
                    self.clients_table.setItem(row, 2, QTableWidgetItem(", ".join(files)))

    def updateTransfersTable(self, transfers):
        self.transfers_table.setRowCount(0)
        for client_id, transfer in transfers.items():
            if not transfer.get('completed', False):
                row = self.transfers_table.rowCount()
                self.transfers_table.insertRow(row)
                filename = transfer.get('filename', "Inconnu")
                self.transfers_table.setItem(row, 0, QTableWidgetItem(filename))
                self.transfers_table.setItem(row, 1, QTableWidgetItem(client_id))
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                total = transfer.get('file_size', 1)
                current = transfer.get('progress', 0)
                percent = min(100, int(current * 100 / total))
                progress_bar.setValue(percent)
                progress_bar.setFormat(f"{percent}% ({self.format_size(current)}/{self.format_size(total)})")
                progress_bar.setAlignment(Qt.AlignCenter)
                self.transfers_table.setCellWidget(row, 2, progress_bar)
                status_text = "En cours" if not transfer.get('completed', False) else "Terminé"
                status_item = QTableWidgetItem(status_text)
                if status_text == "En cours":
                    status_item.setForeground(QBrush(QColor("blue")))
                else:
                    status_item.setForeground(QBrush(QColor("green")))
                self.transfers_table.setItem(row, 3, status_item)
                typ = "Téléchargement" if transfer.get('direction', '') == 'download' else "Upload"
                self.transfers_table.setItem(row, 4, QTableWidgetItem(typ))
                remaining = transfer.get('remaining_time', -1)
                if remaining < 0:
                    remaining_text = "Calcul en cours"
                else:
                    hrs, rem = divmod(int(remaining), 3600)
                    mins, secs = divmod(rem, 60)
                    remaining_text = f"{hrs:02d}:{mins:02d}:{secs:02d}"
                self.transfers_table.setItem(row, 5, QTableWidgetItem(remaining_text))

    def format_size(self, size_bytes):
        if size_bytes < 1024:
            return f"{size_bytes} o"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} Ko"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} Mo"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f} Go"

    # Slots pour les signaux
    def onClientConnected(self, client_id, info):
        self.addLogMessage(f"Client connecté: {client_id}")
        self.refreshStatus()

    def onClientDisconnected(self, client_id):
        self.addLogMessage(f"Client déconnecté: {client_id}")
        self.refreshStatus()

    def onTransferStarted(self, client_id, transfer_info):
        self.addLogMessage(f"Démarrage du transfert: {transfer_info.get('filename', 'Inconnu')} avec {client_id}")
        self.refreshStatus()

    def onTransferUpdated(self, client_id, transfer_info):
        self.refreshStatus()

    def onTransferCompleted(self, client_id, success):
        stat = "réussi" if success else "échoué"
        self.addLogMessage(f"Transfert {stat} pour {client_id}")
        self.refreshStatus()

    def get_tftp_server_info(self):
        """Retourne les informations de configuration du serveur TFTP"""
        return {
            'ip_address': self.ip_label.text().strip(),
            'port': int(self.port_spin.value()),
            'root_dir': self.root_dir_edit.text().strip(),
            'running': self.server.running if self.server else False
        }


