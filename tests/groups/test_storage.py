"""Unit tests for GroupStorage class."""

import json
import os
import tempfile
from pathlib import Path
import pytest
from unittest.mock import patch, mock_open

from mcp_ical.groups.storage import GroupStorage


class TestGroupStorage:
    """Test GroupStorage functionality."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def storage(self, temp_dir):
        """Create GroupStorage instance with temporary path."""
        storage_path = temp_dir / "test_groups.json"
        return GroupStorage(str(storage_path))
    
    def test_init_default_path(self):
        """Test initialization with default path."""
        storage = GroupStorage()
        expected_path = Path.home() / "Library" / "Application Support" / "mcp-ical" / "calendar_groups.json"
        assert storage.storage_path == expected_path
    
    def test_init_custom_path(self, temp_dir):
        """Test initialization with custom path."""
        custom_path = temp_dir / "custom_groups.json"
        storage = GroupStorage(str(custom_path))
        assert storage.storage_path == custom_path
    
    def test_load_groups_empty_file(self, storage):
        """Test loading when no file exists."""
        result = storage.load_groups()
        expected = {"version": "1.0", "groups": {}}
        assert result == expected
    
    def test_load_groups_valid_file(self, storage):
        """Test loading valid groups file."""
        test_data = {
            "version": "1.0",
            "groups": {
                "work": {
                    "name": "work",
                    "calendar_ids": ["cal1", "cal2"],
                    "description": "Work calendars"
                }
            }
        }
        
        # Write test data
        with open(storage.storage_path, 'w') as f:
            json.dump(test_data, f)
        
        result = storage.load_groups()
        assert result == test_data
    
    def test_load_groups_corrupted_file(self, storage):
        """Test loading corrupted JSON file."""
        # Write invalid JSON
        with open(storage.storage_path, 'w') as f:
            f.write("invalid json{")
        
        result = storage.load_groups()
        expected = {"version": "1.0", "groups": {}}
        assert result == expected
    
    def test_save_groups_new_file(self, storage):
        """Test saving groups to new file."""
        test_data = {
            "version": "1.0",
            "groups": {
                "personal": {
                    "name": "personal",
                    "calendar_ids": ["cal3"],
                    "description": "Personal calendar"
                }
            }
        }
        
        storage.save_groups(test_data)
        
        # Verify file was created and contains correct data
        assert storage.storage_path.exists()
        with open(storage.storage_path, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == test_data
    
    def test_save_groups_atomic_write(self, storage):
        """Test atomic write behavior - basic functionality."""
        test_data = {"version": "1.0", "groups": {"test": "data"}}
        
        # Should save without error
        storage.save_groups(test_data)
        
        # Verify file was created correctly
        assert storage.storage_path.exists()
        with open(storage.storage_path, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == test_data
    
    def test_backup_file(self, storage):
        """Test backup file creation."""
        # Create initial file
        test_data = {"version": "1.0", "groups": {"test": "data"}}
        with open(storage.storage_path, 'w') as f:
            json.dump(test_data, f)
        
        backup_path = storage.backup_file()
        
        # Verify backup was created
        assert os.path.exists(backup_path)
        assert "calendar_groups_" in backup_path
        assert backup_path.endswith(".json")
        
        # Verify backup contains same data
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)
        assert backup_data == test_data
    
    def test_backup_file_no_source(self, storage):
        """Test backup when source file doesn't exist."""
        with pytest.raises(FileNotFoundError):
            storage.backup_file()
    
    def test_migrate_schema_no_version(self, storage):
        """Test schema migration for data without version."""
        old_data = {"groups": {"test": "data"}}
        result = storage.migrate_schema(old_data)
        expected = {"version": "1.0", "groups": {"test": "data"}}
        assert result == expected
    
    def test_migrate_schema_legacy_format(self, storage):
        """Test schema migration for legacy format."""
        old_data = {"test": "data"}  # Old format where data was groups directly
        result = storage.migrate_schema(old_data)
        expected = {"version": "1.0", "groups": {"test": "data"}}
        assert result == expected
    
    def test_migrate_schema_current_version(self, storage):
        """Test schema migration for current version."""
        current_data = {"version": "1.0", "groups": {"test": "data"}}
        result = storage.migrate_schema(current_data)
        assert result == current_data
    
    def test_restore_from_backup(self, storage):
        """Test restoration from backup file."""
        # Create backup file
        backup_data = {"version": "1.0", "groups": {"restored": "data"}}
        backup_file = storage.backup_dir / "calendar_groups_20231201_120000.json"
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        
        # Test restoration
        result = storage._restore_from_backup()
        assert result == backup_data
    
    def test_restore_from_backup_no_backups(self, storage):
        """Test restoration when no backups exist."""
        result = storage._restore_from_backup()
        assert result is None
    
    def test_cleanup_old_backups(self, storage):
        """Test cleanup of old backup files."""
        # Create a few backup files
        for i in range(3):
            backup_file = storage.backup_dir / f"calendar_groups_2023120{i}_120000.json"
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            with open(backup_file, 'w') as f:
                json.dump({"test": f"backup{i}"}, f)
        
        # Cleanup should not error
        storage._cleanup_old_backups(max_backups=2)
        
        # Should have at most 2 files remaining
        remaining_files = list(storage.backup_dir.glob("calendar_groups_*.json"))
        assert len(remaining_files) <= 2
    
    def test_save_groups_creates_backup(self, storage):
        """Test that saving creates backup of existing file."""
        # Create initial file
        initial_data = {"version": "1.0", "groups": {"initial": "data"}}
        with open(storage.storage_path, 'w') as f:
            json.dump(initial_data, f)
        
        # Save new data
        new_data = {"version": "1.0", "groups": {"new": "data"}}
        storage.save_groups(new_data)
        
        # Verify backup was created
        backup_files = list(storage.backup_dir.glob("calendar_groups_*.json"))
        assert len(backup_files) >= 1
        
        # Verify latest backup contains initial data
        latest_backup = max(backup_files, key=lambda x: x.stat().st_mtime)
        with open(latest_backup, 'r') as f:
            backup_data = json.load(f)
        assert backup_data == initial_data