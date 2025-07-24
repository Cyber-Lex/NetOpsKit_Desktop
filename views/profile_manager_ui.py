from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QDialog, QDialogButtonBox,
    QMessageBox, QFormLayout, QHeaderView, QAbstractItemView, QSplitter
)
from PyQt5.QtCore import Qt, QSize, pyqtSignal

from utils.profile_manager import ProfileManager, ConfigProfile

class ProfileDialog(QDialog):
    """Dialogue pour créer ou éditer un profil"""
    
    def __init__(self, profile=None, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.setWindowTitle("Profil de configuration" if not profile else f"Éditer : {profile.name}")
        self.setMinimumWidth(500)
        self.initUI()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        self.name_edit = QLineEdit()
        if self.profile:
            self.name_edit.setText(self.profile.name)
        form.addRow("Nom du profil:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        if self.profile:
            self.description_edit.setText(self.profile.description)
        form.addRow("Description:", self.description_edit)
        
        layout.addLayout(form)
        
        # Boutons standard
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

class ProfileManagerWidget(QWidget):
    """Widget de gestion des profils de configuration"""
    
    profile_selected = pyqtSignal(ConfigProfile)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile_manager = ProfileManager()
        self.initUI()
        self.refresh_profiles()
    
    def initUI(self):
        layout = QVBoxLayout(self)
        
        # Titre
        title_label = QLabel("Gestionnaire de profils")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Splitter pour la table et le panneau de détails
        splitter = QSplitter(Qt.Horizontal)
        
        # Table des profils
        self.profiles_table = QTableWidget()
        self.profiles_table.setColumnCount(3)
        self.profiles_table.setHorizontalHeaderLabels(["Nom", "Date", "Description"])
        self.profiles_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.profiles_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.profiles_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.profiles_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.profiles_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.profiles_table.itemSelectionChanged.connect(self.on_selection_changed)
        splitter.addWidget(self.profiles_table)
        
        # Panneau de détails
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        self.detail_label = QLabel("Détails du profil")
        self.detail_label.setStyleSheet("font-weight: bold;")
        details_layout.addWidget(self.detail_label)
        
        self.detail_content = QTextEdit()
        self.detail_content.setReadOnly(True)
        details_layout.addWidget(self.detail_content)
        
        splitter.addWidget(details_widget)
        splitter.setSizes([200, 200])  # Répartition initiale
        
        layout.addWidget(splitter)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        
        self.new_button = QPushButton("Nouveau")
        self.new_button.clicked.connect(self.create_profile)
        buttons_layout.addWidget(self.new_button)
        
        self.load_button = QPushButton("Charger")
        self.load_button.clicked.connect(self.load_profile)
        self.load_button.setEnabled(False)  # Initialement désactivé
        buttons_layout.addWidget(self.load_button)
        
        self.edit_button = QPushButton("Éditer")
        self.edit_button.clicked.connect(self.edit_profile)
        self.edit_button.setEnabled(False)  # Initialement désactivé
        buttons_layout.addWidget(self.edit_button)
        
        self.delete_button = QPushButton("Supprimer")
        self.delete_button.clicked.connect(self.delete_profile)
        self.delete_button.setEnabled(False)  # Initialement désactivé
        buttons_layout.addWidget(self.delete_button)
        
        layout.addLayout(buttons_layout)
    
    def refresh_profiles(self):
        """Rafraîchit la liste des profils"""
        self.profiles_table.setRowCount(0)
        profiles = self.profile_manager.list_profiles()
        
        for i, profile_info in enumerate(profiles):
            self.profiles_table.insertRow(i)
            self.profiles_table.setItem(i, 0, QTableWidgetItem(profile_info["name"]))
            self.profiles_table.setItem(i, 1, QTableWidgetItem(profile_info["date"]))
            self.profiles_table.setItem(i, 2, QTableWidgetItem(profile_info["description"]))
            # Stocker le nom de fichier comme donnée utilisateur
            self.profiles_table.item(i, 0).setData(Qt.UserRole, profile_info["filename"])
    
    def on_selection_changed(self):
        """Gère le changement de sélection dans la table"""
        selected_rows = self.profiles_table.selectedItems()
        has_selection = len(selected_rows) > 0
        
        self.load_button.setEnabled(has_selection)
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        
        if has_selection:
            row = selected_rows[0].row()
            filename = self.profiles_table.item(row, 0).data(Qt.UserRole)
            
            try:
                profile = self.profile_manager.load_profile(filename)
                self.detail_content.setText(
                    f"Nom: {profile.name}\n"
                    f"Description: {profile.description}\n"
                    f"Date de création: {profile.creation_date}\n\n"
                    f"Contenu: {str(profile.config_data)[:500]}..."
                )
            except Exception as e:
                self.detail_content.setText(f"Erreur lors du chargement du profil: {e}")
    
    def create_profile(self):
        """Crée un nouveau profil"""
        dialog = ProfileDialog(parent=self)
        if dialog.exec_() == QDialog.Accepted:
            name = dialog.name_edit.text()
            description = dialog.description_edit.toPlainText()
            
            profile = ConfigProfile(name=name, description=description, config_data={})
            try:
                self.profile_manager.save_profile(profile)
                QMessageBox.information(self, "Succès", f"Profil {name} créé avec succès")
                self.refresh_profiles()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la création du profil: {e}")
    
    def edit_profile(self):
        """Édite le profil sélectionné"""
        selected_rows = self.profiles_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        filename = self.profiles_table.item(row, 0).data(Qt.UserRole)
        
        try:
            profile = self.profile_manager.load_profile(filename)
            dialog = ProfileDialog(profile=profile, parent=self)
            
            if dialog.exec_() == QDialog.Accepted:
                profile.name = dialog.name_edit.text()
                profile.description = dialog.description_edit.toPlainText()
                
                self.profile_manager.delete_profile(filename)
                self.profile_manager.save_profile(profile)
                QMessageBox.information(self, "Succès", f"Profil {profile.name} modifié avec succès")
                self.refresh_profiles()
                
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Erreur lors de l'édition du profil: {e}")
    
    def load_profile(self):
        """Charge le profil sélectionné"""
        selected_rows = self.profiles_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        filename = self.profiles_table.item(row, 0).data(Qt.UserRole)
        
        try:
            profile = self.profile_manager.load_profile(filename)
            self.profile_selected.emit(profile)
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Erreur lors du chargement du profil: {e}")
    
    def delete_profile(self):
        """Supprime le profil sélectionné"""
        selected_rows = self.profiles_table.selectedItems()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        filename = self.profiles_table.item(row, 0).data(Qt.UserRole)
        name = self.profiles_table.item(row, 0).text()
        
        confirm = QMessageBox.question(
            self,
            "Confirmation",
            f"Êtes-vous sûr de vouloir supprimer le profil {name} ?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                self.profile_manager.delete_profile(filename)
                QMessageBox.information(self, "Succès", f"Profil {name} supprimé avec succès")
                self.refresh_profiles()
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur lors de la suppression du profil: {e}")
