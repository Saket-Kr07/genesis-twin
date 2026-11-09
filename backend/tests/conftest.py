"""Runs before any test file is imported: throwaway upload folder and test secrets."""
import os
import tempfile

os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="genesis-uploads-"))
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret")
