# -*- coding: utf-8 -*-
"""Общие настройки тестов: отдельная временная база и известный администратор."""

import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="normocontrol-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP, "test.db").replace("\\", "/")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ADMIN_LOGIN"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin-pass-123"
os.environ.pop("RENDER", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
