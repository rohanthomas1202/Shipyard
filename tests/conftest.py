import os
import tempfile
import pytest

@pytest.fixture
def tmp_codebase():
    """Create a temporary directory with sample files for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample TypeScript file
        ts_file = os.path.join(tmpdir, "sample.ts")
        with open(ts_file, "w") as f:
            f.write(
                'export interface Issue {\n'
                '  id: string;\n'
                '  title: string;\n'
                '  description: string;\n'
                '  status: "open" | "closed";\n'
                '}\n'
            )
        # Create a sample JSON file
        json_file = os.path.join(tmpdir, "config.json")
        with open(json_file, "w") as f:
            f.write('{\n  "port": 3000,\n  "host": "localhost"\n}\n')
        # Create a nested directory
        nested = os.path.join(tmpdir, "src", "models")
        os.makedirs(nested)
        model_file = os.path.join(nested, "user.ts")
        with open(model_file, "w") as f:
            f.write(
                'export interface User {\n'
                '  id: string;\n'
                '  name: string;\n'
                '  email: string;\n'
                '}\n'
            )
        yield tmpdir
