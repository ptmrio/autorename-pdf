import os
import sys
import winreg as reg
import ctypes

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def add_registry_entries():
    if not is_admin():
        print("This script requires administrator privileges. Please run as administrator.")
        return

    # Get the current directory
    current_directory = os.path.dirname(os.path.abspath(__file__))
    
    # Check if we're running from source or as a built executable
    if getattr(sys, 'frozen', False):
        # We're running in a bundle (built executable)
        current_directory = os.path.dirname(sys.executable)
        main_script = os.path.join(current_directory, "autorename-pdf.exe")  # autorename-pdf.exe should be alongside this executable
    else:
        # We're running in a normal Python environment
        executable = os.path.join(current_directory, "venv", "Scripts", "python.exe")
        main_script = os.path.join(current_directory, "autorename.py")

    # Command for folders (using the main script directly)
    if getattr(sys, 'frozen', False):
        autorename_command = f'"{main_script}" "%1"'
    else:
        autorename_command = f'"{executable}" "{main_script}" "%1"'

    # Confirm with the user
    confirm = input("This will add 'Auto Rename PDF' to your context menus. Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    try:
        # Add registry entries for PDFs (using the wrapper)
        add_menu_for_file_type("SystemFileAssociations\\.pdf", "Auto Rename PDF", autorename_command)
        
        # Add registry entries for Folders (using the main script)
        add_menu_for_folder("Auto Rename PDFs in Folder", autorename_command)
        
        # Add registry entries for Directory Background (using the main script)
        add_menu_for_directory_background("Auto Rename PDFs in This Folder", autorename_command)
        
        print("Registry entries added successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

def add_menu_for_file_type(file_type_key, menu_name, command):
    key_path = f"{file_type_key}\\shell\\AutoRenamePDF"
    key_command_path = f"{key_path}\\command"
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, menu_name)
        reg.SetValueEx(key, "Icon", 0, reg.REG_SZ, "shell32.dll,71")
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_command_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, command)

def add_menu_for_folder(menu_name, command):
    key_path = r"Directory\shell\AutoRenamePDFs"
    key_command_path = f"{key_path}\\command"
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, menu_name)
        reg.SetValueEx(key, "Icon", 0, reg.REG_SZ, "shell32.dll,71")
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_command_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, command)

def add_menu_for_directory_background(menu_name, command):
    key_path = r"Directory\Background\shell\AutoRenamePDFs"
    key_command_path = f"{key_path}\\command"
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, menu_name)
        reg.SetValueEx(key, "Icon", 0, reg.REG_SZ, "shell32.dll,71")
    
    with reg.CreateKey(reg.HKEY_CLASSES_ROOT, key_command_path) as key:
        reg.SetValueEx(key, None, 0, reg.REG_SZ, command.replace('"%1"', '"%V"'))

def remove_registry_entries():
    if not is_admin():
        print("This script requires administrator privileges. Please run as administrator.")
        return

    confirm = input("This will remove 'Auto Rename PDF' from your context menus. Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Operation cancelled.")
        return

    try:
        # Remove entries for PDFs
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"SystemFileAssociations\.pdf\shell\AutoRenamePDF\command")
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"SystemFileAssociations\.pdf\shell\AutoRenamePDF")
        
        # Remove entries for Folders
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"Directory\shell\AutoRenamePDFs\command")
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"Directory\shell\AutoRenamePDFs")
        
        # Remove entries for Directory Background
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\AutoRenamePDFs\command")
        reg.DeleteKey(reg.HKEY_CLASSES_ROOT, r"Directory\Background\shell\AutoRenamePDFs")
        
        print("Registry entries removed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    action = input("Do you want to (a)dd or (r)emove registry entries? ").lower()
    if action == 'a':
        add_registry_entries()
    elif action == 'r':
        remove_registry_entries()
    else:
        print("Invalid option. Please choose 'a' to add or 'r' to remove.")