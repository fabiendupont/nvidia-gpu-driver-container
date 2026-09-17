#!/usr/bin/env python3
"""Generate RHEL Dockerfiles and scripts from templates in rhel/.

Run from the repository root:
    python3 scripts/generate-rhel-dockerfiles.py
  or:
    make generate

Version config:  rhel/versions.yaml        (edit here to add/update versions)
Templates:       rhel/*.template            (edit here for structural changes)

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

NODOCS_SETUP = """\
RUN { grep -qE '^tsflags=.*nodocs' /etc/dnf/dnf.conf || \\
      dnf config-manager --save --setopt=tsflags=nodocs; } && \\
    dnf update -y && dnf clean all"""


def _header(template_name: str) -> str:
    return (f"# DO NOT EDIT: generated from rhel/{template_name}\n"
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


def load_template(template_dir: str, name: str) -> str:
    with open(os.path.join(template_dir, name)) as f:
        return f.read()


def generate(template_dir: str, template_name: str, dest_path: str,
             substitutions: dict = None) -> None:
    template = load_template(template_dir, template_name)
    content = _header(template_name) + (render(template, substitutions) if substitutions else template)
    check_unresolved(content, dest_path)
    write_if_changed(dest_path, content)


def load_versions(rhel_dir: str) -> list:
    with open(os.path.join(rhel_dir, "versions.yaml")) as f:
        return yaml.safe_load(f)


def main() -> None:
    rhel_dir = os.path.join(REPO_ROOT, "rhel")
    versions = load_versions(rhel_dir)

    print("Generating RHEL files from templates...")

    common_sh = load_template(rhel_dir, "common.sh.template")

    for ver in versions:
        major = str(ver["major"])
        out_dir = os.path.join(rhel_dir, major)
        subs = {
            "BASE_IMAGE":   ver["base_image"],
            "RHEL_MAJOR":   major,
            "GPGKEY_SUM":   ver["gpgkey_sum"],
            "CUDA_KEY_FILE": ver["cuda_key_file"],
            "NODOCS_SETUP": NODOCS_SETUP,
        }
        major_subs = {"RHEL_MAJOR": major}

        generate(rhel_dir, "Dockerfile.template",
                 os.path.join(out_dir, "Dockerfile"), subs)

        generate(rhel_dir, "ocp_dtk_entrypoint.template",
                 os.path.join(out_dir, "ocp_dtk_entrypoint"), major_subs)

        generate(rhel_dir, "nvidia-driver.template",
                 os.path.join(out_dir, "nvidia-driver"), major_subs)

        generate(rhel_dir, "install.sh.template",
                 os.path.join(out_dir, "install.sh"), major_subs)

        # common.sh is identical across all versions
        content = _header("common.sh.template") + common_sh
        check_unresolved(content, f"rhel/{major}/common.sh")
        write_if_changed(os.path.join(out_dir, "common.sh"), content)

        if ver.get("precompiled"):
            generate(rhel_dir, "precompiled/Dockerfile.template",
                     os.path.join(out_dir, "precompiled", "Dockerfile"))

    print("Done.")


if __name__ == "__main__":
    main()
