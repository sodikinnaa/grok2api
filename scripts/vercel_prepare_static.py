from pathlib import Path
import shutil


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    src = root / "app" / "static"
    dst = root / "public" / "static"

    if not src.exists():
        print(f"[vercel-prepare-static] source not found, skip: {src}")
        return

    if dst.exists():
        shutil.rmtree(dst)

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)
    print(f"[vercel-prepare-static] copied {src} -> {dst}")


if __name__ == "__main__":
    main()
