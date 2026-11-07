import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from schola.sqlite_runtime import ARCHIVE_SHA3, SOURCE_ID, SOURCE_SHA3, VERSION, runtime_environment, validate_runtime


class SQLiteRuntimeTests(unittest.TestCase):
    def test_missing_optional_runtime_preserves_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            environment = {"PATH": "/usr/bin"}
            self.assertEqual(runtime_environment(root, environment), environment)
            with self.assertRaises(RuntimeError):
                runtime_environment(root, environment, required=True)

    def test_present_runtime_validates_digest_and_prepends_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "private/runtime" / f"sqlite-{VERSION}"
            (runtime / "lib").mkdir(parents=True)
            library = runtime / "lib/libsqlite3.so.0"
            library.write_bytes(b"test library")
            receipt = {"version": VERSION, "source_id": SOURCE_ID, "archive_sha3": ARCHIVE_SHA3, "source_sha3": SOURCE_SHA3, "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest()}
            (runtime / "manifest.json").write_text(json.dumps(receipt))
            previous = {"LD_LIBRARY_PATH": "/another/library", "PATH": "/usr/bin"}
            result = runtime_environment(root, previous)
            self.assertEqual(result["LD_LIBRARY_PATH"], str(runtime / "lib") + ":/another/library")
            self.assertEqual(runtime_environment(root, result), result)
            self.assertEqual(previous["LD_LIBRARY_PATH"], "/another/library")
            library.write_bytes(b"damaged library")
            with self.assertRaises(RuntimeError):
                runtime_environment(root, previous)

    def test_partial_runtime_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            runtime.mkdir()
            with self.assertRaises(RuntimeError):
                validate_runtime(runtime)
            link = Path(directory) / "link"
            link.symlink_to(runtime, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                validate_runtime(link)

    def test_untrusted_archive_is_rejected_before_extraction(self):
        path = Path(__file__).resolve().parents[1] / "scripts/install-sqlite-runtime.py"
        specification = importlib.util.spec_from_file_location("install_sqlite_runtime", path)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            module.source_from_archive(b"not an official SQLite release")


if __name__ == "__main__":
    unittest.main()
