# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path

from engine.paths import ENV_DATA_DIR, resolve_path


class PathTest(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="companion_paths_"))
        self.default = self.base / "plugin_data"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.base, ignore_errors=True)

    def test_precedence(self):
        old = os.environ.get(ENV_DATA_DIR)
        try:
            os.environ[ENV_DATA_DIR] = str(self.base / "from_env")
            self.assertEqual(
                resolve_path(str(self.base / "from_config"), ENV_DATA_DIR, self.default, self.base),
                (self.base / "from_config").resolve(),
            )
            self.assertEqual(
                resolve_path("", ENV_DATA_DIR, self.default, self.base),
                (self.base / "from_env").resolve(),
            )
            os.environ.pop(ENV_DATA_DIR, None)
            self.assertEqual(
                resolve_path("", ENV_DATA_DIR, self.default, self.base),
                self.default.resolve(),
            )
        finally:
            if old is None:
                os.environ.pop(ENV_DATA_DIR, None)
            else:
                os.environ[ENV_DATA_DIR] = old

    def test_relative_to_base(self):
        self.assertEqual(
            resolve_path("state", None, self.default, self.base),
            (self.base / "state").resolve(),
        )


if __name__ == "__main__":
    unittest.main()
