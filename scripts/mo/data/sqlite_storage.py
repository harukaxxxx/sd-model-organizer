import os
import shutil
import sqlite3
import threading
from typing import List
from modules import shared

from scripts.mo.data.storage import Storage
from scripts.mo.environment import env, logger
from scripts.mo.models import Record, ModelType

_DB_FILE = 'database.sqlite'
_DB_VERSION = 7
_DB_TIMEOUT = 30


def map_row_to_record(row) -> Record:
    return Record(
        id_=row[0],
        name=row[1],
        model_type=ModelType.by_value(row[2]),
        download_url=row[3],
        url=row[4],
        download_path=row[5],
        download_filename=row[6],
        preview_url=row[7],
        description=row[8],
        positive_prompts=row[9],
        negative_prompts=row[10],
        sha256_hash=row[11],
        md5_hash=row[12],
        created_at=row[13],
        groups=row[14].split(',') if row[14] else [],
        subdir=row[15],
        location=row[16],
        weight=row[17],
        backup_url=row[18]
    )


class SQLiteStorage(Storage):

    def __init__(self):
        self.local = threading.local()
        self._initialize()

    def _database_path(self):
        mo_database_dir = getattr(shared.cmd_opts, "mo_database_dir")
        database_dir = mo_database_dir if mo_database_dir is not None else env.script_dir
        db_file_path = os.path.join(database_dir, _DB_FILE)
        return db_file_path

    def _connection(self):
        if not hasattr(self.local, "connection"):
            self.local.connection = sqlite3.connect(self._database_path(), _DB_TIMEOUT)
        return self.local.connection

    def _initialize(self):
        cursor = self._connection().cursor()

        cursor.execute('''CREATE TABLE IF NOT EXISTS Record
                                    (id INTEGER PRIMARY KEY,
                                    _name TEXT,
                                    model_type TEXT,
                                    download_url TEXT,
                                    url TEXT DEFAULT '',
                                    download_path TEXT DEFAULT '',
                                    download_filename TEXT DEFAULT '',
                                    preview_url TEXT DEFAULT '',
                                    description TEXT DEFAULT '',
                                    positive_prompts TEXT DEFAULT '',
                                    negative_prompts TEXT DEFAULT '',
                                    sha256_hash TEXT DEFAULT '',
                                    md5_hash TEXT DEFAULT '',
                                    created_at INTEGER DEFAULT 0,
                                    groups TEXT DEFAULT '',
                                    subdir TEXT DEFAULT '',
                                    location TEXT DEFAULT '',
                                    weight REAL DEFAULT 1,
                                    backup_url TEXT)
                                 ''')

        cursor.execute(f'''CREATE TABLE IF NOT EXISTS Version
                                (version INTEGER DEFAULT {_DB_VERSION})''')
        self._connection().commit()
        self._check_database_version()

    def _check_database_version(self):
        cursor = self._connection().cursor()
        cursor.execute('SELECT * FROM Version ', )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(f'INSERT INTO Version VALUES ({_DB_VERSION})')
            self._connection().commit()

        version = _DB_VERSION if row is None else row[0]
        if version != _DB_VERSION:
            self._run_migration(version)

    def _run_migration(self, current_version):
        migration_map = {
            1: self._migrate_1_to_2,
            2: self._migrate_2_to_3,
            3: self._migrate_3_to_4,
            4: self._migrate_4_to_5,
            5: self._migrate_5_to_6,
            6: self._migrate_6_to_7,
        }
        for ver in range(current_version, _DB_VERSION):
            self._backup_database(ver)
            migration = migration_map.get(ver)
            if migration is None:
                raise Exception(f'Missing SQLite migration from {ver} to {_DB_VERSION}')
            migration()

    def _backup_database(self, migrate_from):
        db_file_path = self._database_path()
        backup_db_file_path = f'{db_file_path}.v{migrate_from}.bak'
        last_backup_db_file_path = f'{db_file_path}.v{migrate_from-1}.bak' if migrate_from > 1 else None
        if last_backup_db_file_path and os.path.isfile(last_backup_db_file_path):
            os.remove(last_backup_db_file_path)
            logger.info('Backup database v%s removed', migrate_from - 1)
        shutil.copy(db_file_path, backup_db_file_path)
        logger.info('Database v%s backup created', migrate_from)

    def _migrate_1_to_2(self):
        cursor = self._connection().cursor()
        cursor.execute('ALTER TABLE Record ADD COLUMN created_at INTEGER DEFAULT 0;')
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (2)')
        self._connection().commit()

    def _migrate_2_to_3(self):
        cursor = self._connection().cursor()
        cursor.execute("ALTER TABLE Record ADD COLUMN groups TEXT DEFAULT '';")
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (3)')
        self._connection().commit()

    def _migrate_3_to_4(self):
        cursor = self._connection().cursor()
        cursor.execute("ALTER TABLE Record RENAME COLUMN model_hash TO sha256_hash;")
        cursor.execute("ALTER TABLE Record ADD COLUMN subdir TEXT DEFAULT '';")
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (4)')
        self._connection().commit()

    def _migrate_4_to_5(self):
        cursor = self._connection().cursor()
        cursor.execute("ALTER TABLE Record ADD COLUMN location TEXT DEFAULT '';")
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (5)')
        self._connection().commit()

    def _migrate_5_to_6(self):
        cursor = self._connection().cursor()
        cursor.execute("ALTER TABLE Record ADD COLUMN weight REAL DEFAULT 1;")
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (6)')
        self._connection().commit()

    def _migrate_6_to_7(self):
        cursor = self._connection().cursor()
        cursor.execute("ALTER TABLE Record ADD COLUMN backup_url TEXT DEFAULT '';")
        cursor.execute("DELETE FROM Version")
        cursor.execute('INSERT INTO Version VALUES (7)')
        self._connection().commit()

    def get_all_records(self) -> List:
        cursor = self._connection().cursor()
        cursor.execute('SELECT * FROM Record')
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append(map_row_to_record(row))
        return result

    def query_records(self, name_query: str = None, groups=None, model_types=None, show_downloaded=True,
                      show_not_downloaded=True) -> List:

        query = 'SELECT * FROM Record'

        is_where_appended = False
        append_and = False

        if name_query is not None and name_query:
            if not is_where_appended:
                query += ' WHERE'
                is_where_appended = True

            query += f" LOWER(_name) LIKE '%{name_query}%'"
            append_and = True

        if model_types is not None and len(model_types) > 0:
            if not is_where_appended:
                query += ' WHERE'
                is_where_appended = True

            if append_and:
                query += ' AND'

            query += ' ('
            append_or = False
            for model_type in model_types:
                if append_or:
                    query += ' OR'
                query += f" model_type='{model_type}'"
                append_or = True

            query += ')'

            append_and = True
            pass

        if groups is not None and len(groups) > 0:
            if not is_where_appended:
                query += ' WHERE'

            for group in groups:
                if append_and:
                    query += ' AND'
                query += f" LOWER(groups) LIKE '%{group}%'"
                append_and = True

        logger.debug('query: %s',query)
        cursor = self._connection().cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            record = map_row_to_record(row)
            is_downloaded = bool(record.location) and os.path.exists(record.location)

            if show_downloaded and is_downloaded:
                result.append(record)
            elif show_not_downloaded and not is_downloaded:
                result.append(record)

        return result

    def get_record_by_id(self, id_) -> Record:
        cursor = self._connection().cursor()
        cursor.execute('SELECT * FROM Record WHERE id=?', (id_,))
        row = cursor.fetchone()
        return None if row is None else map_row_to_record(row)

    def get_records_by_group(self, group: str) -> List:
        cursor = self._connection().cursor()
        cursor.execute(f"SELECT * FROM Record WHERE LOWER(groups) LIKE '%{group}%'")
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append(map_row_to_record(row))
        return result

    def get_records_by_query(self, query: str) -> List:
        cursor = self._connection().cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append(map_row_to_record(row))
        return result

    def add_record(self, record: Record):
        cursor = self._connection().cursor()
        data = (
            record.name,
            record.model_type.value,
            record.download_url,
            record.url,
            record.download_path,
            record.download_filename,
            record.preview_url,
            record.description,
            record.positive_prompts,
            record.negative_prompts,
            record.sha256_hash,
            record.md5_hash,
            record.created_at,
            ",".join(record.groups),
            record.subdir,
            record.location,
            record.weight,
            record.backup_url
        )
        cursor.execute(
            """INSERT INTO Record(
                    _name,
                    model_type,
                    download_url,
                    url,
                    download_path,
                    download_filename,
                    preview_url,
                    description,
                    positive_prompts,
                    negative_prompts,
                    sha256_hash,
                    md5_hash,
                    created_at,
                    groups,
                    subdir,
                    location,
                    weight,
                    backup_url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data)
        self._connection().commit()

    def update_record(self, record: Record):
        cursor = self._connection().cursor()
        data = (
            record.name,
            record.model_type.value,
            record.download_url,
            record.url,
            record.download_path,
            record.download_filename,
            record.preview_url,
            record.description,
            record.positive_prompts,
            record.negative_prompts,
            record.sha256_hash,
            record.md5_hash,
            ",".join(record.groups),
            record.subdir,
            record.location,
            record.weight,
            record.backup_url,
            record.id_
        )
        cursor.execute(
            """UPDATE Record SET 
                    _name=?,
                    model_type=?,
                    download_url=?,
                    url=?,
                    download_path=?,
                    download_filename=?,
                    preview_url=?,
                    description=?,
                    positive_prompts=?,
                    negative_prompts=?,
                    sha256_hash=?,
                    md5_hash=?,
                    groups=?,
                    subdir=?,
                    location=?,
                    weight=?,
                    backup_url=?
                WHERE id=?
            """, data
        )

        self._connection().commit()

    def remove_record(self, _id):
        cursor = self._connection().cursor()
        cursor.execute("DELETE FROM Record WHERE id=?", (_id,))
        self._connection().commit()

    def get_available_groups(self) -> List:
        cursor = self._connection().cursor()
        cursor.execute('SELECT groups FROM Record')
        rows = cursor.fetchall()
        result = []
        for row in rows:
            if row[0]:
                result.extend(row[0].split(","))

        result = list(set(result))
        return list(filter(None, result))

    def get_all_records_locations(self) -> List:
        cursor = self._connection().cursor()
        cursor.execute('SELECT location FROM Record')
        rows = cursor.fetchall()
        result = []
        for row in rows:
            if row[0]:
                result.append(row[0])

        return result
