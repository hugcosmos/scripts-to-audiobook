import os
import re
from pathlib import Path

class ConfigManager:
    def __init__(self, env_file=None):
        if env_file is None:
            # Default to root directory .env file
            backend_dir = Path(__file__).parent
            root_dir = backend_dir.parent
            env_file = root_dir / '.env'
        self.env_file = str(env_file)
        self._cache = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load environment variables from .env file into cache"""
        if not os.path.exists(self.env_file):
            return
        
        with open(self.env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    self._cache[key] = value
    
    def get(self, key, default=None):
        """Get value from cache or environment variables"""
        # Always reload from file to get latest value
        self._load_cache()
        if key in self._cache:
            return self._cache[key]
        return os.getenv(key, default)
    
    def set(self, key, value):
        """Set value in cache and update .env file"""
        self._cache[key] = value
        self._update_env_file()
    
    def delete(self, key):
        """Delete value from cache and update .env file"""
        if key in self._cache:
            del self._cache[key]
            self._update_env_file()
    
    def _update_env_file(self):
        """Update .env file with current cache"""
        # Read existing content
        content = []
        if os.path.exists(self.env_file):
            with open(self.env_file, 'r', encoding='utf-8') as f:
                content = f.readlines()
        
        # Create a dictionary of existing key-value pairs
        existing_vars = {}
        new_content = []
        
        for line in content:
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('#'):
                key, _ = line_stripped.split('=', 1)
                key = key.strip()
                existing_vars[key] = True
                # If key is in cache, update it
                if key in self._cache:
                    new_content.append(f"{key}={self._cache[key]}\n")
                # If key is not in cache, remove it
                # (it will be deleted from the file)
            else:
                # Preserve comments and empty lines
                new_content.append(line)
        
        # Add new keys that are not in existing content
        for key, value in self._cache.items():
            if key not in existing_vars:
                new_content.append(f"{key}={value}\n")
        
        # Write updated content back to .env file
        with open(self.env_file, 'w', encoding='utf-8') as f:
            f.writelines(new_content)
    
    def get_all(self):
        """Get all environment variables"""
        return self._cache.copy()

# Create global instance
config_manager = ConfigManager()