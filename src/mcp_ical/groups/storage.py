"""Storage layer for calendar groups with atomic operations and JSON persistence."""

import json
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


class GroupStorage:
    """Handle JSON file persistence for calendar groups with atomic operations."""
    
    def __init__(self, storage_path: str = None):
        """Initialize storage with configurable path.
        
        Args:
            storage_path: Path to store groups file. Defaults to user config directory.
        """
        if storage_path is None:
            # Use proper macOS Application Support directory
            config_dir = Path.home() / "Library" / "Application Support" / "mcp-ical"
            config_dir.mkdir(parents=True, exist_ok=True)
            storage_path = config_dir / "calendar_groups.json"
        
        self.storage_path = Path(storage_path)
        self.backup_dir = self.storage_path.parent / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def load_groups(self) -> Dict[str, Any]:
        """Load groups from JSON file with error recovery.
        
        Returns:
            Dictionary containing groups data with schema version.
        """
        if not self.storage_path.exists():
            return {"version": "1.0", "groups": {}}
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Migrate schema if needed
            data = self.migrate_schema(data)
            return data
            
        except (json.JSONDecodeError, IOError) as e:
            # Try to restore from backup
            backup_data = self._restore_from_backup()
            if backup_data is not None:
                return backup_data
            
            # If no backup available, return empty schema
            return {"version": "1.0", "groups": {}}
    
    def save_groups(self, groups: Dict[str, Any]) -> None:
        """Save groups to JSON file using atomic write pattern.
        
        Args:
            groups: Dictionary containing groups data to save.
        """
        # Create backup before saving
        if self.storage_path.exists():
            self.backup_file()
        
        # Atomic write: write to temp file then rename
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w',
                encoding='utf-8',
                dir=self.storage_path.parent,
                delete=False,
                suffix='.tmp'
            ) as f:
                temp_file = f.name
                json.dump(groups, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename
            shutil.move(temp_file, self.storage_path)
            temp_file = None
            
        except Exception as e:
            # Clean up temp file if something went wrong
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            raise IOError(f"Failed to save groups: {e}")
    
    def backup_file(self) -> str:
        """Create a timestamped backup of the current groups file.
        
        Returns:
            Path to the created backup file.
        """
        if not self.storage_path.exists():
            raise FileNotFoundError("No groups file to backup")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"calendar_groups_{timestamp}.json"
        backup_path = self.backup_dir / backup_name
        
        shutil.copy2(self.storage_path, backup_path)
        
        # Keep only last 10 backups
        self._cleanup_old_backups()
        
        return str(backup_path)
    
    def migrate_schema(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate data between schema versions.
        
        Args:
            data: Raw data from JSON file.
            
        Returns:
            Migrated data with current schema version.
        """
        # Handle legacy data without version
        if "version" not in data:
            if "groups" in data:
                # Already in expected format, just add version
                data["version"] = "1.0"
            else:
                # Old format where data was groups directly
                data = {"version": "1.0", "groups": data}
        
        # Future version migrations would go here
        # if data["version"] == "1.0":
        #     data = self._migrate_1_0_to_1_1(data)
        
        return data
    
    def _restore_from_backup(self) -> Dict[str, Any] | None:
        """Attempt to restore from the most recent backup.
        
        Returns:
            Restored data or None if no valid backup found.
        """
        if not self.backup_dir.exists():
            return None
        
        backup_files = sorted(
            [f for f in self.backup_dir.glob("calendar_groups_*.json")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for backup_file in backup_files:
            try:
                with open(backup_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return self.migrate_schema(data)
            except (json.JSONDecodeError, IOError):
                continue
        
        return None
    
    def _cleanup_old_backups(self, max_backups: int = 10) -> None:
        """Remove old backup files, keeping only the most recent ones.
        
        Args:
            max_backups: Maximum number of backup files to retain.
        """
        backup_files = sorted(
            [f for f in self.backup_dir.glob("calendar_groups_*.json")],
            key=lambda x: x.stat().st_mtime,
            reverse=True
        )
        
        for old_backup in backup_files[max_backups:]:
            try:
                old_backup.unlink()
            except OSError:
                pass  # Ignore errors when cleaning up