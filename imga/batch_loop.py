import os
import sys
import time
os.environ.pop("SSL_CERT_FILE", None)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))
import gradio as gr
from core import Core
import config.config as config
import pandas as pd
from math import ceil
import tempfile
import shutil
import argparse
import subprocess
core = Core(
    upload_temp_dir="./data/temp",
    raw_dir=config.PDF_DIR,
    meta_path=config.META_DIR,
    result_dir=config.RESULT_DIR,
    image_dir=config.IMAGE_DIR,
    api_key=config.OPENAI_API_KEY
)

def clean_temp_dir(folder_path = "./pre_process"):
    files = len(os.listdir(folder_path))
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.remove(file_path)         # 파일 또는 링크
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)     # 서브폴더 전체 삭제
        except Exception as e:
            print(f"삭제 실패: {file_path} - {e}")
    return f"✅ {files} of Temp files removed."

def chunk_list(lst, chunk_size):
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

# --------------------------
# [1] 파일 업로드 → Batch 실행
# --------------------------

def upload_files_and_batch(upload_files, project):
    if not upload_files:
        return "❌ No files uploaded."

    file_records, skipped_files = core.upload_files(upload_files,project)
    code_files = [(r["org_filename"], r["code_filename"]) for r in file_records]
    print("skipping...", len(skipped_files))
    if not code_files:
        return "⛔ All files are duplicates."

    batch_size = 3
    batch_count = ceil(len(code_files) / batch_size)
    
    print("🚀 Starting batch processing...", batch_size)
    i = 0
    for chunk in chunk_list(code_files, batch_size):
        core.execute_batch_process(chunk, project)
        i += 1
        print(f"Batch {i}/{batch_count} submitted with {len(chunk)} files.")

    msg = f"✅ Uploaded {len(code_files)} new files. Created {batch_count} Batch Groups."

    if skipped_files:
        msg += f"\n⛔ Skipped {len(skipped_files)} duplicate files: {', '.join(skipped_files)}"

    return msg

# --------------------------
# [2] 상태 보기 (Meta + DB)
# --------------------------

def get_batch_status():

    core.status_update()
    meta_status = core.get_status()
    rows = []
    # Meta status
    for meta in meta_status:
        rows.append({
            "project": meta.get("project"),
            "page_type": meta.get("page_type"),
            "Status": meta.get("status"),
            "last_updated_at": meta.get("last_updated_at"),
            "batch_id": meta.get("batch_id")
        })

    return pd.DataFrame(rows)

# --------------------------
# [3] 다운로드 가능한 메타 파일
# --------------------------

def get_downloadable_files():
    metas = core.get_status()
    core.postprocess_results()
    downloadable = {}
    files = os.listdir(os.path.join(config.RESULT_DIR, "output"))
    for file in files:
        if file.endswith(".csv"):
            downloadable[file] = os.path.join(config.RESULT_DIR,"output", file)

    return downloadable

def download_file(file_path):
    return file_path

def download_selected_files_as_zip(selected_files):
    all_files = get_downloadable_files()
    temp_dir = tempfile.mkdtemp()

    for fname in selected_files:
        if fname in all_files:
            shutil.copy(all_files[fname], os.path.join(temp_dir, fname))

    zip_path = shutil.make_archive(os.path.join(temp_dir, "batch_results"), 'zip', temp_dir)
    return zip_path
    

def simulate_gradio_files(file_paths):
    return [open(path, "rb") for path in file_paths]

def process_all_files(work_path):
    months = os.listdir(work_path)

    for month in months:
        month_path = os.path.join(work_path, month)
        for location in os.listdir(month_path):
            file_dir = os.path.join(month_path, location)
            if os.path.isdir(file_dir):
                files = os.listdir(file_dir)
                file_paths = [os.path.join(file_dir, f) for f in files if f.endswith('.pdf')]
                gradio_files = simulate_gradio_files(file_paths)

                try:
                    loc_code = location.split(".")[1]
                except IndexError:
                    loc_code = location
                project_name = f"{loc_code}_{month.replace('년','').replace('월','')}"

                print(f"🚀 Submitting: {project_name}")
                msg = upload_files_and_batch(gradio_files, project_name)
                print(msg)
    
def wait_until_finished():
    while True:
        time.sleep(20)
        status_df = get_batch_status()
        if status_df.empty:
            print("📭 No status available yet...")
            continue

        if (status_df["Status"] == "completed").all():
            core.postprocess_results()
            # subprocess.run(["python", "./porst_process_script.py"], check=True)
            print("✅ All batches completed and postprocessed.")
            break
        else:
            print("⏳ Waiting for remaining batches...")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch PDF processor")
    parser.add_argument("--work_path", type=str, required=True, help="Base folder path to process")
    args = parser.parse_args()

    try:
        process_all_files(args.work_path)
        wait_until_finished()
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)