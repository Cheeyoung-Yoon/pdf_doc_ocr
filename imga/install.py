import os
from app.config import config


def create_directories():
    dirs = [
        config.PDF_DIR,
        config.IMAGE_DIR,
        config.RESULT_DIR,
        os.path.join(config.RESULT_DIR, "output"),
        config.META_DIR,
        os.path.join(os.path.dirname(config.META_DIR), "batch_results"),
        os.path.join(".", "data", "temp"),
        os.path.join(".", "final_outputs"),
        os.path.join(".", "pre_process"),
    ]

    for d in dirs:
        path = os.path.normpath(d)
        os.makedirs(path, exist_ok=True)
        print(f"Created: {path}")


if __name__ == "__main__":
    create_directories()
    print("\n📂 Directory setup complete.")