"""The live API must never load the training libraries.

Railway installs only requirements.txt. If any server module imported pandas,
scipy or implicit, the deployed app would crash on start-up — and the test
suite would not notice, because the dev environment has them installed.

Run in a fresh Python process: in this one, other tests have already
imported pandas, so checking sys.modules here would prove nothing.
"""

import subprocess
import sys
from pathlib import Path

TRAINING_ONLY = ("pandas", "scipy", "implicit", "pyarrow", "threadpoolctl")


def test_importing_the_app_loads_no_training_library():
    backend = Path(__file__).resolve().parent.parent
    code = (
        "import sys, app.main; "
        f"print([m for m in {TRAINING_ONLY!r} if m in sys.modules])"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=backend, capture_output=True, text=True, check=True
    )

    assert result.stdout.strip() == "[]", result.stdout
