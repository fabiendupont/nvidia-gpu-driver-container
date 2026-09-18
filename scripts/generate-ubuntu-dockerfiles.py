#!/usr/bin/env python3
"""Generate Ubuntu Dockerfiles and scripts from templates in ubuntu/.

Run from the repository root:
    python3 scripts/generate-ubuntu-dockerfiles.py
  or:
    make generate

Version config:  ubuntu/versions.yaml        (edit here to add/update versions)
Templates:       ubuntu/*.template            (edit here for structural changes)

ubuntu 26.04 uses a different install architecture (DKMS packages) and is not
generated from shared templates — its files are committed statically in ubuntu/26.04/.

Generated files are NOT committed — they are produced at build time.
"""

import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml  or  dnf install python3-pyyaml")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _header(template_name: str) -> str:
    return (f"# DO NOT EDIT: generated from ubuntu/{template_name}\n"
            "# Run 'make generate' to regenerate.\n")


def render(template: str, substitutions: dict) -> str:
    result = template
    for marker, value in substitutions.items():
        result = result.replace(f"@@{marker}@@", value)
    return result


def check_unresolved(content: str, path: str) -> None:
    unresolved = re.findall(r"@@[A-Z_]+@@", content)
    if unresolved:
        print(f"ERROR: unresolved markers in {path}: {unresolved}", file=sys.stderr)
        sys.exit(1)


def write_if_changed(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path) as f:
            if f.read() == content:
                print(f"  unchanged: {os.path.relpath(path, REPO_ROOT)}")
                return
    with open(path, "w") as f:
        f.write(content)
    print(f"  wrote:     {os.path.relpath(path, REPO_ROOT)}")


def load_template(ubuntu_dir: str, name: str) -> str:
    with open(os.path.join(ubuntu_dir, name)) as f:
        return f.read()


def generate(ubuntu_dir: str, template_name: str, dest_path: str,
             substitutions: dict = None) -> None:
    template = load_template(ubuntu_dir, template_name)
    content = _header(template_name) + (render(template, substitutions) if substitutions else template)
    check_unresolved(content, dest_path)
    write_if_changed(dest_path, content)


def load_versions(ubuntu_dir: str) -> list:
    with open(os.path.join(ubuntu_dir, "versions.yaml")) as f:
        return yaml.safe_load(f)


def main() -> None:
    ubuntu_dir = os.path.join(REPO_ROOT, "ubuntu")
    versions = load_versions(ubuntu_dir)

    print("Generating Ubuntu files from templates...")

    for ver in versions:
        version = ver["version"]
        out_dir = os.path.join(ubuntu_dir, version)
        subs = {
            "BASE_IMAGE":           ver["base_image"],
            "UBUNTU_VERSION":       f"ubuntu{version}",
            "DRIVER_BRANCH":        ver["driver_branch"],
            "CUDA_VERSION_NODOT":   ver["cuda_version_nodot"],
        }

        generate(ubuntu_dir, "Dockerfile.template",
                 os.path.join(out_dir, "Dockerfile"), subs)

        generate(ubuntu_dir, "install.sh.template",
                 os.path.join(out_dir, "install.sh"),
                 {"CUDA_VERSION_NODOT": ver["cuda_version_nodot"]})

        generate(ubuntu_dir, "precompiled/Dockerfile.template",
                 os.path.join(out_dir, "precompiled", "Dockerfile"), subs)

        # Copy shared precompiled scripts (identical for all generated versions)
        for script in ("local-repo.sh", "nvidia-driver"):
            src = os.path.join(ubuntu_dir, "precompiled", script)
            dst = os.path.join(out_dir, "precompiled", script)
            with open(src) as f:
                content = f.read()
            write_if_changed(dst, content)

    print("Done.")


if __name__ == "__main__":
    main()
