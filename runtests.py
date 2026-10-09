#!/usr/bin/env python
"""Run the test suite without an Alliance Auth instance, on testauth.

    python runtests.py eos_spy_network [manage.py test options]

testauth/settings/local.py keeps its own sqlite database, the test runner
puts the test database in memory; nothing here reaches a real Auth database.
Redis on localhost has to run, as for Alliance Auth itself (cache).
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testauth.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line([sys.argv[0], "test", *sys.argv[1:]])
