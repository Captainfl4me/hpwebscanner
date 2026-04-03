"""Configuration validation tests using subprocess.

These tests spawn a separate Python process to test startup validation,
avoiding interference with the main test suite's imported modules.
"""
import os
import sys
import subprocess
import pytest


def run_main_import_test(env_vars):
    """Helper: run python -c 'import main' with given env vars, return exit code and output."""
    env = os.environ.copy()
    env.update(env_vars)
    # Ensure src directory is in PYTHONPATH
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(project_root, "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-c", "import main"],
        capture_output=True,
        text=True,
        env=env,
        cwd=project_root
    )
    return result.returncode, result.stdout, result.stderr


def test_save_folder_non_writable_exits(tmp_path):
    """Test that SAVE_FOLDER without write permission causes exit code 1."""
    save_dir = tmp_path / "readonly"
    save_dir.mkdir()
    os.chmod(save_dir, 0o444)  # Read-only
    
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": str(save_dir)
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 1
    assert "not writable" in stderr.lower() or "failed to validate" in stderr.lower()


def test_save_folder_is_file_exits(tmp_path):
    """Test that SAVE_FOLDER pointing to a file (not directory) causes exit code 1."""
    save_file = tmp_path / "not_a_dir"
    save_file.touch()
    
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": str(save_file)
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 1
    assert "not a directory" in stderr.lower() or "failed to validate" in stderr.lower()


def test_max_jobs_invalid_value_exits():
    """Test that invalid MAX_JOBS (non-integer) causes exit code 1."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "MAX_JOBS": "invalid"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 1
    # Error message goes to stderr
    assert "max_jobs" in stderr.lower() and "integer" in stderr.lower()


def test_max_jobs_negative_value_allowed():
    """Test that negative MAX_JOBS is parsed without exit (validation not strict)."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "MAX_JOBS": "-1",
        "SAVE_FOLDER": "/tmp"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    # Negative values are technically integers, so should not cause parse error
    assert code == 0, f"Expected success but got exit {code}, stderr: {stderr}"


def test_ssl_verify_parsing_lowercase_false():
    """Test that SSL_VERIFY='false' is parsed as False."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": "/tmp",
        "SSL_VERIFY": "false"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 0
    # Check combined output for the log line
    output = stdout + stderr
    assert "SSL_VERIFY: False" in output or "SSL_VERIFY:False" in output


def test_ssl_verify_parsing_uppercase_false():
    """Test that SSL_VERIFY='FALSE' is parsed as False (case-insensitive)."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": "/tmp",
        "SSL_VERIFY": "FALSE"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 0
    output = stdout + stderr
    assert "SSL_VERIFY: False" in output or "SSL_VERIFY:False" in output


def test_ssl_verify_parsing_true_default():
    """Test that default SSL_VERIFY is True and 'true' gives True."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": "/tmp",
        "SSL_VERIFY": "true"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 0
    output = stdout + stderr
    assert "SSL_VERIFY: True" in output or "SSL_VERIFY:True" in output


def test_log_level_invalid_exits():
    """Test that invalid LOG_LEVEL causes exit code 1."""
    env_vars = {
        "SCANNER_IP": "192.168.1.100",
        "SAVE_FOLDER": "/tmp",
        "LOG_LEVEL": "INVALID"
    }
    code, stdout, stderr = run_main_import_test(env_vars)
    assert code == 1
    assert "Invalid LOG_LEVEL" in stderr or "LOG_LEVEL" in stderr


def test_log_level_valid_all_levels():
    """Test that all standard logging levels are accepted."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    for level in valid_levels:
        env_vars = {
            "SCANNER_IP": "192.168.1.100",
            "SAVE_FOLDER": "/tmp",
            "LOG_LEVEL": level
        }
        code, stdout, stderr = run_main_import_test(env_vars)
        assert code == 0, f"LOG_LEVEL={level} should succeed, stderr: {stderr}"
