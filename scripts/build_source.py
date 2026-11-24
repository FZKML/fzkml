"""Build a source-only archive containing exactly the inventoried public files."""
import gzip
import io
from pathlib import Path
import tarfile
from check_governance import ROOT, digest, public_path, read_json, validate


def build(root=ROOT, destination=None):
    validate(root)
    destination = destination or root / "dist/fzkml-source.tar.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for name in sorted(read_json(root / "compliance/files.json")["files"]):
                    data = public_path(root, name).read_bytes()
                    info = tarfile.TarInfo("fzkml/" + name)
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    archive.addfile(info, io.BytesIO(data))
    destination.with_suffix(destination.suffix + ".sha256").write_text(
        digest(destination) + "  " + destination.name + "\n"
    )
    print(destination)
    return destination


if __name__ == "__main__":
    build()
