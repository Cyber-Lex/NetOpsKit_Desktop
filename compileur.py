import os
import secrets
import subprocess
import sys
import shutil

def generate_encryption_key():
    """Génère une clé de chiffrement unique."""
    return secrets.token_hex(16)

def obfuscate_code(input_file):
    """Obfusque le code source avec PyArmor."""
    try:
        from pyarmor.pyarmor import main as pyarmor_main
        
        # Définit les arguments pour PyArmor - sans inclure 'pyarmor' comme premier argument
        pyarmor_args = ['obfuscate', '--advanced', '2', '--restrict', '3', '--recursive', input_file]
        
        # Exécute PyArmor en passant explicitement les arguments
        pyarmor_main(pyarmor_args)
        
        print("Obfuscation réussie.")
    except Exception as e:
        print(f"Erreur lors de l'obfuscation : {e}")
        sys.exit(1)

def compile_executable(encryption_key, input_file):
    """Compile l'exécutable avec PyInstaller."""
    try:
        # Assurez-vous que le dossier dist existe
        os.makedirs('dist', exist_ok=True)
        
        # Utiliser py -m PyInstaller comme vous le faites manuellement
        # Suppression de l'option --key qui n'est plus supportée dans PyInstaller v6.0+
        compile_cmd = [
            sys.executable, 
            '-m', 
            'PyInstaller',
            '--onefile',
            '--windowed',
            f'--name=NetOpsKit',
            # L'option --key a été supprimée dans PyInstaller v6.0+
            '--add-data', 'resources;resources',  # Notez le point-virgule pour Windows
            '--hidden-import=psutil',
            '--hidden-import=winreg',
            '--hidden-import=cryptography',
            '--hidden-import=hashlib',
            '--hidden-import=hmac',
            '--hidden-import=base64',
            '--icon=resources/logo/Icon_netopskit.ico',
            '--clean',
            input_file
        ]
        
        print(f"Exécution de la commande : {' '.join(compile_cmd)}")
        subprocess.run(compile_cmd, check=True)
        print("Compilation réussie.")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de la compilation : {e}")
        sys.exit(1)

def main():
    # Fichier principal à compiler
    main_script = 'main.py'
   
    # Générer la clé de chiffrement
    encryption_key = generate_encryption_key()
    print(f"Clé de chiffrement générée : {encryption_key}")
   
    # Étape 1 : Obfuscation
    obfuscate_code(main_script)
   
    # Étape 2 : Compilation
    compile_executable(encryption_key, main_script)
   
    # Informations finales
    print("\nApplication compilée avec succès!")
    print("L'exécutable est disponible dans : ./dist/NetOpsKit.exe")

if __name__ == '__main__':
    main()