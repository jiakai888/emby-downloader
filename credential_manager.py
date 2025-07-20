"""
Credential Manager - Handles secure storage and management of Emby server credentials
"""

import json
import base64
import hashlib
import platform
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple
from dataclasses import dataclass, asdict
from rich.console import Console

console = Console()

@dataclass
class ServerConfig:
    """Server configuration data model"""
    name: str
    url: str
    username: str
    password: str  # Will be encrypted when stored
    last_used: Optional[datetime] = None
    created: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created is None:
            self.created = datetime.now()
        if self.last_used is None:
            self.last_used = datetime.now()

class CredentialManager:
    """Manages secure storage and retrieval of server credentials"""
    
    def __init__(self, config_file: str = None):
        if config_file is None:
            # Use user home directory
            home = Path.home()
            self.config_dir = home / ".emby_extractor"
            self.config_file = self.config_dir / "servers.json"
        else:
            self.config_file = Path(config_file)
            self.config_dir = self.config_file.parent
        
        # Ensure config directory exists
        self.config_dir.mkdir(exist_ok=True)
        
        # Generate machine-specific encryption key
        self._encryption_key = self._generate_encryption_key()
    
    def _generate_encryption_key(self) -> str:
        """Generate a machine-specific encryption key"""
        try:
            # Use machine info to create a consistent key
            machine_info = f"{platform.node()}-{platform.machine()}-emby_extractor"
            key = hashlib.sha256(machine_info.encode()).hexdigest()[:32]
            return key
        except Exception:
            # Fallback key if machine info fails
            return "emby_extractor_default_key_12345"
    
    def _encrypt_password(self, password: str) -> str:
        """Simple encryption for password storage"""
        try:
            # Simple XOR encryption with the key
            key = self._encryption_key
            encrypted = ""
            for i, char in enumerate(password):
                key_char = key[i % len(key)]
                encrypted += chr(ord(char) ^ ord(key_char))
            
            # Base64 encode the result
            return base64.b64encode(encrypted.encode('latin-1')).decode('ascii')
        except Exception:
            # Fallback to base64 encoding if encryption fails
            return base64.b64encode(password.encode()).decode('ascii')
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt stored password"""
        try:
            # Decode base64
            encrypted = base64.b64decode(encrypted_password.encode('ascii')).decode('latin-1')
            
            # XOR decrypt with the key
            key = self._encryption_key
            decrypted = ""
            for i, char in enumerate(encrypted):
                key_char = key[i % len(key)]
                decrypted += chr(ord(char) ^ ord(key_char))
            
            return decrypted
        except Exception:
            # Try base64 decode as fallback
            try:
                return base64.b64decode(encrypted_password.encode('ascii')).decode()
            except Exception:
                return encrypted_password  # Return as-is if all fails
    
    def save_server(self, config: ServerConfig) -> bool:
        """Save a server configuration"""
        try:
            # Load existing servers
            servers = self.load_servers()
            
            # Check for duplicate names
            existing_names = [s.name for s in servers]
            if config.name in existing_names:
                console.print(f"[yellow]Server name '{config.name}' already exists. Please choose a different name.[/yellow]")
                return False
            
            # Add new server to list (password will be encrypted in _save_servers_to_file)
            servers.append(config)
            
            # Save to file
            return self._save_servers_to_file(servers)
            
        except Exception as e:
            console.print(f"[red]Error saving server configuration: {e}[/red]")
            return False
    
    def load_servers(self) -> List[ServerConfig]:
        """Load all server configurations"""
        try:
            if not self.config_file.exists():
                return []
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            servers = []
            for server_data in data.get('servers', []):
                # Decrypt password
                server_data['password'] = self._decrypt_password(server_data['password'])
                
                # Parse datetime fields
                if 'last_used' in server_data and server_data['last_used']:
                    server_data['last_used'] = datetime.fromisoformat(server_data['last_used'])
                if 'created' in server_data and server_data['created']:
                    server_data['created'] = datetime.fromisoformat(server_data['created'])
                
                servers.append(ServerConfig(**server_data))
            
            # Sort by last used (most recent first)
            servers.sort(key=lambda x: x.last_used or datetime.min, reverse=True)
            
            return servers
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load server configurations: {e}[/yellow]")
            return []
    
    def update_server_last_used(self, server_name: str) -> bool:
        """Update the last used timestamp for a server"""
        try:
            servers = self.load_servers()
            
            for server in servers:
                if server.name == server_name:
                    server.last_used = datetime.now()
                    return self._save_servers_to_file(servers)
            
            return False
            
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update server timestamp: {e}[/yellow]")
            return False
    
    def delete_server(self, server_name: str) -> bool:
        """Delete a server configuration"""
        try:
            servers = self.load_servers()
            original_count = len(servers)
            
            servers = [s for s in servers if s.name != server_name]
            
            if len(servers) < original_count:
                return self._save_servers_to_file(servers)
            else:
                console.print(f"[yellow]Server '{server_name}' not found.[/yellow]")
                return False
                
        except Exception as e:
            console.print(f"[red]Error deleting server: {e}[/red]")
            return False
    
    def _save_servers_to_file(self, servers: List[ServerConfig]) -> bool:
        """Save servers list to file"""
        try:
            # Create backup if file exists
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.backup')
                # Remove existing backup file if it exists
                if backup_file.exists():
                    backup_file.unlink()
                self.config_file.rename(backup_file)
            
            # Prepare data for JSON serialization
            servers_data = []
            for server in servers:
                server_dict = asdict(server)
                # Convert datetime objects to ISO format strings
                if server_dict['last_used']:
                    server_dict['last_used'] = server_dict['last_used'].isoformat()
                if server_dict['created']:
                    server_dict['created'] = server_dict['created'].isoformat()
                
                # Encrypt password for storage (passwords in memory are always plaintext)
                server_dict['password'] = self._encrypt_password(server.password)
                servers_data.append(server_dict)
            
            data = {
                'version': '1.0',
                'servers': servers_data
            }
            
            # Write to file
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Set file permissions to user-only
            try:
                self.config_file.chmod(0o600)
            except Exception:
                pass  # Ignore permission errors on Windows
            
            return True
            
        except Exception as e:
            console.print(f"[red]Error saving server configurations: {e}[/red]")
            # Restore backup if it exists
            backup_file = self.config_file.with_suffix('.json.backup')
            if backup_file.exists():
                backup_file.rename(self.config_file)
            return False
    
    def validate_server_config(self, config: ServerConfig) -> Tuple[bool, str]:
        """Validate server configuration"""
        if not config.name.strip():
            return False, "Server name cannot be empty"
        
        if not config.url.strip():
            return False, "Server URL cannot be empty"
        
        if not config.url.startswith(('http://', 'https://')):
            return False, "Server URL must start with http:// or https://"
        
        if not config.username.strip():
            return False, "Username cannot be empty"
        
        if not config.password.strip():
            return False, "Password cannot be empty"
        
        return True, "Valid configuration"