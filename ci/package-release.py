#!/usr/bin/env python3
"""Validate a dagu boot image before packaging it for a GitHub Release."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unpack_ramdisk(data):
    files = {}
    offset = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        require(header[:6] in (b"070701", b"070702"), "Invalid CPIO header")
        size = int(header[54:62], 16)
        name_size = int(header[94:102], 16)
        require(name_size > 0, "Invalid CPIO filename length")
        name = data[offset + 110:offset + 110 + name_size - 1].decode()
        offset = (offset + 110 + name_size + 3) & ~3
        require(offset + size <= len(data), "Truncated CPIO entry")
        if name == "TRAILER!!!":
            return files
        files[name.removeprefix("./")] = data[offset:offset + size]
        offset = (offset + size + 3) & ~3
    raise ValueError("Missing CPIO trailer")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--device-tree", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkfc", type=Path, required=True)
    parser.add_argument("--avbtool", type=Path, required=True)
    args = parser.parse_args()
    tree = args.device_tree.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = args.image.read_bytes()
    require(len(image) == 134217728, "Expected a 128 MiB dagu boot image")
    require(image[:8] == b"ANDROID!", "Missing Android boot header")
    require(struct.unpack_from("<I", image, 40)[0] == 3, "Expected header v3")
    kernel_size, ramdisk_size, os_version = struct.unpack_from("<III", image, 8)
    require((os_version >> 25, (os_version >> 18) & 127,
             (os_version >> 11) & 127) == (13, 0, 0), "Expected Android 13")
    kernel = image[4096:4096 + kernel_size]
    require(kernel == (tree / "prebuilt/dagu/kernel").read_bytes(),
            "Packaged kernel does not match dagu")
    start = (4096 + kernel_size + 4095) & ~4095
    files = unpack_ramdisk(gzip.decompress(image[start:start + ramdisk_size]))
    props = dict(line.split("=", 1) for line in files["prop.default"].decode().splitlines()
                 if "=" in line and not line.startswith("#"))
    expected = {"ro.twrp.device.name": "dagu", "ro.twrp.keymaster": "4.0",
                "ro.build.version.release": "13", "ro.product.first_api_level": "31",
                "ro.vndk.version": "32"}
    for key, value in expected.items():
        require(props.get(key) == value, f"Unexpected {key}: {props.get(key)}")
    version = re.search(r"TW_DEVICE_VERSION\s*:=\s*(MIUI14-A13\S*)",
                        (tree / "BoardConfig.mk").read_text()).group(1)
    require(version.encode() in files["system/bin/recovery"], "Unexpected recovery version")
    for name in ["init.recovery.qcom.rc", "system/etc/recovery.fstab", "system/etc/twrp.flags"]:
        require(files[name] == (tree / "recovery/root" / name).read_bytes(),
                f"Packaged {name} differs from source")
    init = files["init.recovery.qcom.rc"].decode().split("\non init\n", 1)[1].split("\non ", 1)[0]
    require(init.index("symlink /persist /mnt/vendor/persist") < init.index("start vendor.qseecomd"),
            "Persist alias must exist before QSEE starts")
    flags = files["system/etc/twrp.flags"].decode()
    persist = [line for line in flags.splitlines() if line.split()[:1] == ["/persist"]]
    require(len(persist) == 1 and ";mounttodecrypt" in persist[0],
            "Persist must be mounted for credential verification")
    contexts = set()
    for name in ["system/etc/recovery.fstab", "system/etc/twrp.flags"]:
        for line in files[name].decode().splitlines():
            if not line or line.startswith("#"):
                continue
            if name.endswith("recovery.fstab"):
                require(len(line.split()) == 5, f"Invalid fstab entry: {line}")
            for options in re.findall(r'fsflags="([^"]+)"', line):
                require(not re.search(r"\s", options), "Whitespace in mount options")
            contexts.update(re.findall(r'context=(u:object_r:[^ ,";]+)', line))
    require(contexts == {"u:object_r:vendor_file:s0"}, "Unexpected mount contexts")
    with tempfile.TemporaryDirectory(prefix="dagu-policy-") as tmp:
        policy = Path(tmp) / "sepolicy"
        policy.write_bytes(files["sepolicy"])
        context_file = Path(tmp) / "file_contexts"
        context_file.write_text("/firmware u:object_r:vendor_file:s0\n")
        subprocess.run([str(args.checkfc.resolve()), str(policy), str(context_file)], check=True)
    keymaster = []
    for name, contents in files.items():
        if name.startswith("vendor/etc/vintf/") and name.endswith(".xml"):
            for hal in ET.fromstring(contents).findall("hal"):
                if hal.findtext("name") == "android.hardware.keymaster":
                    keymaster.append(hal.findtext("version"))
    require(keymaster == ["4.0"], f"Unexpected Keymaster manifests: {keymaster}")
    require("vendor/etc/vintf/manifest/android.hardware.keymaster@4.1.xml" not in files,
            "Keymaster 4.1 must not be packaged for dagu")
    module = files["vendor/lib/modules/1.1/exfat.ko"]
    require(module == (tree / "prebuilt/dagu/modules/1.1/exfat.ko").read_bytes(),
            "Packaged exfat module does not match dagu")
    kernel_release = re.search(rb"Linux version ([^ ]+)", kernel).group(1).decode()
    vermagic = re.search(rb"vermagic=([^\0]+)", module).group(1).decode()
    require(vermagic.split()[0] == kernel_release, "Kernel/module version mismatch")
    avb = subprocess.run([str(args.avbtool.resolve()), "verify_image", "--image",
                          str(args.image.resolve())], capture_output=True, text=True, check=True)
    (output / "avb-verify.log").write_text(avb.stdout + avb.stderr)
    target = output / "boot.img"
    if args.image.resolve() != target:
        shutil.copyfile(args.image, target)
    commit = subprocess.check_output(["git", "-C", str(tree), "rev-parse", "HEAD"], text=True).strip()
    info = {"device": "dagu", "device_version": version, "device_tree_commit": commit,
            "image_sha256": hashlib.sha256(image).hexdigest(), "image_size": len(image),
            "header_version": 3, "android_version": "13", "properties": expected,
            "kernel_release": kernel_release, "module_vermagic": vermagic,
            "persist_mounttodecrypt": True, "packaged_mount_contexts_checked": True,
            "run_url": (f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/'
                        f'{os.environ["GITHUB_RUN_ID"]}' if "GITHUB_RUN_ID" in os.environ else None)}
    (output / "build-info.json").write_text(json.dumps(info, indent=2) + "\n")
    (output / "RELEASE_NOTES.md").write_text(
        f"TWRP **{version}** for Xiaomi Pad 5 Pro 12.4 (**dagu**), MIUI 14 / Android 13.\n\n"
        f"Device tree commit: `{commit}`.\n\n"
        "Includes the QSEE persist alias and mount-before-decrypt fix. The user initially "
        "reported successful decryption with r3 on the MIUI Pad 14.0.6.0(TMHCNXM) port. "
        "Each new CI image still needs on-device verification.\n\n"
        "Verify `SHA256SUMS`, then test with `fastboot boot boot.img`. "
        "Do not flash this complete image directly to boot.\n")
    assets = sorted(p for p in output.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    (output / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in assets))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
