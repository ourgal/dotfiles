import sqlite3
import tempfile
import unittest
from pathlib import Path

import seanime_db


class PatchSettingsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "seanime.db"
        con = sqlite3.connect(self.db)
        con.execute(
            "create table settings (id integer primary key, library_path text, "
            "library_paths text, torrent_provider text)"
        )
        con.execute("insert into settings (id) values (1)")
        con.commit()
        con.close()

    def read(self) -> tuple:
        con = sqlite3.connect(self.db)
        try:
            return con.execute(
                "select library_path, library_paths, torrent_provider from settings"
            ).fetchone()
        finally:
            con.close()

    def test_single_library_leaves_library_paths_null(self) -> None:
        seanime_db.patch_settings(self.db, libraries=[self.tmp.name])
        expected = Path(self.tmp.name).resolve().as_posix()
        self.assertEqual(self.read(), (expected, None, None))

    def test_multiple_libraries_are_csv_and_first_is_primary(self) -> None:
        a, b = Path(self.tmp.name) / "a", Path(self.tmp.name) / "b"
        seanime_db.patch_settings(self.db, libraries=[str(a), str(b)], provider="animetosho-new")
        self.assertEqual(
            self.read(),
            (a.resolve().as_posix(), b.resolve().as_posix(), "animetosho-new"),
        )

    def test_nested_libraries_are_rejected(self) -> None:
        a, b = Path(self.tmp.name) / "a", Path(self.tmp.name) / "a" / "b"
        with self.assertRaisesRegex(seanime_db.SetupError, "nested"):
            seanime_db.patch_settings(self.db, libraries=[str(a), str(b)])

    def test_duplicate_libraries_are_rejected(self) -> None:
        with self.assertRaisesRegex(seanime_db.SetupError, "duplicate"):
            seanime_db.patch_settings(self.db, libraries=[self.tmp.name, self.tmp.name])

    def test_provider_only_keeps_library_columns(self) -> None:
        seanime_db.patch_settings(self.db, libraries=[self.tmp.name])
        seanime_db.patch_settings(self.db, provider="")
        self.assertEqual(self.read()[2], "")

    def test_no_changes_is_a_noop(self) -> None:
        self.assertEqual(seanime_db.patch_settings(self.db), [])

    def test_missing_columns_raise(self) -> None:
        con = sqlite3.connect(self.db)
        con.execute("drop table settings")
        con.execute("create table settings (id integer primary key)")
        con.commit()
        con.close()
        with self.assertRaises(seanime_db.SetupError):
            seanime_db.patch_settings(self.db, provider="x")


if __name__ == "__main__":
    unittest.main()
