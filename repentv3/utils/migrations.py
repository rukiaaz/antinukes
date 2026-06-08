"""
Repent - Database Migration System
Manages database schema changes in a controlled, versioned manner.
"""

import os
import aiosqlite
from typing import Callable, Dict, List
from datetime import datetime, timezone
from config import DB_PATH
from utils.logger import get_logger


class Migration:
    """Represents a single database migration."""
    
    def __init__(self, version: int, name: str, up: Callable, down: Callable = None):
        """
        Initialize a migration.
        
        Args:
            version: Migration version number
            name: Migration name/description
            up: Function to apply the migration
            down: Function to rollback the migration (optional)
        """
        self.version = version
        self.name = name
        self.up = up
        self.down = down


class MigrationRunner:
    """Manages database migrations."""
    
    def __init__(self):
        self.migrations: Dict[int, Migration] = {}
        self.logger = get_logger()
    
    def register(self, migration: Migration):
        """Register a migration."""
        if migration.version in self.migrations:
            raise ValueError(f"Migration version {migration.version} already registered")
        self.migrations[migration.version] = migration
    
    async def get_current_version(self, db: aiosqlite.Connection) -> int:
        """Get the current database migration version."""
        try:
            cursor = await db.execute("SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1")
            row = await cursor.fetchone()
            return row[0] if row else 0
        except aiosqlite.OperationalError:
            # Schema migrations table doesn't exist yet
            return 0
    
    async def create_migrations_table(self, db: aiosqlite.Connection):
        """Create the schema migrations tracking table."""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        await db.commit()
    
    async def migrate(self, target_version: int = None):
        """
        Run migrations to bring database to target version.
        
        Args:
            target_version: Target version (defaults to latest)
        """
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        db = await aiosqlite.connect(DB_PATH)
        
        try:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode = WAL")
            # Set busy timeout to handle concurrent access
            await db.execute("PRAGMA busy_timeout = 5000")
            
            await self.create_migrations_table(db)
            current_version = await self.get_current_version(db)
            
            if target_version is None:
                target_version = max(self.migrations.keys()) if self.migrations else current_version
            
            self.logger.info(f"Migration: current version {current_version}, target version {target_version}")
            
            if target_version > current_version:
                # Upgrade
                for version in range(current_version + 1, target_version + 1):
                    if version in self.migrations:
                        migration = self.migrations[version]
                        self.logger.info(f"Applying migration {version}: {migration.name}")
                        
                        try:
                            await migration.up(db)
                            await db.execute(
                                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                                (version, migration.name, datetime.now(timezone.utc).isoformat())
                            )
                            await db.commit()
                            self.logger.info(f"Successfully applied migration {version}")
                        except Exception as e:
                            self.logger.error(f"Failed to apply migration {version}", exc_info=True)
                            await db.rollback()
                            raise
            elif target_version < current_version:
                # Downgrade
                for version in range(current_version, target_version, -1):
                    if version in self.migrations:
                        migration = self.migrations[version]
                        if migration.down:
                            self.logger.info(f"Rolling back migration {version}: {migration.name}")
                            
                            try:
                                await migration.down(db)
                                await db.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))
                                await db.commit()
                                self.logger.info(f"Successfully rolled back migration {version}")
                            except Exception as e:
                                self.logger.error(f"Failed to rollback migration {version}", exc_info=True)
                                await db.rollback()
                                raise
                        else:
                            self.logger.warning(f"Migration {version} has no rollback function")
            
            self.logger.info(f"Migration complete: now at version {target_version}")
            
        finally:
            await db.close()


# Global migration runner
migration_runner = MigrationRunner()


def get_migration_runner() -> MigrationRunner:
    """Get the global migration runner."""
    return migration_runner


# Example migration functions
async def migration_1_add_foreign_keys(db: aiosqlite.Connection):
    """Example migration: Add foreign key support to existing tables."""
    # This would be implemented if we wanted to add FKs to existing tables
    # For now, this is just a placeholder
    pass


async def migration_1_down(db: aiosqlite.Connection):
    """Rollback migration 1."""
    pass


# Register migrations
migration_runner.register(Migration(
    version=1,
    name="add_foreign_key_support",
    up=migration_1_add_foreign_keys,
    down=migration_1_down
))